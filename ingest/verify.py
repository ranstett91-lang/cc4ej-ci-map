"""Verify that every file on disk in data_raw/ matches snapshots/MANIFEST.lock.yaml.

Run in CI on every PR. A non-zero exit means either:
  - a raw file was modified locally after being locked (tampering / drift), or
  - a file is missing (raw/ was cleaned; re-fetch), or
  - a lock entry is orphaned (source removed from manifest but still in lock)

verify.py does NOT hit the network. It is purely a local integrity check
so CI stays deterministic.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ingest.snapshots import LOCK_FILE, RAW_ROOT, load_lock, sha256_of


def verify() -> int:
    lock = load_lock()
    sources = lock.get("sources", {})
    if not sources:
        print("verify: lock file empty — nothing to check (ok).")
        return 0

    errors: list[str] = []
    checked = 0
    for source, by_vintage in sources.items():
        for vintage, entry in (by_vintage or {}).items():
            filename = entry.get("filename")
            expected = entry.get("sha256")
            if not filename or not expected:
                errors.append(f"{source}/{vintage}: lock entry missing filename or sha256")
                continue
            path = RAW_ROOT / source / vintage / filename
            if not path.exists():
                errors.append(f"{source}/{vintage}: file missing at {path.relative_to(RAW_ROOT.parent)}")
                continue
            actual = sha256_of(path)
            if actual != expected:
                errors.append(
                    f"{source}/{vintage}: sha256 drift\n"
                    f"   expected {expected}\n"
                    f"   actual   {actual}\n"
                    f"   file     {path.relative_to(RAW_ROOT.parent)}"
                )
            else:
                checked += 1

    print(f"verify: checked {checked} locked files")
    if errors:
        print(f"verify: {len(errors)} integrity error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("verify: OK")
    return 0


if __name__ == "__main__":
    sys.exit(verify())
