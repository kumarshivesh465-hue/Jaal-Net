#!/usr/bin/env bash
# Install a pre-commit hook that runs the fast (non-integration) test suite.
# Run once per clone:  bash scripts/install_hooks.sh
set -euo pipefail

cd "$(dirname "$0")/.."
HOOK_DIR="$(git rev-parse --git-dir)/hooks"
HOOK="$HOOK_DIR/pre-commit"

mkdir -p "$HOOK_DIR"
cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# Installed by scripts/install_hooks.sh — fail the commit if the fast suite fails.
./.venv/Scripts/python -m pytest tests/ -m "not integration" -q \
  --tb=line -x || exit 1
EOF
chmod +x "$HOOK"

echo "installed $HOOK"
