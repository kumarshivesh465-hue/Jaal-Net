#!/usr/bin/env bash
# Full local verification gate. Any failure aborts (set -e).
set -euo pipefail

cd "$(dirname "$0")/.."

./.venv/Scripts/python -m py_compile inference.py backend.py \
  config.py train_upi_model.py train_dgraph.py \
  train_dgraph_tgn.py train_model.py synth/upi_mule_generator.py
./.venv/Scripts/python -m pytest tests/ -m "not integration" -q
./.venv/Scripts/python scripts/check_metrics.py
./.venv/Scripts/python -c "import app"
echo "VERIFY: ALL GREEN"
