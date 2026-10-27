<#
.SYNOPSIS
    One-command demo: check prerequisites, fill in missing data/artifacts, start
    the API and the analyst console, print the URLs, and stop both on Ctrl-C.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/demo.ps1

.NOTES
    Same behaviour as scripts/demo.sh. Nothing trains unless an artifact is
    actually missing, and no database is required: without Exasol the data
    layer falls back to mock rows.
#>
[CmdletBinding()]
param(
    [int]$BackendPort = $(if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }),
    [int]$FrontendPort = $(if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 8501 }),
    [int]$HealthTimeout = 90
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    [ok] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Die($msg)  { Write-Host "`nERROR: $msg`n" -ForegroundColor Red; exit 1 }

function Find-Python {
    foreach ($candidate in @("$PWD\.venv\Scripts\python.exe", ".\.venv\Scripts\python.exe", "python")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

function Test-PortFree([int]$port) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { $listener.Stop() }
    }
}

function Wait-Url([string]$url, [int]$seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        try {
            $null = Invoke-WebRequest -Uri $url -TimeoutSec 1 -UseBasicParsing
            return $true
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

$backend = $null
$frontend = $null
$logDir = Join-Path $PWD "logs"
$backendLog = Join-Path $logDir "demo-backend.log"
$frontendLog = Join-Path $logDir "demo-frontend.log"

function Stop-Demo {
    Step "Stopping servers"
    foreach ($proc in @($frontend, $backend)) {
        if ($proc -and -not $proc.HasExited) {
            # /T also reaches any child the process spawned
            & taskkill /F /T /PID $proc.Id 2>&1 | Out-Null
            Ok "stopped pid $($proc.Id)"
        }
    }
}

try {
    # ---------------------------------------------------------------- 1. prereqs
    Step "Checking prerequisites"

    $py = Find-Python
    if (-not $py) {
        Die "No Python found. Create the venv first: python -m venv .venv; .venv\Scripts\pip install -r requirements.lock"
    }

    & $py -c "import importlib.util,sys; missing=[m for m in ('fastapi','uvicorn','streamlit','onnxruntime','numpy','pandas') if importlib.util.find_spec(m) is None]; sys.exit(1 if missing else 0)"
    if ($LASTEXITCODE -ne 0) {
        Die "Dependencies missing. Run: .venv\Scripts\python -m pip install -r requirements.txt"
    }
    Ok "python: $(& $py --version) ($py)"

    foreach ($port in @($BackendPort, $FrontendPort)) {
        if (-not (Test-PortFree $port)) {
            Die "Port $port is already in use. Stop the old process or set `$env:BACKEND_PORT / `$env:FRONTEND_PORT."
        }
    }
    Ok "ports $BackendPort and $FrontendPort are free"

    # ------------------------------------------------------- 2. data + artifacts
    Step "Checking data and model artifacts"

    if (Test-Path "synth\out\transactions.csv") {
        Ok "synthetic UPI data present (synth/out/)"
    } else {
        Warn "synth/out/ missing - generating 100,000 transactions (~20s)"
        & $py synth/upi_mule_generator.py --seed 42 --out synth/out
        if ($LASTEXITCODE -ne 0) { Die "Data generation failed" }
    }

    if ((Test-Path "artifacts\upi_edge_model.onnx") -and (Test-Path "artifacts\upi_node_embeddings.npz")) {
        Ok "UPI head present (artifacts/upi_edge_model.onnx)"
    } else {
        Warn "UPI artifacts missing - training the head (~100s, CPU)"
        & $py train_upi_model.py
        if ($LASTEXITCODE -ne 0) { Die "Training failed" }
    }

    # ------------------------------------------------------------- 3. database
    Step "Checking Exasol (optional)"

    if (-not $env:EXASOL_PASSWORD -and (Test-Path ".env")) {
        $line = Get-Content ".env" | Where-Object { $_ -match '^EXASOL_PASSWORD=' } | Select-Object -Last 1
        if ($line) { $env:EXASOL_PASSWORD = $line -replace '^EXASOL_PASSWORD=', '' }
    }

    if (-not $env:EXASOL_PASSWORD) {
        Warn "EXASOL_PASSWORD not set - the data layer will use mock rows"
    } elseif ((Get-Command docker -ErrorAction SilentlyContinue) -and
              (docker ps --format '{{.Names}}' 2>$null | Select-String -SimpleMatch "exasol")) {
        Ok "exasol container is running"
    } else {
        Warn "exasol container is not running - falling back to mock rows"
        Warn "to use it: docker compose up -d exasol; $py scripts/init_exasol.py"
    }

    # ----------------------------------------------------------- 4. start API
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    Step "Starting the API on http://localhost:$BackendPort"

    $backend = Start-Process -FilePath $py `
        -ArgumentList @("-m", "uvicorn", "backend:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
        -RedirectStandardOutput $backendLog -RedirectStandardError "$backendLog.err" `
        -NoNewWindow -PassThru

    if (-not (Wait-Url "http://127.0.0.1:$BackendPort/health" $HealthTimeout)) {
        Get-Content $backendLog -Tail 20 -ErrorAction SilentlyContinue
        Die "The API did not become healthy in ${HealthTimeout}s (see $backendLog)"
    }
    $contract = (Invoke-RestMethod "http://127.0.0.1:$BackendPort/health").model_contract
    Ok "API healthy (pid $($backend.Id), model contract: $contract)"

    # ------------------------------------------------------- 5. start console
    Step "Starting the analyst console on http://localhost:$FrontendPort"

    $frontend = Start-Process -FilePath $py `
        -ArgumentList @("-m", "streamlit", "run", "app.py", "--server.port", "$FrontendPort",
                        "--server.headless", "true", "--browser.gatherUsageStats", "false") `
        -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" `
        -NoNewWindow -PassThru

    if (-not (Wait-Url "http://127.0.0.1:$FrontendPort/_stcore/health" $HealthTimeout)) {
        Get-Content $frontendLog -Tail 20 -ErrorAction SilentlyContinue
        Die "Streamlit did not come up in ${HealthTimeout}s (see $frontendLog)"
    }
    Ok "console up (pid $($frontend.Id))"

    # ------------------------------------------------------------- 6. hand over
    Write-Host @"

  UPI Mule Fraud Detection - running
  ----------------------------------
  Analyst console   http://localhost:$FrontendPort
  API health        http://localhost:$BackendPort/health
  Score a txn       curl -X POST http://localhost:$BackendPort/score ``
                         -H "Content-Type: application/json" -d @test_txn.json

  Logs              $backendLog
                    $frontendLog
  Stop              Ctrl-C (both servers are killed)

"@ -ForegroundColor Gray

    while (-not $backend.HasExited -and -not $frontend.HasExited) {
        Start-Sleep -Seconds 1
        $backend.Refresh()
        $frontend.Refresh()
    }

    if ($backend.HasExited) {
        Warn "the API stopped - last lines of ${backendLog}"
    } else {
        Warn "the console stopped - last lines of ${frontendLog}"
    }
    Get-Content $backendLog -Tail 10 -ErrorAction SilentlyContinue
    Get-Content $frontendLog -Tail 10 -ErrorAction SilentlyContinue
    exit 1
}
finally {
    Stop-Demo
}
