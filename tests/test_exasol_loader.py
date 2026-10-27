"""Unit tests for exasol_loader.py in mock mode (no live connection).

Run:
    pytest tests/test_exasol_loader.py -v
"""

import pytest

import config
import exasol_loader as loader


@pytest.fixture(autouse=True)
def force_mock_mode(monkeypatch):
    """Ensure no real connection is attempted during tests.

    config.py reads .env at import time, so clearing the environment variable
    is no longer enough to reach mock mode: the effective password has to be
    cleared too.
    """
    monkeypatch.delenv("EXASOL_PASSWORD", raising=False)
    monkeypatch.setattr(config, "EXASOL_PASSWORD", "", raising=False)
    loader._CONN = None
    yield
    loader._CONN = None


def test_fetch_recent_transactions_returns_list():
    rows = loader.fetch_recent_transactions(limit=10)
    assert isinstance(rows, list)
    assert len(rows) == 10


def test_fetch_recent_transactions_has_expected_columns():
    rows = loader.fetch_recent_transactions(limit=3)
    expected = {
        "txn_id", "txn_timestamp", "sender_account", "receiver_account",
        "amount_inr", "model_score", "action_taken", "sender_state",
        "device_change_flag", "ip_risk_score", "ring_id",
    }
    for row in rows:
        assert set(row.keys()) == expected


def test_fetch_decision_log_returns_list():
    rows = loader.fetch_decision_log("UPI-test-00001")
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0]["txn_id"] == "UPI-test-00001"


def test_fetch_active_thresholds_returns_dict():
    t = loader.fetch_active_thresholds()
    assert isinstance(t, dict)
    assert "threshold_block" in t
    assert "threshold_stepup" in t
    assert "threshold_monitor" in t
    assert t["threshold_monitor"] < t["threshold_stepup"] < t["threshold_block"]


@pytest.mark.parametrize("ring_id", config.RING_IDS)
def test_fetch_ring_members_returns_list(ring_id):
    members = loader.fetch_ring_members(ring_id)
    assert isinstance(members, list)
    assert len(members) > 0
    for m in members:
        assert "account_id" in m
        assert m["role"] in {"hub", "spoke", "layering", "cash_out"}


def test_count_blocked_volume_24h_returns_float():
    v = loader.count_blocked_volume_24h()
    assert isinstance(v, float)
    assert v >= 0.0


def test_insert_decision_in_mock_mode_returns_true():
    ok = loader.insert_decision(
        txn_id="UPI-test-00001",
        model_version=config.MODEL_VERSION,
        score=87,
        action_taken=config.ACTION_STEPUP,
        threshold_block=config.THRESHOLD_BLOCK,
        threshold_stepup=config.THRESHOLD_STEPUP,
        explanation_json="[]",
        feature_vector_json="{}",
        latency_ms=87,
    )
    assert ok is True
