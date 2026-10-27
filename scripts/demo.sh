#!/usr/bin/env bash
# One-command demo: check prerequisites, fill in missing data/artifacts, start
# the API and the analyst console, print the URLs, and kill both on Ctrl-C.
#
#   bash scripts/demo.sh          # or: make demo
#
# Nothing here trains unless an artifact is actually missing, and it never
# requires a database: without Exasol the data layer falls back to mock rows.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"
LOG_DIR="$ROOT/logs"
BACKEND_LOG="$LOG_DIR/demo-backend.log"
FRONTEND_LOG="$LOG_DIR/demo-frontend.log"

BACKEND_PID=""
FRONTEND_PID=""

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
step()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()    { printf '    \033[32m✓\033[0m %s\n' "$*"; }
warn()  { printf '    \033[33m!\033[0m %s\n' "$*"; }
die()   { printf '\n\033[1;31mERROR:\033[0m %s\n\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Cleanup: stop both servers, whatever happened
# ---------------------------------------------------------------------------
# Liveness is checked on the listening port, not with `kill -0`: from Git Bash
# kill -0 reports "no such process" for a native python.exe that is very much
# alive, which is exactly the wrong answer when deciding to stop it.
port_open() {
    "$PY" - "$1" <<'EOF'
import socket, sys
s = socket.socket()
s.settimeout(0.5)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
EOF
}

# A plain `kill` from Git Bash does not reach a native python.exe, so ask
# politely, then use the Windows force paths.
stop_pid() {
    local pid="$1" name="$2" port="$3"
    [ -n "$pid" ] || return 0

    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5 6; do
        port_open "$port" || { ok "stopped $name (pid $pid)"; return 0; }
        sleep 0.5
    done

    kill -9 "$pid" 2>/dev/null || true
    kill -f "$pid" 2>/dev/null || true   # msys: TerminateProcess
    if command -v taskkill >/dev/null 2>&1; then
        taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
    fi

    for _ in 1 2 3 4 5 6; do
        port_open "$port" || { ok "stopped $name (pid $pid)"; return 0; }
        sleep 0.5
    done
    warn "could not stop $name (pid $pid); port $port is still open"
}

cleanup() {
    local code=$?
    trap - INT TERM EXIT
    printf '\n'
    step "Stopping servers"
    stop_pid "$FRONTEND_PID" "console" "$FRONTEND_PORT"
    stop_pid "$BACKEND_PID" "API" "$BACKEND_PORT"
    exit "$code"
}
trap cleanup INT TERM EXIT

# ---------------------------------------------------------------------------
# 1. Prerequisites
# ---------------------------------------------------------------------------
step "Checking prerequisites"

for candidate in "./.venv/Scripts/python.exe" "./.venv/bin/python" "python3" "python"; do
    if [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done
[ -n "${PY:-}" ] || die "No Python found. Create the venv first: python -m venv .venv && pip install -r requirements.lock"

"$PY" - <<'EOF' || die "Dependencies missing. Run: .venv/Scripts/python -m pip install -r requirements.txt"
import importlib.util, sys
required = ["fastapi", "uvicorn", "streamlit", "onnxruntime", "numpy", "pandas"]
missing = [m for m in required if importlib.util.find_spec(m) is None]
if missing:
    print("missing:", ", ".join(missing))
    sys.exit(1)
EOF
ok "python: $("$PY" --version 2>&1) ($PY)"

port_free() {
    "$PY" - "$1" <<'EOF'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
EOF
}
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    port_free "$port" || die "Port $port is already in use. Stop the old process or set BACKEND_PORT/FRONTEND_PORT."
done
ok "ports $BACKEND_PORT and $FRONTEND_PORT are free"

# ---------------------------------------------------------------------------
# 2. Data and model artifacts (only generated when missing)
# ---------------------------------------------------------------------------
step "Checking data and model artifacts"

if [ -f "synth/out/transactions.csv" ]; then
    ok "synthetic UPI data present (synth/out/)"
else
    warn "synth/out/ missing — generating 100,000 transactions (~20s)"
    "$PY" synth/upi_mule_generator.py --seed 42 --out synth/out
fi

if [ -f "artifacts/upi_edge_model.onnx" ] && [ -f "artifacts/upi_node_embeddings.npz" ]; then
    ok "UPI head present (artifacts/upi_edge_model.onnx)"
else
    warn "UPI artifacts missing — training the head (~100s, CPU)"
    "$PY" train_upi_model.py
fi

# ---------------------------------------------------------------------------
# 3. Database: optional, reported honestly
# ---------------------------------------------------------------------------
step "Checking Exasol (optional)"

if [ -z "${EXASOL_PASSWORD:-}" ] && [ -f ".env" ]; then
    EXASOL_PASSWORD="$(sed -n 's/^EXASOL_PASSWORD=//p' .env | tail -1)"
    export EXASOL_PASSWORD
fi

if [ -z "${EXASOL_PASSWORD:-}" ]; then
    warn "EXASOL_PASSWORD not set — the data layer will use mock rows"
elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx exasol; then
    ok "exasol container is running"
else
    warn "exasol container is not running — falling back to mock rows"
    warn "to use it: docker compose up -d exasol && $PY scripts/init_exasol.py"
fi

# ---------------------------------------------------------------------------
# 4. Start the API
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"
step "Starting the API on http://localhost:$BACKEND_PORT"

"$PY" -m uvicorn backend:app --host 127.0.0.1 --port "$BACKEND_PORT" \
    > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

ready=""
for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        tail -20 "$BACKEND_LOG" >&2
        die "The API exited during startup (see $BACKEND_LOG)"
    fi
    if "$PY" -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$BACKEND_PORT/health', timeout=1)" 2>/dev/null; then
        ready="yes"
        break
    fi
    sleep 1
done
[ -n "$ready" ] || { tail -20 "$BACKEND_LOG" >&2; die "The API did not become healthy in ${HEALTH_TIMEOUT}s"; }

contract="$("$PY" -c "
import json, urllib.request
print(json.load(urllib.request.urlopen('http://127.0.0.1:$BACKEND_PORT/health'))['model_contract'])
" 2>/dev/null || echo unknown)"
ok "API healthy (pid $BACKEND_PID, model contract: $contract)"

# ---------------------------------------------------------------------------
# 5. Start the console
# ---------------------------------------------------------------------------
step "Starting the analyst console on http://localhost:$FRONTEND_PORT"

"$PY" -m streamlit run app.py --server.port "$FRONTEND_PORT" \
    --server.headless true --browser.gatherUsageStats false \
    > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

ready=""
for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        tail -20 "$FRONTEND_LOG" >&2
        die "Streamlit exited during startup (see $FRONTEND_LOG)"
    fi
    if "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$FRONTEND_PORT/_stcore/health', timeout=1)" 2>/dev/null; then
        ready="yes"
        break
    fi
    sleep 1
done
[ -n "$ready" ] || { tail -20 "$FRONTEND_LOG" >&2; die "Streamlit did not come up in ${HEALTH_TIMEOUT}s"; }
ok "console up (pid $FRONTEND_PID)"

# ---------------------------------------------------------------------------
# 6. Hand over
# ---------------------------------------------------------------------------
cat <<EOF

  UPI Mule Fraud Detection — running
  ----------------------------------
  Analyst console   http://localhost:$FRONTEND_PORT
  API health        http://localhost:$BACKEND_PORT/health
  Score a txn       curl -X POST http://localhost:$BACKEND_PORT/score \\
                         -H "Content-Type: application/json" -d @test_txn.json

  Logs              $BACKEND_LOG
                    $FRONTEND_LOG
  Stop              Ctrl-C (both servers are killed)

EOF

# Wait on the servers so Ctrl-C reaches the trap. If either dies on its own,
# come back and say which, instead of pretending the demo is still up.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    warn "the API stopped — last lines of $BACKEND_LOG:"
else
    warn "the console stopped — last lines of $FRONTEND_LOG:"
fi
tail -10 "$BACKEND_LOG" "$FRONTEND_LOG" 2>/dev/null || true
exit 1
