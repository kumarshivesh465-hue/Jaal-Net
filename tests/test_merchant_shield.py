"""Unit and contract tests for JaalNet MerchantShield pre-flight counterparty protection."""

from fastapi.testclient import TestClient
import pytest

import backend
import merchant_shield


@pytest.fixture
def client():
    return TestClient(backend.app)


def test_merchant_shield_hop0_mule():
    """Verify that a confirmed mule ring member is rejected immediately."""
    res = merchant_shield.evaluate_counterparty_shield(
        counterparty="L***7350",
        amount_inr=240000.0,
        direction="INCOMING",
        merchant_id="MERCHANT_RAMESH_KIRANA",
    )
    assert res["verdict"] == "TAINTED_MULE_HAZARD_REJECT"
    assert res["action"] == "REJECT_PAYMENT_IMMEDIATELY"
    assert res["lien_hazard_score"] >= 90
    assert res["tainted_hops"] == 0
    assert "shield_certificate" in res
    assert res["shield_certificate"]["cert_id"].startswith("MS-")
    assert res["shield_certificate"]["status"] == "VALID"


def test_merchant_shield_hop1_partner():
    """Verify that a 1-hop counterparty to a mule is blocked or escrowed."""
    res = merchant_shield.evaluate_counterparty_shield(
        counterparty="P***8522",
        amount_inr=45000.0,
        direction="INCOMING",
        merchant_id="MERCHANT_RAMESH_KIRANA",
    )
    assert res["verdict"] == "HIGH_HAZARD_BLOCKED"
    assert res["action"] == "REJECT_OR_ESCROW"
    assert res["lien_hazard_score"] >= 75
    assert res["tainted_hops"] == 1
    assert res["recommended_hold_hours"] >= 48


def test_merchant_shield_clean_account():
    """Verify that a clean benign account receives an instant safe pass."""
    res = merchant_shield.evaluate_counterparty_shield(
        counterparty="ACC_CLEAN_BENIGN_001",
        amount_inr=50.0,
        direction="INCOMING",
        merchant_id="MERCHANT_RAMESH_KIRANA",
    )
    assert res["verdict"] == "CLEAN_SAFE_TO_ACCEPT"
    assert res["action"] == "ACCEPT_INSTANT"
    assert res["lien_hazard_score"] < 25
    assert res["recommended_hold_hours"] == 0
    assert "clean" in res["advisory"].lower()


def test_merchant_shield_api_endpoint(client):
    """Test POST /merchant/shield-check via FastAPI TestClient."""
    payload = {
        "merchant_id": "MERCHANT_SHARMA_ELECTRONICS",
        "counterparty": "L***7350",
        "amount": 89000.0,
        "direction": "INCOMING",
        "category": "CONSUMER_ELECTRONICS",
    }
    response = client.post("/merchant/shield-check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["merchant_id"] == "MERCHANT_SHARMA_ELECTRONICS"
    assert data["verdict"] == "TAINTED_MULE_HAZARD_REJECT"
    assert data["lien_hazard_score"] >= 90
    assert "shield_certificate" in data
    assert "SHA256:" in data["shield_certificate"]["signature"]


def test_merchant_shield_vendor_payout_clean(client):
    """Test vendor payout check for clean supplier."""
    payload = {
        "merchant_id": "MERCHANT_MODERN_AGRI",
        "counterparty": "SUPPLIER_FERTILIZER_CLEAN",
        "amount": 15000.0,
        "direction": "OUTGOING",
        "category": "B2B_SUPPLIES",
    }
    response = client.post("/merchant/shield-check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["direction"] == "OUTGOING"
    assert data["verdict"] == "CLEAN_SAFE_TO_ACCEPT"
    assert data["action"] == "ACCEPT_INSTANT"
