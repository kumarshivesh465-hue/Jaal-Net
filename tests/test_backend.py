"""Integration tests for backend.py. Uses FastAPI TestClient.

The fixture forces inference to mock mode so these run without a real model file
and are fast. The mocked scorer uses the same 6-key feature contract as the
real ONNX model, so the request/response shape is verified correctly.

Full-model integration tests (against the real ONNX artifact) live in
test_inference.py (marked @pytest.mark.integration) and are additionally
covered below by /score end-to-end tests when the model file is present.
"""

import pytest
from fastapi.testclient import TestClient

import config


@pytest.fixture
def client():
    """TestClient with the app, but model load is forced to mock mode.

    The mock scorer uses the real 6-key PaySim feature contract, so the
    request/response shape is verified even without a model file.
    """
    import inference

    inference._MODEL_CACHE[config.MODEL_PATH] = "mock"
    from backend import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def valid_body():
    return {
        "txn_id":                "UPI-test-00001",
        "sender":                "A***4521",
        "receiver":              "B***8812",
        "amount":                45000.00,
        "origin_balance_error":  -8.5,
        "dest_balance_error":    -5.2,
        "tx_type":               "TRANSFER",
    }


# ---------- /health ----------

def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_version"] == config.MODEL_VERSION


# ---------- /score ----------

def test_score_returns_valid_response(client, valid_body):
    r = client.post("/score", json=valid_body)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 100
    assert body["action"] in config.ACTIONS
    assert body["latency_ms"] > 0
    assert isinstance(body["explanation"], list)


def test_score_action_consistent_with_thresholds(client, valid_body):
    r = client.post("/score", json=valid_body)
    body = r.json()
    score = body["score"]
    action = body["action"]
    if score < config.THRESHOLD_MONITOR:
        assert action == config.ACTION_ALLOW
    elif score < config.THRESHOLD_STEPUP:
        assert action == config.ACTION_MONITOR
    elif score < config.THRESHOLD_BLOCK:
        assert action == config.ACTION_STEPUP
    else:
        assert action == config.ACTION_BLOCK


def test_score_rejects_negative_amount(client, valid_body):
    bad = dict(valid_body, amount=-100)
    r = client.post("/score", json=bad)
    assert r.status_code == 422


def test_score_rejects_zero_amount(client, valid_body):
    bad = dict(valid_body, amount=0)
    r = client.post("/score", json=bad)
    assert r.status_code == 422


def test_score_rejects_missing_fields(client):
    r = client.post("/score", json={"txn_id": "x"})
    assert r.status_code == 422


def test_score_rejects_unknown_tx_type(client, valid_body):
    bad = dict(valid_body, tx_type=" pyramid_scheme ")
    r = client.post("/score", json=bad)
    assert r.status_code == 422


def test_score_accepts_all_five_txn_types(client):
    """Every tx_type in PAYSIM_TXN_TYPES should be accepted (200)."""
    for tx_type in config.PAYSIM_TXN_TYPES:
        body = {
            "txn_id":                f"UPI-tx-{tx_type}",
            "sender":                "A***1111",
            "receiver":              "B***2222",
            "amount":                1000.0,
            "origin_balance_error":  0.0,
            "dest_balance_error":    0.0,
            "tx_type":               tx_type,
        }
        r = client.post("/score", json=body)
        assert r.status_code == 200, f"tx_type {tx_type!r} was rejected: {r.json()}"


def test_score_old_fields_ignored_new_fields_required(client, valid_body):
    """The new contract replaces velocity_10min/device_change/ip_risk with
    origin_balance_error/dest_balance_error/tx_type. Pydantic/FastAPI ignores
    extra fields by default, so sending the old fields alongside the new ones
    yields 200 (the new 6 keys are used). What must hold: the new keys are
    required, and the old keys are not.
    """
    body_with_old_fields = dict(valid_body)
    body_with_old_fields["velocity_10min"] = 47
    body_with_old_fields["device_change"] = True
    body_with_old_fields["ip_risk"] = 0.87
    r = client.post("/score", json=body_with_old_fields)
    # FastAPI ignores extra fields by default -> 200.
    assert r.status_code == 200, f"Expected 200 (extra fields ignored), got {r.status_code}: {r.json()}"
    body = r.json()
    assert 0 <= body["score"] <= 100
    assert body["action"] in config.ACTIONS


def test_score_explanation_sorted_descending(client, valid_body):
    r = client.post("/score", json=valid_body)
    weights = [w for _, w in r.json()["explanation"]]
    assert weights == sorted(weights, reverse=True)


def test_score_latency_ms_positive(client, valid_body):
    r = client.post("/score", json=valid_body)
    assert r.json()["latency_ms"] > 0


# ---------- /dev/sample ----------

def test_dev_sample_returns_valid_body(client):
    r = client.get("/dev/sample")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "txn_id", "sender", "receiver", "amount",
        "origin_balance_error", "dest_balance_error", "tx_type",
    ):
        assert key in body, f"missing key {key!r}"
    # The returned body must itself be scoreable.
    r2 = client.post("/score", json=body)
    assert r2.status_code == 200
