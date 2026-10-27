"""Tests for the Phase 4 calibration artifacts and serving temperature.

Run:
    pytest tests/test_calibration.py -v

These read the committed artifacts; they do not refit anything (that is
`scripts/calibrate.py`, ~20 s of ONNX inference).
"""

import json
import os

import numpy as np
import pytest

import config
import inference

CALIB_DIR = os.path.join(config.ARTIFACTS_DIR, "calibration")
TEMPERATURE_PATH = os.path.join(CALIB_DIR, "upi_edge_model_temperature.json")
CALIBRATION_PATH = os.path.join(CALIB_DIR, "upi_edge_model_calibration.json")
RELIABILITY_PATH = os.path.join(CALIB_DIR, "upi_edge_model_reliability.csv")


@pytest.fixture(scope="module")
def calibration() -> dict:
    with open(CALIBRATION_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_calibration_artifacts_exist():
    for path in (TEMPERATURE_PATH, CALIBRATION_PATH, RELIABILITY_PATH):
        assert os.path.isfile(path), path


def test_all_calibration_gates_pass(calibration):
    assert calibration["gates"], "gate table must not be empty"
    failed = [g["gate"] for g in calibration["gates"] if not g["pass"]]
    assert not failed, f"failing calibration gates: {failed}"
    assert calibration["gates_pass"] is True


def test_temperature_matches_calibration_report(calibration):
    with open(TEMPERATURE_PATH, encoding="utf-8") as fh:
        artifact = json.load(fh)
    assert artifact["T"] == pytest.approx(calibration["temperature"]["T"], abs=1e-6)
    # The report and the artifact must agree on whether T is applied at serving.
    assert artifact["applied"] is calibration["temperature_applied_at_serving"]


def test_served_method_is_calibrated_or_documented(calibration):
    """Either T is applied, or the report says which method is served."""
    served = calibration["served_method"]
    assert served in {"uncalibrated", "temperature"}
    applied = calibration["temperature_applied_at_serving"]
    assert served == ("temperature" if applied else "uncalibrated")


def test_temperature_should_apply_threshold():
    assert inference.temperature_should_apply(None) is False
    assert inference.temperature_should_apply(1.0) is False
    assert inference.temperature_should_apply(1.04) is False   # inside the band
    assert inference.temperature_should_apply(1.06) is True
    assert inference.temperature_should_apply(0.90) is True


def test_temperature_shrinks_an_overconfident_positive_score(monkeypatch):
    """A softmax over [0, 3] is softened by T > 1 once the band is exceeded."""
    monkeypatch.setattr(inference, "serving_temperature", lambda: 2.0)

    logits = np.array([[0.0, 3.0]], dtype=np.float32)

    class FakeSession:
        def run(self, _names, _feeds):
            return [logits.copy()]

    features = {
        "sender_embedding": [0.0] * config.EMB_DIM,
        "receiver_embedding": [0.0] * config.EMB_DIM,
        "amount": 100.0,
        "velocity_10min": 1.0,
        "device_change": 0.0,
        "ip_risk": 0.1,
    }

    hot = inference.score_transaction(FakeSession(), features)
    assert inference.temperature_is_applied() is True
    # T=2 halves the logit gap, so the served fraud probability must drop
    assert hot.score < round(1 / (1 + np.exp(-3.0)) * 100)
