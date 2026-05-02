#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2024-2026 <YOUR NAME>. See LICENSE.md.
"""
fetch_nlcd_impervious.py — build bg_heat_index.json from NLCD 2021.

Produces a measured (non-demographic) heat-island proxy per Delaware block
group by computing the mean percent-developed-imperviousness from the USGS
NLCD 2021 Imperviousness raster (30 m). Impervious surface fraction is one
of the strongest single predictors of summertime Land Surface Temperature
(LST) in published urban-heat-island studies — typical r ≈ 0.7–0.85 vs
Landsat-derived LST in mid-Atlantic cities. Critically, NLCD imperviousness
is derived from satellite imagery, NOT from demographics, so using it to
drive the heat overlay actually tests whether equity focus areas run hotter
rather than re-encoding the demographic signal that defined them.

Output (block-group keyed for fast browser lookup):
    bg_heat_index.json
    {
      "_meta": {
        "source": "USGS NLCD 2021 Percent Developed Imperviousness",
        "url":    "https://www.mrlc.gov/data/nlcd-2021-percent-developed-imperviousness-conus",
        "resolution_m": 30,
        "method":  "Mean impervious % per Census 2020 block group, NLCD 30m raster.",
        "scaling": "lst_proxy_idx = clamp(impervious_pct_mean / 10, 0, 10)",
        "retrieved_utc": "...",
        "n_block_groups": 700
      },
      "block_groups": {
        "100030001001": {"impervious_pct_mean": 67.3, "lst_proxy_idx": 6.73, "px": 412},
        ...
      }
    }

Usage:
    # If you have the NLCD impervious raster locally already:
    python3 scripts/fetch_nlcd_impervious.py --raster /path/to/nlcd_2021_impervious.tif

    # Or point at any HTTP-readable COG / GeoTIFF (rasterio supports /vsicurl):
    python3 scripts/fetch_nlcd_impervious.py --raster-url https://.../nlcd_impervious_de.tif

    # Dry run shows what would be written without writing:
    python3 scripts/fetch_nlcd_impervious.py --raster ./nlcd.tif --dry-run

Requires: rasterio, shapely, numpy   (pip install rasterio shapely numpy)

Where to get the raster:
  - Full CONUS (1.4 GB ZIP): https://www.mrlc.gov/data/nlcd-2021-percent-developed-imperviousness-conus
  - Or use NLCD 2021 ImageServer:
        https://www.mrlc.gov/geoserver/mrlc_display/NLCD_2021_Impervious_L48/wms
  - Or extract a Delaware-clipped subset using `gdal_translate -projwin ...`
    against the CONUS raster.

Note on precip: this script does NOT cover extreme precipitation. The
sub-county precip story in Delaware is dominated by drainage and impervious
runoff rather than rainfall depth (rainfall varies <10% across the state vs
year-to-year swings of 30%+). If a future fetcher targets precip, use NOAA
Atlas 14 100-yr/24-hr depth grids, OR pair the NLCD imperviousness output
here with the FEMA NFHL flood layer for an honest "flood exposure" overlay.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
    import rasterio
    from rasterio.mask import mask as rio_mask
    from rasterio.warp import transform_geom
except ImportError:
    sys.exit(
        "Missing dependencies. Install with:\n"
        "    pip install rasterio numpy shapely\n"
        "(rasterio bundles GDAL, so no separate GDAL install is needed on "
        "most platforms.)"
    )


ROOT = Path(__file__).parent.parent
BG_FILE = ROOT / "de_blockgroups.geojson"
OUT_FILE = ROOT / "bg_heat_index.json"

# NLCD impervious raster encodes percent (0-100) as uint8. 127 is the
# canonical no-data value used in the 2021 product.
NLCD_NODATA = 127


def load_block_groups(path: Path) -> list[dict]:
    with path.open() as f:
        gj = json.load(f)
    return gj["features"]


def zonal_mean_impervious(raster_path: str, features: list[dict]) -> dict[str, dict]:
    """Compute mean impervious % per BG.

    For each block group polygon: reproject to the raster CRS, mask the
    raster, drop nodata pixels, return the mean. `px` is the number of
    valid pixels that contributed to the mean — small counts (single
    digits) indicate the BG fell mostly on water or nodata, treat with
    skepticism.
    """
    out: dict[str, dict] = {}
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        for feat in features:
            geoid = feat["properties"]["GEOID"]
            geom = feat["geometry"]
            # Reproject the BG geometry into the raster's CRS (NLCD is
            # Albers Equal Area CONUS; BG geojson is WGS84).
            geom_proj = transform_geom("EPSG:4326", raster_crs, geom)
            try:
                arr, _ = rio_mask(src, [geom_proj], crop=True, filled=False)
            except ValueError:
                # BG entirely outside the raster footprint.
                out[geoid] = {"impervious_pct_mean": None, "lst_proxy_idx": None, "px": 0}
                continue
            data = arr[0]
            valid = (~data.mask) & (data.data != NLCD_NODATA)
            n_px = int(valid.sum())
            if n_px == 0:
                out[geoid] = {"impervious_pct_mean": None, "lst_proxy_idx": None, "px": 0}
                continue
            mean_pct = float(data.data[valid].mean())
            # Map 0-100% impervious → 0-10 heat index. Linear is the
            # honest first cut; published LST relationships are roughly
            # linear in this range with a slight upward bend above ~70%.
            idx = max(0.0, min(10.0, mean_pct / 10.0))
            out[geoid] = {
                "impervious_pct_mean": round(mean_pct, 1),
                "lst_proxy_idx": round(idx, 2),
                "px": n_px,
            }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--raster", help="Local path to NLCD impervious GeoTIFF")
    grp.add_argument("--raster-url", help="HTTP(S) URL to a COG/GeoTIFF; rasterio reads via /vsicurl")
    ap.add_argument("--dry-run", action="store_true", help="Compute but do not write")
    ap.add_argument("--out", default=str(OUT_FILE), help=f"Output JSON path (default: {OUT_FILE})")
    args = ap.parse_args()

    raster_path = args.raster if args.raster else f"/vsicurl/{args.raster_url}"

    if not BG_FILE.exists():
        sys.exit(f"Missing {BG_FILE}. Run from the repo root.")

    features = load_block_groups(BG_FILE)
    print(f"Computing impervious zonal mean for {len(features)} block groups…", file=sys.stderr)

    bg_stats = zonal_mean_impervious(raster_path, features)

    n_with_data = sum(1 for v in bg_stats.values() if v["impervious_pct_mean"] is not None)
    print(f"  {n_with_data}/{len(features)} BGs have valid pixels", file=sys.stderr)

    payload = {
        "_meta": {
            "source": "USGS NLCD 2021 Percent Developed Imperviousness",
            "url": "https://www.mrlc.gov/data/nlcd-2021-percent-developed-imperviousness-conus",
            "resolution_m": 30,
            "method": (
                "Mean impervious % per Census 2020 block group, computed "
                "via rasterio.mask over NLCD 30m raster. Used as a proxy "
                "for summer Land Surface Temperature (urban heat island)."
            ),
            "scaling": "lst_proxy_idx = clamp(impervious_pct_mean / 10, 0, 10)",
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_block_groups": len(features),
            "n_with_data": n_with_data,
            "raster_input": args.raster or args.raster_url,
        },
        "block_groups": bg_stats,
    }

    if args.dry_run:
        print(json.dumps(payload["_meta"], indent=2))
        sample = dict(list(bg_stats.items())[:3])
        print("Sample BGs:", json.dumps(sample, indent=2))
        return 0

    Path(args.out).write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
