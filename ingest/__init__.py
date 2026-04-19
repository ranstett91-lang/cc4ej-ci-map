"""cc4ej-ci-map ingest pipeline.

Module layout:
    manifest.yaml         — source + mirror registry (edit this, not code)
    snapshots.py          — download-with-fallback, SHA-256, lock-file writer
    verify.py             — checks snapshots/MANIFEST.lock.yaml matches data_raw/

See docs/INGEST_ARCHITECTURE.md for the full design.
"""
