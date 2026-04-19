"""Snapshot-and-lock layer for the ingest pipeline.

Every raw file the pipeline pulls gets:
  - stored under data_raw/<source>/<vintage>/<filename>
  - SHA-256 hashed
  - recorded in snapshots/MANIFEST.lock.yaml with the mirror that served it,
    the timestamp, the byte size, and the URL that actually responded

This is the "cannot be silently taken down" layer. If EPA mutates a
file retroactively (or PEDP rebuilds a vintage with different numbers),
the hash drifts and verify.py fails the CI run.

Python stdlib + requests + PyYAML only. No cloud SDK dependencies —
S3/Zenodo mirroring is a separate opt-in step documented in
docs/INGEST_ARCHITECTURE.md.
"""

from __future__ import annotations

import hashlib
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import requests
    import yaml
except ImportError:
    sys.exit("pip install -r ingest/requirements.txt first (requests, PyYAML)")


ROOT      = Path(__file__).parent.parent
MANIFEST  = ROOT / "ingest" / "manifest.yaml"
LOCK_FILE = ROOT / "snapshots" / "MANIFEST.lock.yaml"
RAW_ROOT  = ROOT / "data_raw"


@dataclass
class SnapshotRecord:
    source:      str       # "ejscreen"
    vintage:     str       # "2023"
    mirror_id:   str       # "gaftp" | "pedp" | "harvard_dataverse" | "edgi"
    url:         str       # actual URL that served the file
    filename:    str       # local filename under data_raw/<source>/<vintage>/
    sha256:      str
    bytes:       int
    fetched_at:  str       # ISO-8601 UTC

    def to_lock_entry(self) -> dict:
        return {
            "mirror":     self.mirror_id,
            "url":        self.url,
            "filename":   self.filename,
            "sha256":     self.sha256,
            "bytes":      self.bytes,
            "fetched_at": self.fetched_at,
        }


def load_manifest() -> dict:
    if not MANIFEST.exists():
        sys.exit(f"manifest missing: {MANIFEST}")
    with MANIFEST.open() as f:
        return yaml.safe_load(f)


def load_lock() -> dict:
    if not LOCK_FILE.exists():
        return {"schema_version": 1, "sources": {}}
    with LOCK_FILE.open() as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("schema_version", 1)
    data.setdefault("sources", {})
    return data


def write_lock(lock: dict) -> None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w") as f:
        yaml.safe_dump(lock, f, sort_keys=True, default_flow_style=False)


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def mirrors_for(source_cfg: dict, vintage: str) -> Iterable[tuple[str, str]]:
    """Yield (mirror_id, url) tuples for a source+vintage in priority order.

    Skips mirrors that don't list this vintage in their `files` map. Priority
    is numeric, lower first (1 = most trusted).
    """
    ranked = sorted(source_cfg.get("mirrors", []), key=lambda m: m.get("priority", 99))
    for m in ranked:
        files = m.get("files", {}) or {}
        if vintage not in files:
            continue   # mirror doesn't claim to host this vintage yet
        filename = files[vintage]
        url = m["url_template"].format(vintage=vintage, file=filename)
        yield m["id"], url


def fetch_with_fallback(source: str, vintage: str, *, timeout: int = 120,
                        force: bool = False) -> SnapshotRecord:
    """Fetch one (source, vintage) to data_raw/. Tries mirrors in priority order.

    Raises RuntimeError if every mirror fails. Sets `force=True` to re-download
    even when an existing file matches the lock.
    """
    manifest = load_manifest()
    source_cfg = manifest.get("sources", {}).get(source)
    if not source_cfg:
        raise RuntimeError(f"source '{source}' not in manifest")

    out_dir = RAW_ROOT / source / vintage
    out_dir.mkdir(parents=True, exist_ok=True)

    last_err: Exception | None = None
    for mirror_id, url in mirrors_for(source_cfg, vintage):
        local_name = url.rsplit("/", 1)[-1].split("?", 1)[0]
        local_path = out_dir / local_name

        if local_path.exists() and not force:
            print(f"  [{source}/{vintage}] already present: {local_path.name}")
            digest = sha256_of(local_path)
            return SnapshotRecord(
                source=source, vintage=vintage, mirror_id=mirror_id,
                url=url, filename=local_path.name, sha256=digest,
                bytes=local_path.stat().st_size,
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )

        print(f"  [{source}/{vintage}] trying {mirror_id}: {url}")
        try:
            resp = requests.get(url, timeout=timeout, stream=True)
            resp.raise_for_status()
            with local_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
            digest = sha256_of(local_path)
            return SnapshotRecord(
                source=source, vintage=vintage, mirror_id=mirror_id,
                url=url, filename=local_path.name, sha256=digest,
                bytes=local_path.stat().st_size,
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        except Exception as e:
            print(f"    {mirror_id} failed: {e}")
            last_err = e
            if local_path.exists():
                local_path.unlink()   # don't leave a partial behind
            time.sleep(1)

    raise RuntimeError(
        f"all mirrors failed for {source}/{vintage} (last: {last_err})"
    )


def record_snapshot(rec: SnapshotRecord) -> None:
    """Append or update a snapshot record in the lock file."""
    lock = load_lock()
    src_bucket = lock["sources"].setdefault(rec.source, {})
    src_bucket[rec.vintage] = rec.to_lock_entry()
    lock["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_lock(lock)
    print(f"  locked {rec.source}/{rec.vintage} @ {rec.sha256[:12]}")


def ensure(source: str, vintages: list[str] | None = None,
           *, force: bool = False) -> None:
    """Fetch + lock every vintage for a source (all, if vintages is None)."""
    manifest = load_manifest()
    source_cfg = manifest.get("sources", {}).get(source)
    if not source_cfg:
        raise RuntimeError(f"source '{source}' not in manifest")
    target_vintages = list(vintages or source_cfg.get("vintages", {}).keys())
    for v in target_vintages:
        try:
            rec = fetch_with_fallback(source, v, force=force)
            record_snapshot(rec)
        except Exception as e:
            print(f"  !! {source}/{v} failed: {e}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Fetch raw sources into data_raw/ and update the lock file.")
    ap.add_argument("--source",   required=True, help="manifest source id (e.g. ejscreen)")
    ap.add_argument("--vintages", default="",    help="comma-sep vintages (default: all configured)")
    ap.add_argument("--force",    action="store_true", help="re-download even if local file exists")
    args = ap.parse_args()
    vs = [v.strip() for v in args.vintages.split(",") if v.strip()] or None
    ensure(args.source, vs, force=args.force)


if __name__ == "__main__":
    main()
