"""
Central configuration. No magic numbers anywhere else in the codebase.
Matches CONTRACTS.md section 3 exactly.
"""

import os

# ----------------------------------------------------------------------------
# Thresholds (must satisfy MONITOR < STEPUP < BLOCK)
# ----------------------------------------------------------------------------
THRESHOLD_MONITOR: int = 30
THRESHOLD_STEPUP: int = 70
THRESHOLD_BLOCK: int = 90

# ----------------------------------------------------------------------------
# Stream
# ----------------------------------------------------------------------------
MAX_STREAM_SIZE: int = 200
STREAM_BATCH_SIZE: int = 3
REFRESH_INTERVAL_MS: int = 2000

# ----------------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------------
MODEL_VERSION: str = "TGAT+SAGE-v1.2"
MODEL_PATH: str = "models/tgat_sage_v1.2.onnx"
MAX_HOPS: int = 2
MAX_NEIGHBORS_PER_NODE: int = 50

# PaySim-trained model contract (trained 2026-10-12)
# The ONNX model has 6 inputs: sender_embedding(64), receiver_embedding(64),
# amount, origin_balance_error, dest_balance_error, tx_type(int 0-4).
# Output is a logit; consumers apply sigmoid.
ARTIFACTS_DIR: str = "artifacts"
PAYSIM_EMB_DIM: int = 64
PAYSIM_TXN_TYPES: list[str] = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]

# ----------------------------------------------------------------------------
# UPI-shaped model contract (trained on the synthetic dataset, 2026-10-15)
# ----------------------------------------------------------------------------
# The UPI edge head has 6 inputs: sender_embedding(32), receiver_embedding(32),
# amount, velocity_10min, device_change, ip_risk. Output is 2 logits
# [legitimate, fraud]; consumers apply softmax.
# It takes precedence over the PaySim head whenever its file exists — see
# inference.load_model for the documented precedence.
UPI_EMB_DIM: int = 32
UPI_MODEL_PATH: str = os.path.join(ARTIFACTS_DIR, "upi_edge_model.onnx")
UPI_EMBEDDINGS_PATH: str = os.path.join(ARTIFACTS_DIR, "upi_node_embeddings.npz")

# EMB_DIM is the embedding width of the *active* head: 32 for the UPI model,
# 64 for the PaySim model. Resolved once here so that everything sizing a
# hash-fallback vector from it (backend._resolve_embedding, eval_transfer) is
# guaranteed to match the model that will actually be loaded.
EMB_DIM: int = UPI_EMB_DIM if os.path.exists(UPI_MODEL_PATH) else PAYSIM_EMB_DIM

# Scaler parameters saved from training (artifacts/scaler.json).
# node_mean/node_scale: per-column mean/std of the 6-dim node feature vec.
# tab_mean/tab_scale: mean/std of the 4 tabular edge features used by the
#   logistic baseline: amount, origin_balance_error, dest_balance_error, tx_type_int.
#   The GNN uses these same scalings for amount + the two balance-error features.
_SCALER_RAW: dict = {}


def _load_scaler() -> dict:
    """Lazy-load scaler.json from the artifacts directory."""
    global _SCALER_RAW
    if _SCALER_RAW:
        return _SCALER_RAW
    import json
    import os
    try:
        _SCALER_RAW = json.loads(
            open(os.path.join(ARTIFACTS_DIR, "scaler.json"), encoding="utf-8").read()
        )
    except Exception:  # missing scaler is fine here; SCALER() raises later
        _SCALER_RAW = {}
    return _SCALER_RAW


def SCALER() -> dict:
    """Return the scaler dict. Raises RuntimeError if artifacts are missing."""
    s = _load_scaler()
    if not s:
        raise RuntimeError(
            "Scaler not found. Run train_model.py to produce artifacts/scaler.json."
        )
    return s


def _get_scaler_field(field: str) -> list[float]:
    """Return one scaler array field, or [] if it isn't there."""
    s = _load_scaler()
    return s.get(field, [])


# pulled out at import time so inference/backend can just read them instead
# of calling SCALER() and catching RuntimeError. Empty lists pre-training.
SCALER_NODE_MEAN: list[float] = _get_scaler_field("node_mean")
SCALER_NODE_SCALE: list[float] = _get_scaler_field("node_scale")
SCALER_TAB_MEAN: list[float] = _get_scaler_field("tab_mean")
SCALER_TAB_SCALE: list[float] = _get_scaler_field("tab_scale")

# ----------------------------------------------------------------------------
# Rings (mock)
# ----------------------------------------------------------------------------
RING_IDS: list[str] = ["RING-001", "RING-002", "RING-003"]

# ----------------------------------------------------------------------------
# States
# ----------------------------------------------------------------------------
INDIAN_STATE_CODES: list[str] = [
    "MH", "KA", "TN", "DL", "UP", "GJ", "WB", "RJ", "KL", "TS",
]

# ----------------------------------------------------------------------------
# Colors (mirrors styles.py)
# ----------------------------------------------------------------------------
COLOR_SAFE: str = "#10B981"
COLOR_MONITOR: str = "#F59E0B"
COLOR_STEPUP: str = "#F97316"
COLOR_BLOCK: str = "#EF4444"
COLOR_MULE_RING: str = "#EC4899"
COLOR_ACCENT: str = "#8B5CF6"
COLOR_LAYERING: str = "#A855F7"
COLOR_CIRCULAR: str = "#06B6D4"
COLOR_EDGE_NORMAL: str = "#374151"
COLOR_BG_PRIMARY: str = "#0A0E17"
COLOR_BG_SECONDARY: str = "#111827"
COLOR_TEXT_MUTED: str = "#6B7280"

# ----------------------------------------------------------------------------
# Action labels (must match SCHEMA.md Action Enum)
# ----------------------------------------------------------------------------
ACTION_ALLOW: str = "ALLOW"
ACTION_MONITOR: str = "MONITOR"
ACTION_STEPUP: str = "STEP_UP"
ACTION_BLOCK: str = "BLOCK"

ACTIONS: list[str] = [ACTION_ALLOW, ACTION_MONITOR, ACTION_STEPUP, ACTION_BLOCK]

# ----------------------------------------------------------------------------
# Edge types (must match SCHEMA.md section 4)
# ----------------------------------------------------------------------------
EDGE_NORMAL: str = "normal"
EDGE_RING: str = "ring"
EDGE_LAYERING: str = "layering"
EDGE_CIRCULAR: str = "circular"

EDGE_TYPES: list[str] = [EDGE_NORMAL, EDGE_RING, EDGE_LAYERING, EDGE_CIRCULAR]

# ----------------------------------------------------------------------------
# Exasol connection (password comes from the EXASOL_PASSWORD env var)
# ----------------------------------------------------------------------------
# set these in .env, never commit real credentials.
# .env is read here (no external dependency) so that `streamlit run app.py` and
# the tests connect to the real database without an export step; a value that
# is already in the process environment always wins.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str = os.path.join(_PROJECT_ROOT, ".env")) -> None:
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(
                    key.strip(), value.strip().strip('"').strip("'")
                )
    except OSError:
        return


_load_dotenv()

EXASOL_DSN: str = os.environ.get("EXASOL_DSN", "localhost:8563")
EXASOL_USER: str = os.environ.get("EXASOL_USER", "sys")
EXASOL_PASSWORD: str = os.environ.get("EXASOL_PASSWORD", "")
EXASOL_SCHEMA: str = os.environ.get("EXASOL_SCHEMA", "FRAUD")

# ----------------------------------------------------------------------------
# Backend
# ----------------------------------------------------------------------------
BACKEND_HOST: str = "0.0.0.0"
BACKEND_PORT: int = 8000
BACKEND_URL: str = "http://localhost:8000"

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
LOG_LEVEL: str = "INFO"
