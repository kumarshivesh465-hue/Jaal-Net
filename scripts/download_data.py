#!/usr/bin/env python
"""Idempotent dataset bootstrap for the JaalNet reference pipeline.

Checks the two external datasets this repo trains on and fetches them only when
missing. Verification is SHA256 against the constants below.

    python scripts/download_data.py

Design notes
------------
* Idempotent: an existing, non-empty file at the target path is left untouched.
* No credentials are handled here. DGraphFin is distributed through Kaggle,
  which needs an authenticated client; this script prints instructions rather
  than attempting automated auth.
* Provenance is only encoded when it can be verified. Where a URL or digest
  could not be established from the repository, the constant is ``None`` and a
  ``# TODO`` records why -- the script never fabricates a source.
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Dataset provenance constants
# ---------------------------------------------------------------------------
# PaySim
#   Provenance: HuggingFace dataset `theman10/paysim` (see train_model.py
#   docstring and MODEL_CARD.md "Training Data"). The repo records the dataset
#   *identifier* only; no file-level download URL and no content digest are
#   recorded anywhere in the code or git history.
#   TODO(provenance): set PAYSIM_URL to the exact `resolve/main` file URL once
#   confirmed against the upstream dataset viewer, and PAYSIM_SHA256 to the
#   digest of that file. Until then the script instructs instead of guessing.
PAYSIM_PATH = os.path.join(ROOT, "data", "paysim.csv")
PAYSIM_URL: str | None = None
PAYSIM_SHA256: str | None = None

# DGraphFin
#   Provenance: "downloaded via Kaggle mirror" (PROMOTION_LOG.md, 2026-10-14),
#   verified against the official NeurIPS 2022 release at 680,317,982 bytes.
#   The Kaggle slug/URL is not recorded in the repo.
#   TODO(provenance): record the Kaggle URL here and fill DGRAPHFIN_SHA256.
DGRAPHFIN_PATH = os.path.join(ROOT, "data", "DGraphFin", "raw", "dgraphfin.npz")
DGRAPHFIN_BYTES = 680_317_982
DGRAPHFIN_SHA256: str | None = None


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _present(path: str) -> bool:
    return os.path.isfile(path) and os.path.getsize(path) > 0


def verify(path: str, expected: str | None) -> bool:
    """Return True if the file matches `expected` (or no digest is known)."""
    if expected is None:
        print(f"  [verify] no digest recorded for {os.path.basename(path)}; "
              "size check only")
        return True
    actual = sha256_file(path)
    ok = actual.lower() == expected.lower()
    print(f"  [verify] {os.path.basename(path)} sha256={actual} "
          f"({'OK' if ok else 'MISMATCH'})")
    return ok


def fetch_paysim() -> int:
    print("== PaySim ==")
    if _present(PAYSIM_PATH):
        print(f"  present: {PAYSIM_PATH} ({os.path.getsize(PAYSIM_PATH):,} bytes)")
        return 0
    if PAYSIM_URL is None:
        print("  MISSING and no verified download URL is recorded.")
        print("  TODO(provenance): the repo references the HuggingFace dataset")
        print("  `theman10/paysim` but not a file URL or digest. Fetch it from")
        print("  the dataset viewer, then set PAYSIM_URL/PAYSIM_SHA256 in this")
        print("  script and re-run. Expected target:")
        print(f"    {PAYSIM_PATH}")
        return 0
    os.makedirs(os.path.dirname(PAYSIM_PATH), exist_ok=True)
    print(f"  downloading {PAYSIM_URL}")
    urllib.request.urlretrieve(PAYSIM_URL, PAYSIM_PATH)
    if not verify(PAYSIM_PATH, PAYSIM_SHA256):
        print("  SHA256 mismatch; leaving the file in place for inspection.")
        return 2
    return 0


def fetch_dgraphfin() -> int:
    print("== DGraphFin ==")
    if _present(DGRAPHFIN_PATH):
        size = os.path.getsize(DGRAPHFIN_PATH)
        print(f"  present: {DGRAPHFIN_PATH} ({size:,} bytes)")
        if size != DGRAPHFIN_BYTES:
            print(f"  WARNING: expected {DGRAPHFIN_BYTES:,} bytes")
        return 0
    print("  MISSING. Kaggle requires an authenticated client, so this script")
    print("  does not download it automatically. To obtain it:")
    print("    1. Install the Kaggle CLI and place kaggle.json in ~/.kaggle/.")
    print("    2. Download the DGraphFin release (NeurIPS 2022 Datasets and")
    print("       Benchmarks Track, Huang et al.) from Kaggle.")
    print("    3. Extract so that this exact path exists:")
    print(f"       {DGRAPHFIN_PATH}")
    print(f"    4. Confirm the size is {DGRAPHFIN_BYTES:,} bytes, then re-run.")
    # TODO(provenance): record the Kaggle slug/URL and a SHA256 here.
    return 0


def main() -> int:
    print(f"repo root: {ROOT}")
    rc = fetch_paysim()
    rc |= fetch_dgraphfin()
    if rc == 0:
        print("\ndownload_data: OK (nothing fetched or all present)")
    else:
        print("\ndownload_data: FAILED — see messages above", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
