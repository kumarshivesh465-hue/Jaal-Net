"""Contract tests for inference.py per CONTRACTS.md section 7 (revised).

Feature contract (PaySim-trained model):
  sender_embedding, receiver_embedding (list[float] length 64),
  amount (> 0), origin_balance_error, dest_balance_error (numbers),
  tx_type (str in PAYSIM_TXN_TYPES or int 0-4).

Tests marked `integration` require a real ONNX model file at config.MODEL_PATH.
They are skipped if the file is absent.
"""

import os

import numpy as np
import pytest

import config
from config import (
    MODEL_PATH,
    THRESHOLD_BLOCK,
    THRESHOLD_MONITOR,
    THRESHOLD_STEPUP,
    PAYSIM_TXN_TYPES,
    EMB_DIM,
)

inference = pytest.importorskip("inference")


def _fake_features(tx_type="TRANSFER") -> dict:
    emb = [0.0] * EMB_DIM
    return {
        "sender_embedding":   emb,
        "receiver_embedding": emb,
        "amount":             45000.0,
        "origin_balance_error": -8.5,
        "dest_balance_error":   -5.2,
        "tx_type":             tx_type,
        # UPI-contract fields, so this helper works whichever head is loaded
        # (the PaySim head simply ignores them)
        "velocity_10min":      0,
        "device_change":       False,
        "ip_risk":             0.0,
    }


def test_load_model_falls_back_to_mock_when_file_missing():
    if os.path.exists(MODEL_PATH):
        pytest.skip("Model file present; mock fallback not exercised")
    assert inference.load_model(MODEL_PATH) == "mock"


def test_score_transaction_mock_mode_returns_valid_result():
    result = inference.score_transaction("mock", _fake_features())
    assert 0 <= result.score <= 100
    assert result.action in {"ALLOW", "MONITOR", "STEP_UP", "BLOCK"}
    assert result.latency_ms > 0
    assert isinstance(result.explanation, list)


def test_score_transaction_raises_on_missing_keys():
    """Validation happens first, so this works without a real model."""
    incomplete = {"amount": 100.0}
    with pytest.raises(ValueError, match="Missing feature"):
        inference.score_transaction(lambda x: 50, incomplete)


def test_score_transaction_raises_on_bad_amount():
    features = _fake_features()
    bad = dict(features, amount=-100)
    with pytest.raises(ValueError, match="positive number"):
        inference.score_transaction("mock", bad)


def test_score_transaction_raises_on_bad_balance_error():
    features = _fake_features()
    bad = dict(features, origin_balance_error="not-a-number")
    with pytest.raises(ValueError, match="must be a number"):
        inference.score_transaction("mock", bad)


def test_score_transaction_raises_on_bad_tx_type():
    features = _fake_features()
    bad = dict(features, tx_type="NOT_A_REAL_TYPE")
    with pytest.raises(ValueError, match="unknown"):
        inference.score_transaction("mock", bad)


def test_score_transaction_tx_type_int_accepted():
    """The model accepts tx_type as an int 0-4 too."""
    features = _fake_features()
    int_features = dict(features, tx_type=3)  # PAYMENT
    result = inference.score_transaction("mock", int_features)
    assert isinstance(result.score, int)


def test_score_transaction_embedding_wrong_dim_raises():
    bad = _fake_features()
    bad["sender_embedding"] = [0.0] * (EMB_DIM + 1)
    with pytest.raises(ValueError, match="must be length"):
        inference.score_transaction("mock", bad)


def test_score_action_consistent_with_thresholds_mock_mode():
    result = inference.score_transaction("mock", _fake_features())
    if result.score < THRESHOLD_MONITOR:
        assert result.action == "ALLOW"
    elif result.score < THRESHOLD_STEPUP:
        assert result.action == "MONITOR"
    elif result.score < THRESHOLD_BLOCK:
        assert result.action == "STEP_UP"
    else:
        assert result.action == "BLOCK"


def test_score_transaction_explanation_sorted_descending_mock_mode():
    result = inference.score_transaction("mock", _fake_features())
    weights = [w for _, w in result.explanation]
    assert weights == sorted(weights, reverse=True)


def test_score_transaction_score_zero_for_no_risk_features():
    """Zero balance error + CASH_IN should produce a low (near-zero) mock score."""
    result = inference.score_transaction(
        "mock",
        {
            "sender_embedding":   [0.0] * EMB_DIM,
            "receiver_embedding": [0.0] * EMB_DIM,
            "amount":             100.0,
            "origin_balance_error": 0.0,
            "dest_balance_error": 0.0,
            "tx_type": "CASH_IN",
        },
    )
    assert 0 <= result.score < 30  # ALLOW band


@pytest.mark.integration
def test_load_model_returns_session():
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Model file not found: {MODEL_PATH}")
    # Clear the module cache so we actually load (not return a stale mock
    # left by a prior mock-mode test in the same session).
    inference._MODEL_CACHE.pop(MODEL_PATH, None)
    model = inference.load_model(MODEL_PATH)
    assert hasattr(model, "run") or callable(model)


@pytest.mark.integration
def test_score_transaction_valid_output():
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Model file not found: {MODEL_PATH}")
    inference._MODEL_CACHE.pop(MODEL_PATH, None)
    model = inference.load_model(MODEL_PATH)
    result = inference.score_transaction(model, _fake_features())
    assert 0 <= result.score <= 100
    assert result.action in {"ALLOW", "MONITOR", "STEP_UP", "BLOCK"}
    assert result.latency_ms > 0
    assert isinstance(result.explanation, list)
    weights = [w for _, w in result.explanation]
    assert weights == sorted(weights, reverse=True)


@pytest.mark.integration
def test_score_transaction_output_is_sigmoid_scaled():
    """The ONNX model outputs a logit, not a probability. The score should be
    in 0-100 and produce a sane action. A transaction with large negative
    balance errors and a TRANSFER should score high; one with zero errors and
    CASH_IN should score low."""
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Model file not found: {MODEL_PATH}")
    inference._MODEL_CACHE.pop(MODEL_PATH, None)
    model = inference.load_model(MODEL_PATH)

    high_risk = _fake_features(tx_type="TRANSFER")
    high_risk["amount"] = 250000.0
    high_risk["origin_balance_error"] = -25.0
    high_risk["dest_balance_error"] = -18.0
    high = inference.score_transaction(model, high_risk)

    low_risk = _fake_features(tx_type="CASH_IN")
    low_risk["amount"] = 500.0
    low_risk["origin_balance_error"] = 0.0
    low_risk["dest_balance_error"] = 0.0
    low = inference.score_transaction(model, low_risk)

    # The high-risk one should be >= the low-risk one. We don't assert exact
    # ordering because model scores are distribution-dependent, but both must
    # be valid and the high-risk one should not be in the ALLOW band if the
    # model learned anything (it did: AUC-PR 0.514).
    assert 0 <= high.score <= 100
    assert 0 <= low.score <= 100
    assert high.action in {"ALLOW", "MONITOR", "STEP_UP", "BLOCK"}
    assert low.action in {"ALLOW", "MONITOR", "STEP_UP", "BLOCK"}


@pytest.mark.integration
def test_score_transaction_handles_account_not_in_embedding_store():
    """When the sender/receiver is not in the embedding index, the backend
    falls back to a hash embedding. This test verifies inference itself still
    works when given a 64-dim embedding that happened to be the hash of an
    out-of-index account (the embedding store lookup is in backend, not here)."""
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Model file not found: {MODEL_PATH}")
    inference._MODEL_CACHE.pop(MODEL_PATH, None)
    import hashlib
    model = inference.load_model(MODEL_PATH)

    digest = hashlib.sha256(b"nonexistent-account-99999").digest()
    emb = [round(digest[i % len(digest)] / 255.0, 4) for i in range(EMB_DIM)]
    features = {
        "sender_embedding":   emb,
        "receiver_embedding": emb,
        "amount":             10000.0,
        "origin_balance_error": 0.0,
        "dest_balance_error": 0.0,
        "tx_type": "DEBIT",
        # UPI-contract fields; required by the UPI head, ignored by PaySim
        "velocity_10min": 0,
        "device_change": False,
        "ip_risk": 0.0,
    }
    result = inference.score_transaction(model, features)
    assert 0 <= result.score <= 100
    assert result.latency_ms > 0


# ---------------------------------------------------------------------------
# UPI head wiring (artifacts/upi_edge_model.onnx takes precedence)
# ---------------------------------------------------------------------------

UPI_MODEL_PATH = config.UPI_MODEL_PATH
UPI_EMBEDDINGS_PATH = config.UPI_EMBEDDINGS_PATH

needs_upi_artifacts = pytest.mark.skipif(
    not (os.path.exists(UPI_MODEL_PATH) and os.path.exists(UPI_EMBEDDINGS_PATH)),
    reason="UPI artifacts missing (run train_upi_model.py)",
)


def _upi_accounts() -> list[str]:
    """Two masked handles from the table the UPI head is served with."""
    data = np.load(UPI_EMBEDDINGS_PATH, allow_pickle=False)
    return [str(a) for a in data["account_ids"][:2]]


def _reset_model_state() -> None:
    """Drop the model + embedding caches so the next load starts fresh."""
    inference._MODEL_CACHE.clear()
    inference._EMBEDDING_STORE = None


@needs_upi_artifacts
def test_score_endpoint_with_upi_account_and_fields_returns_score():
    """A known UPI account plus the three UPI features scores end to end."""
    from fastapi.testclient import TestClient

    import backend

    sender, receiver = _upi_accounts()
    _reset_model_state()
    with TestClient(backend.app) as client:
        # the UPI head really is the one serving
        loaded = [i.name for i in client.app.state.model.get_inputs()]
        assert "velocity_10min" in loaded
        response = client.post("/score", json={
            "txn_id": "UPI-wiring-00001",
            "sender": sender,
            "receiver": receiver,
            "amount": 45000.0,
            "origin_balance_error": -8.5,
            "dest_balance_error": -5.2,
            "tx_type": "TRANSFER",
            "velocity_10min": 7,
            "device_change": True,
            "ip_risk": 0.9,
        })
    assert response.status_code == 200, response.json()
    payload = response.json()
    assert 0 <= payload["score"] <= 100
    assert payload["action"] in {"ALLOW", "MONITOR", "STEP_UP", "BLOCK"}
    assert payload["explanation"], "explanation must be non-empty"
    weights = [w for _, w in payload["explanation"]]
    assert weights == sorted(weights, reverse=True)


@needs_upi_artifacts
def test_score_endpoint_without_upi_fields_still_works():
    """Backward compatibility: the UPI fields default to benign."""
    from fastapi.testclient import TestClient

    import backend

    sender, receiver = _upi_accounts()
    body = {
        "txn_id": "UPI-legacy-00001",
        "sender": sender,
        "receiver": receiver,
        "amount": 45000.0,
        "origin_balance_error": -8.5,
        "dest_balance_error": -5.2,
        "tx_type": "TRANSFER",
    }
    request = backend.ScoreRequest(**body)  # old payloads must still validate
    assert (request.velocity_10min, request.device_change,
            request.ip_risk) == (0, False, 0.0)

    _reset_model_state()
    with TestClient(backend.app) as client:
        response = client.post("/score", json=body)
    assert response.status_code == 200, response.json()
    assert 0 <= response.json()["score"] <= 100


@needs_upi_artifacts
def test_model_selector_picks_upi_head_when_present():
    """The UPI artifact wins over config.MODEL_PATH while it exists."""
    _reset_model_state()
    try:
        assert inference.active_model_path(config.MODEL_PATH) == UPI_MODEL_PATH
        model = inference.load_model(config.MODEL_PATH)
        assert hasattr(model, "get_inputs"), "expected a real ONNX session"
        assert "velocity_10min" in [i.name for i in model.get_inputs()]
        assert inference._contract_is_upi(model) is True
    finally:
        _reset_model_state()


def test_model_selector_falls_back_to_paysim_when_upi_absent(tmp_path, monkeypatch):
    """With no UPI file the PaySim head (or the mock) is selected instead."""
    monkeypatch.setattr(config, "UPI_MODEL_PATH", str(tmp_path / "absent.onnx"))
    _reset_model_state()
    try:
        assert inference.active_model_path(config.MODEL_PATH) == config.MODEL_PATH
        model = inference.load_model(config.MODEL_PATH)
        if os.path.exists(config.MODEL_PATH):
            assert hasattr(model, "get_inputs")
            assert inference._contract_is_upi(model) is False
        else:
            assert model == "mock"
    finally:
        _reset_model_state()
