"""Model loading and scoring. CONTRACTS.md section 7.

Two heads, one ScoreResult out of both, plus a mock fallback:
  - UPI head: artifacts/upi_edge_model.onnx. Preferred whenever the file
    exists (precedence documented on load_model). Trained by
    train_upi_model.py on the synthetic UPI dataset. inputs:
    sender_embedding(32), receiver_embedding(32), amount, velocity_10min,
    device_change, ip_risk; output "score" is 2 logits
    [legitimate, fraud] -- read with softmax.
  - PaySim head: config.MODEL_PATH. Used when the UPI file is absent.
  - Mock: model missing -> deterministic heuristic so the rest of the app
    still works during development.

The active contract is detected from the loaded session's ONNX input names
(_contract_is_upi), never assumed, and the embedding store follows the active
head: 32-dim masked UPI handles, or 64-dim PaySim accounts. Accounts outside
the store fall back to a hash embedding, so scoring never fails.

PaySim contract (trained 2026-10-12):
  inputs: sender_embedding(64), receiver_embedding(64), amount,
          origin_balance_error, dest_balance_error, tx_type(int 0-4)
  output: "score" logit, not a probability — consumers apply sigmoid.
  Embeddings are looked up from artifacts/ and never recomputed from the
  account string. The two heads do not scale alike: PaySim re-uses
  artifacts/scaler.json, while the UPI head takes log1p(amount) and
  log1p(velocity_10min) unscaled plus raw 0-1 device/ip flags, exactly as
  train_upi_model.py fed them.
"""

import json
import logging
import math
import os
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import config

logger = logging.getLogger(__name__)

# Module-level cache so load_model is idempotent
_MODEL_CACHE: dict[str, Any] = {}

# Account embedding store: loaded lazily, shared across calls
_EMBEDDING_STORE: dict[str, np.ndarray] | None = None

# Serving temperature for the UPI head. Loaded lazily from
# artifacts/calibration/upi_edge_model_temperature.json; applied only when the
# fitted value is far enough from 1.0 to matter (see score_transaction).
_SERVING_TEMPERATURE: float | None = None
_SERVING_TEMPERATURE_APPLIED: bool = False
_COLDSTART_MODEL: Any = None


class CatBoostColdStartWrapper:
    """Standardized wrapper executing the exported CatBoost ONNX cold-start model with predict_proba API."""
    def __init__(self, kind: str, model_obj: Any):
        self.kind = kind
        self.model_obj = model_obj

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.kind == "onnx":
            outs = self.model_obj.run(None, {"features": np.asarray(X, dtype=np.float32)})
            probs = outs[1]
            if isinstance(probs, list) and len(probs) > 0 and isinstance(probs[0], dict):
                res = []
                for row_dict in probs:
                    p1 = float(row_dict.get(1, 0.0))
                    p0 = float(row_dict.get(0, 1.0 - p1))
                    res.append([p0, p1])
                return np.array(res, dtype=np.float32)
            elif hasattr(probs, "shape") and probs.ndim == 2:
                return np.asarray(probs, dtype=np.float32)
            else:
                p1 = float(outs[0][0])
                return np.array([[1.0 - p1, p1]], dtype=np.float32)
        return self.model_obj.predict_proba(X)


def _get_coldstart_model() -> Any:
    """Return cached CatBoost cold-start classifier (ONNX Runtime session preferred, CatBoost native fallback)."""
    global _COLDSTART_MODEL
    if _COLDSTART_MODEL is None:
        onnx_path = os.path.join(config.ARTIFACTS_DIR, "catboost_coldstart.onnx")
        if os.path.exists(onnx_path):
            try:
                import onnxruntime as ort

                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                sess = ort.InferenceSession(onnx_path, sess_options=opts, providers=["CPUExecutionProvider"])
                _COLDSTART_MODEL = CatBoostColdStartWrapper("onnx", sess)
                logger.info("Loaded CatBoost cold-start ONNX model from %s", onnx_path)
                return _COLDSTART_MODEL
            except Exception as e:
                logger.warning("Could not load CatBoost cold-start ONNX model: %s", e)

        cbm_path = os.path.join(config.ARTIFACTS_DIR, "catboost_coldstart.cbm")
        if os.path.exists(cbm_path):
            try:
                from catboost import CatBoostClassifier

                cb = CatBoostClassifier()
                cb.load_model(cbm_path)
                _COLDSTART_MODEL = CatBoostColdStartWrapper("catboost", cb)
                logger.info("Loaded CatBoost cold-start CBM model from %s", cbm_path)
                return _COLDSTART_MODEL
            except Exception as e:
                logger.warning("Could not load CatBoost cold-start CBM model: %s", e)
    return _COLDSTART_MODEL



def serving_temperature() -> float | None:
    """Fitted temperature for the UPI head, or None when no artifact exists.

    Cached after the first read. A missing or malformed file is not an error:
    uncalibrated scoring is the documented default.
    """
    global _SERVING_TEMPERATURE
    if _SERVING_TEMPERATURE is not None:
        return _SERVING_TEMPERATURE
    path = os.path.join(config.ARTIFACTS_DIR, "calibration",
                        "upi_edge_model_temperature.json")
    try:
        with open(path, encoding="utf-8") as fh:
            _SERVING_TEMPERATURE = float(json.load(fh)["T"])
    except (OSError, ValueError, KeyError, TypeError):
        _SERVING_TEMPERATURE = None
    return _SERVING_TEMPERATURE


def temperature_is_applied() -> bool:
    """True when score_transaction is dividing UPI logits by a fitted T."""
    return _SERVING_TEMPERATURE_APPLIED


def temperature_should_apply(temperature: float | None) -> bool:
    """Whether a fitted temperature is far enough from 1.0 to be worth it.

    Only re-scale the served probabilities when the fit moved by
    more than 0.05. A temperature of 1.03 changes the score by less than one
    point, and silently reshaping served scores for that is not worth the
    extra artifact dependency.
    """
    return temperature is not None and abs(temperature - 1.0) > 0.05

# Feature contracts. The active head decides which key set is required; the
# embedding width may be either head's width (32 UPI / 64 PaySim), because the
# module cannot always see which session the caller loaded.
ALLOWED_EMB_DIMS: tuple[int, ...] = (config.UPI_EMB_DIM, config.PAYSIM_EMB_DIM)
PAYSIM_REQUIRED_FEATURES: tuple[str, ...] = (
    "sender_embedding", "receiver_embedding", "amount",
    "origin_balance_error", "dest_balance_error", "tx_type",
)
UPI_REQUIRED_FEATURES: tuple[str, ...] = (
    "sender_embedding", "receiver_embedding", "amount",
    "velocity_10min", "device_change", "ip_risk",
)


def _load_embedding_store() -> dict[str, np.ndarray]:
    """Load the account -> embedding map for the *active* head, once.

    UPI head active -> artifacts/upi_node_embeddings.npz (32-dim vectors keyed
    by masked UPI handle). PaySim head active -> artifacts/account_index.json
    + node_embeddings.npz (64-dim, PaySim account ids). Missing artifacts just
    give an empty store (hash fallback downstream), the safe no-info case.
    """
    global _EMBEDDING_STORE
    if _EMBEDDING_STORE is not None:
        return _EMBEDDING_STORE

    if os.path.exists(config.UPI_MODEL_PATH):
        _EMBEDDING_STORE = _load_upi_embedding_lookup()
        return _EMBEDDING_STORE

    store: dict[str, np.ndarray] = {}
    idx_path = os.path.join(config.ARTIFACTS_DIR, "account_index.json")
    emb_path = os.path.join(config.ARTIFACTS_DIR, "node_embeddings.npz")

    try:
        idx = json.loads(open(idx_path, encoding="utf-8").read())
        emb = np.load(emb_path, allow_pickle=False)["embeddings"]
        for acc, i in idx.items():
            store[acc] = emb[i]
        logger.info("Loaded %d account embeddings from artifacts/", len(store))
    except Exception as exc:
        logger.warning("Could not load embedding store (%s); using empty store", exc)

    _EMBEDDING_STORE = store
    return store


def _load_upi_embedding_lookup() -> dict[str, np.ndarray]:
    """Load artifacts/upi_node_embeddings.npz: masked UPI handle -> 32 floats.

    train_upi_model.py writes `account_ids` as a fixed-width unicode array, so
    this loads with allow_pickle=False. A missing or malformed file yields an
    empty lookup and every account then takes the hash fallback.
    """
    try:
        data = np.load(config.UPI_EMBEDDINGS_PATH, allow_pickle=False)
        ids = data["account_ids"]
        embeddings = data["embeddings"]
        store = {str(acc): embeddings[i] for i, acc in enumerate(ids)}
        logger.info("Loaded %d UPI account embeddings from %s",
                    len(store), config.UPI_EMBEDDINGS_PATH)
        return store
    except Exception as exc:
        logger.warning("Could not load UPI embeddings (%s); using empty store", exc)
        return {}


def active_model_path(requested: str | None = None) -> str:
    """The path load_model will actually use.

    Precedence: artifacts/upi_edge_model.onnx wins whenever it exists,
    otherwise `requested` (default config.MODEL_PATH, the PaySim head).
    """
    if os.path.exists(config.UPI_MODEL_PATH):
        return config.UPI_MODEL_PATH
    return requested or config.MODEL_PATH


def _model_input_names(model: object) -> list[str]:
    """ONNX input names of a loaded session; [] for the mock or a stub."""
    if model is None or isinstance(model, str):
        return []
    try:
        return [i.name for i in model.get_inputs()]
    except AttributeError:
        return []


def _contract_is_upi(model: object, input_names: list[str] | None = None) -> bool:
    """Which feature contract the loaded model speaks.

    Read off the session's input names when they are available. The mock
    scorer mirrors the PaySim contract (that is what its heuristic models); a
    model object with no introspectable inputs follows the active head.
    """
    names = _model_input_names(model) if input_names is None else input_names
    if names:
        return "velocity_10min" in names
    if isinstance(model, str):
        return False
    return os.path.exists(config.UPI_MODEL_PATH)


def _tx_type_to_int(tx_type: str) -> int:
    """Map a PaySim type string to the int the model expects.

    Order comes from scaler.json: CASH_IN, CASH_OUT, DEBIT, PAYMENT, TRANSFER.
    Unknown types fall back to DEBIT (index 2).
    """
    types = config.PAYSIM_TXN_TYPES
    if tx_type in types:
        return types.index(tx_type)
    return 2


def _validate_features(features: dict, upi: bool = False) -> None:
    """Raise ValueError if any required key is missing or has the wrong type.

    `upi=True` selects the UPI head's contract: velocity_10min/device_change/
    ip_risk become required and the PaySim balance/transaction-type fields are
    not inspected, since the UPI head never reads them. Embeddings may be 32
    or 64 floats whichever head is loaded.
    """
    if not isinstance(features, dict):
        raise ValueError(f"features must be a dict, got {type(features).__name__}")

    required = set(UPI_REQUIRED_FEATURES if upi else PAYSIM_REQUIRED_FEATURES)
    missing = required - set(features.keys())
    if missing:
        raise ValueError(f"Missing feature: {sorted(missing)[0]}")

    if not isinstance(features["amount"], (int, float)) or features["amount"] <= 0:
        raise ValueError("feature 'amount' must be a positive number")

    if upi:
        for key in ("velocity_10min", "device_change", "ip_risk"):
            if not isinstance(features[key], (int, float)):
                raise ValueError(f"feature '{key}' must be a number")
    else:
        for key in ("origin_balance_error", "dest_balance_error"):
            if not isinstance(features[key], (int, float)):
                raise ValueError(f"feature '{key}' must be a number")

        tx_type = features["tx_type"]
        if not isinstance(tx_type, (str, int)):
            raise ValueError(f"feature 'tx_type' must be a string or int, got {type(tx_type).__name__}")
        if isinstance(tx_type, str):
            if tx_type not in config.PAYSIM_TXN_TYPES and tx_type not in ("0", "1", "2", "3", "4"):
                raise ValueError(f"feature 'tx_type' unknown: {tx_type!r}")

    for key in ("sender_embedding", "receiver_embedding"):
        if not isinstance(features[key], list):
            raise ValueError(f"feature '{key}' must be a list")
        if len(features[key]) not in ALLOWED_EMB_DIMS:
            widths = " or ".join(str(d) for d in ALLOWED_EMB_DIMS)
            raise ValueError(
                f"feature '{key}' must be length {widths}, got {len(features[key])}"
            )


def load_model(path: str) -> object:
    """Load the active ONNX model. Falls back to a mock scorer if unavailable.

    Precedence (documented): artifacts/upi_edge_model.onnx is loaded whenever
    it exists, even when a different `path` was requested; otherwise `path`
    (normally config.MODEL_PATH, the PaySim head) is used. A cache entry for
    the requested path is honoured first, so a caller can pin mock mode.

    Returns an onnxruntime.InferenceSession OR the string "mock".
    score_transaction handles both. Result is cached in _MODEL_CACHE.
    """
    if path in _MODEL_CACHE:
        logger.info("Model already cached: %s", path)
        return _MODEL_CACHE[path]

    effective = active_model_path(path)
    if effective in _MODEL_CACHE:
        logger.info("Model already cached: %s", effective)
        return _MODEL_CACHE[effective]
    if effective != path:
        logger.info("UPI head present: loading %s in preference to %s",
                    effective, path)

    try:
        import onnxruntime as ort

        session = ort.InferenceSession(effective, providers=["CPUExecutionProvider"])
        logger.info("ONNX model loaded: %s", effective)
        _MODEL_CACHE[effective] = session
        return session
    except ImportError:
        logger.warning("onnxruntime not installed; using mock scorer")
    except FileNotFoundError:
        logger.warning("Model file not found: %s; using mock scorer", effective)
    except Exception as exc:
        logger.warning("Model load failed (%s); using mock scorer", exc)

    _MODEL_CACHE[effective] = "mock"
    return "mock"


def score_transaction(model: object, features: dict) -> "ScoreResult":
    """Score one transaction. CONTRACTS.md section 7.

    Needs the 6 model features (embeddings are len-64 lists, amount > 0,
    tx_type a PaySim type string or 0-4 int). Returns score in [0,100] with
    the matching action, explanation sorted by weight, latency > 0.
    """
    upi = _contract_is_upi(model)
    _validate_features(features, upi=upi)

    start = time.perf_counter()

    # Cold-Start Routing: If transaction involves accounts not in the 20,000-node GNN store,
    # evaluate via the CatBoost cold-start model on tabular edge features
    if features.get("is_cold_start"):
        cb = _get_coldstart_model()
        if cb is not None:
            amt = float(features.get("amount", 0.0))
            vel = float(features.get("velocity_10min", 0.0))
            dev = 1.0 if features.get("device_change") else 0.0
            ip = float(features.get("ip_risk", 0.0))
            X = np.array([[np.log1p(amt), np.log1p(vel), dev, ip]], dtype=np.float32)
            prob = float(cb.predict_proba(X)[0, 1])
            score = int(round(prob * 100))
            score = max(0, min(100, score))
            action = _action_from_score(score)
            explanation = [
                ("cold-start tabular scoring (new account)", 0.40),
                ("velocity spike in 10-min window", 0.30 if vel > 0 else 0.05),
                ("ip address risk rating", 0.20 if ip > 0.4 else 0.05),
                ("transaction value anomaly", 0.10 if amt > 50000 else 0.05),
            ]
            explanation.sort(key=lambda item: item[1], reverse=True)
            elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
            return ScoreResult(score=score, action=action, explanation=explanation, latency_ms=elapsed_ms)


    global _SERVING_TEMPERATURE_APPLIED

    if model == "mock":
        score = _mock_score(features)
        _SERVING_TEMPERATURE_APPLIED = False
    else:
        # embeddings are already resolved by backend._build_features;
        # we just trust the arrays we were handed
        inp = _prepare_onnx_inputs(features, upi=upi)

        outputs = model.run(["score"], inp)
        arr = np.asarray(outputs[0])
        if arr.ndim == 2 and arr.shape[1] == 2:
            # UPI head: 2 logits [legitimate, fraud] -> softmax, take fraud,
            # after temperature scaling when a meaningful T was fitted.
            temperature = serving_temperature()
            _SERVING_TEMPERATURE_APPLIED = temperature_should_apply(temperature)
            if _SERVING_TEMPERATURE_APPLIED:
                arr = arr / float(temperature)
            shifted = arr - arr.max(axis=1, keepdims=True)
            exp = np.exp(shifted)
            prob = float((exp / exp.sum(axis=1, keepdims=True))[0, 1])
        else:
            _SERVING_TEMPERATURE_APPLIED = False
            # PaySim head: a single logit -> sigmoid
            raw = float(arr.flatten()[0])
            prob = 1.0 / (1.0 + math.exp(-raw))
        score = int(round(prob * 100))
        score = max(0, min(100, score))

    action = _action_from_score(score)
    explanation = _explain(features, score)
    elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))

    return ScoreResult(
        score=score,
        action=action,
        explanation=explanation,
        latency_ms=elapsed_ms,
    )


def _prepare_onnx_inputs(features: dict,
                         upi: bool | None = None) -> dict[str, np.ndarray]:
    """Build the input arrays for whichever contract the active model speaks.

    `upi=None` (a bare call) follows the active head, i.e. the same precedence
    load_model uses.
    """
    if upi is None:
        upi = os.path.exists(config.UPI_MODEL_PATH)
    if upi:
        return _prepare_upi_inputs(features)
    return _prepare_paysim_inputs(features)


def _prepare_paysim_inputs(features: dict) -> dict[str, np.ndarray]:
    """The PaySim head's 6 inputs: 64-dim embeddings + 4 scaled tabulars.

    Scales amount + balance errors with the scaler loaded at import time
    from artifacts/scaler.json.
    """
    tab_mean = config.SCALER_TAB_MEAN
    tab_scale = config.SCALER_TAB_SCALE
    if not tab_mean or not tab_scale:
        raise RuntimeError(
            "Scaler fields are empty. Run train_model.py to produce artifacts/scaler.json."
        )

    sender_emb = np.array([features["sender_embedding"]], dtype=np.float32)
    receiver_emb = np.array([features["receiver_embedding"]], dtype=np.float32)

    # amount -> log1p then scale, matching the training pipeline exactly
    # (train_model.edge_tabular builds the amount column as np.log1p(amount)
    # and scaler_tab is fit on that column)
    amount = float(features["amount"])
    amount_scaled = (math.log1p(amount) - tab_mean[0]) / tab_scale[0]
    amount_arr = np.array([[amount_scaled]], dtype=np.float32)

    # balance errors -> scale
    ob = float(features["origin_balance_error"])
    db = float(features["dest_balance_error"])
    ob_scaled = (ob - tab_mean[1]) / tab_scale[1]
    db_scaled = (db - tab_mean[2]) / tab_scale[2]
    ob_arr = np.array([[ob_scaled]], dtype=np.float32)
    db_arr = np.array([[db_scaled]], dtype=np.float32)

    # tx_type -> int 0-4
    tx_type = features["tx_type"]
    tx_int = _tx_type_to_int(tx_type) if isinstance(tx_type, str) else int(tx_type)
    tx_arr = np.array([[tx_int]], dtype=np.float32)

    return {
        "sender_embedding": sender_emb,
        "receiver_embedding": receiver_emb,
        "amount": amount_arr,
        "origin_balance_error": ob_arr,
        "dest_balance_error": db_arr,
        "tx_type": tx_arr,
    }


def _prepare_upi_inputs(features: dict) -> dict[str, np.ndarray]:
    """The UPI head's 6 inputs: 32-dim embeddings + raw UPI edge features.

    Mirrors train_upi_model.py exactly; no scaler is involved:
      amount           log1p(amount_inr)
      velocity_10min   log1p(same-sender txns in the preceding 600s)
      device_change    0.0 / 1.0
      ip_risk          raw 0.0 - 1.0
    """
    sender_emb = np.array([features["sender_embedding"]], dtype=np.float32)
    receiver_emb = np.array([features["receiver_embedding"]], dtype=np.float32)
    amount_arr = np.array([[math.log1p(float(features["amount"]))]],
                          dtype=np.float32)
    vel_arr = np.array([[math.log1p(float(features["velocity_10min"]))]],
                       dtype=np.float32)
    device_arr = np.array([[1.0 if features["device_change"] else 0.0]],
                          dtype=np.float32)
    ip_arr = np.array([[float(features["ip_risk"])]], dtype=np.float32)

    return {
        "sender_embedding": sender_emb,
        "receiver_embedding": receiver_emb,
        "amount": amount_arr,
        "velocity_10min": vel_arr,
        "device_change": device_arr,
        "ip_risk": ip_arr,
    }


def _action_from_score(score: int) -> str:
    if score < config.THRESHOLD_MONITOR:
        return config.ACTION_ALLOW
    if score < config.THRESHOLD_STEPUP:
        return config.ACTION_MONITOR
    if score < config.THRESHOLD_BLOCK:
        return config.ACTION_STEPUP
    return config.ACTION_BLOCK


def _mock_score(features: dict) -> int:
    """Heuristic score used when the ONNX model is unavailable.

    Big balance-error magnitude or a TRANSFER/CASH_OUT pushes the score up,
    large amount adds a mild boost. Deterministic so tests are stable.
    """
    score = 5

    ob = abs(float(features["origin_balance_error"]))
    db = abs(float(features["dest_balance_error"]))
    score += min(35, int((ob + db) * 8))

    tx_type = features["tx_type"]
    if isinstance(tx_type, str):
        if tx_type in ("TRANSFER", "CASH_OUT"):
            score += 15
        elif tx_type in ("CASH_IN", "DEBIT"):
            score += 5
    else:
        if tx_type in (3, 4):  # PAYMENT/TRANSFER
            score += 15
        elif tx_type in (0, 1):  # CASH_IN/CASH_OUT
            score += 8

    amount = float(features["amount"])
    score += min(10, int(math.log10(max(amount, 1)) * 2))

    return max(0, min(100, score))


def _explain(features: dict, score: int) -> list[tuple[str, float]]:
    """Attribution weights for the decision explanation.

    Feature magnitudes relative to their training distribution (scaler.json).
    Same labels in mock mode, just heuristic numbers.
    """
    tab_scale = config.SCALER_TAB_SCALE
    tab_mean = config.SCALER_TAB_MEAN

    # scalers are empty lists when training hasn't run — guard the indexing
    def _z(value: float, i: int) -> float:
        if len(tab_scale) > i and tab_scale[i]:
            return value / tab_scale[i]
        return 0.0

    # .get + defaults: a UPI-contract payload need not carry the PaySim fields
    ob = abs(float(features.get("origin_balance_error", 0.0)))
    db = abs(float(features.get("dest_balance_error", 0.0)))
    ob_z = _z(ob, 1)
    db_z = _z(db, 2)

    amount = float(features.get("amount", 0.0))
    amount_z = _z(amount - tab_mean[0], 0) if len(tab_mean) > 0 else 0.0

    tx_type = features.get("tx_type")
    if isinstance(tx_type, str):
        tx_unusual = 1.0 if tx_type in ("TRANSFER", "CASH_OUT") else 0.3
    elif tx_type is None:
        tx_unusual = 0.0
    else:
        tx_unusual = 1.0 if tx_type in (3, 4) else 0.3

    raw = [
        ("origin balance drain", round(min(0.40, ob_z * 0.12), 3)),
        ("destination balance drain", round(min(0.40, db_z * 0.12), 3)),
        ("high-value transaction", round(min(0.20, max(0.0, amount_z) * 0.05), 3)),
        ("unusual transaction type", round(tx_unusual * 0.18, 3)),
        ("graph proximity to mule ring", 0.05 if score >= 70 else 0.02),
    ]

    # UPI-shaped signals, only when the caller sent them
    if "ip_risk" in features:
        ip = float(features["ip_risk"])
        raw.append(("ip risk", round(min(0.35, ip * 0.35), 3)))
    if features.get("device_change"):
        raw.append(("device change on sender", 0.22))
    velocity = int(features.get("velocity_10min", 0) or 0)
    if velocity > 0:
        raw.append(("transfer velocity (10 min)",
                    round(min(0.30, math.log1p(velocity) * 0.15), 3)))

    raw.sort(key=lambda x: -x[1])
    total = sum(w for _, w in raw) or 1.0
    return [(label, round(w / total, 3)) for label, w in raw]


@dataclass
class ScoreResult:
    """Matches CONTRACTS.md section 2 (revised)."""

    score: int
    action: str
    explanation: list[tuple[str, float]]
    latency_ms: int
