# Full local verification gate (PowerShell). Any failure aborts.
$ErrorActionPreference = 'Stop'

Set-Location (Split-Path -Parent $PSScriptRoot)

.\.venv\Scripts\python.exe -m py_compile inference.py backend.py `
  config.py train_upi_model.py train_dgraph.py `
  train_dgraph_tgn.py train_model.py synth/upi_mule_generator.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.\.venv\Scripts\python.exe scripts/check_metrics.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

.\.venv\Scripts\python.exe -c "import app"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output "VERIFY: ALL GREEN"
