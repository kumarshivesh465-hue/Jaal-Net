"""Contract tests for the three_viz module (Three.js WebGL visualizations).

three_viz renders self-contained HTML strings, so these checks are string
level and fast — no browser is needed. Band thresholds must follow
config.THRESHOLD_* exactly, and the globe HUD must derive its ring count and
shielded volume from caller-supplied data rather than hard-coded constants.
"""

import pytest

import config
from three_viz import three_globe_html, three_risk_gauge_html


def test_globe_html_is_selfcontained():
    html = three_globe_html().rstrip()
    assert html.startswith("<!DOCTYPE html>")
    assert html.endswith("</html>")
    assert "three.min.js" in html          # Three.js runtime loaded from CDN
    assert "OrbitControls" in html          # rotating camera controls
    assert "hud-panel" in html              # HUD overlay present
    assert "canvas-container" in html


def test_globe_hud_uses_rings_and_stream():
    """Ring count and shielded volume come from the data, not constants."""
    rings = {"RING-001": ["A", "B", "C"], "RING-002": ["D", "E"]}
    txns = [
        {"action": "BLOCK", "amount": 45000.0},
        {"action": "STEP_UP", "amount": 210000.0},
        {"action": "ALLOW", "amount": 890.0},   # not shielded
    ]
    html = three_globe_html(rings_data=rings, stream_txns=txns)
    assert "2 RINGS" in html
    assert "₹2.5L" in html                      # 45,000 + 210,000 = 2.55 lakh


def test_globe_defaults_when_data_absent():
    """Without rings_data/stream_txns the HUD keeps its illustrative defaults."""
    html = three_globe_html()
    assert "3 RINGS" in html
    assert "₹0" in html


def test_globe_rejects_bad_height():
    """Same height precondition rule as graph.cytoscape_html."""
    with pytest.raises(ValueError):
        three_globe_html(height=150)
    with pytest.raises(ValueError):
        three_globe_html(height="540")


def test_gauge_bands_follow_config_thresholds():
    """Gauge labels switch exactly at config.THRESHOLD_* boundaries."""
    cases = [
        (config.THRESHOLD_MONITOR - 5, "SAFE MERCHANT"),
        (config.THRESHOLD_MONITOR,     "WATCHLIST MONITOR"),
        (config.THRESHOLD_STEPUP,      "STEP-UP AUTH REQ"),
        (config.THRESHOLD_BLOCK,       "CRITICAL MULE BLOCK"),
    ]
    for score, expected in cases:
        html = three_risk_gauge_html(score, "MONITOR")
        assert expected in html, f"score {score}: expected {expected!r}"
        assert f"{score:02d}" in html           # the numeric core readout


def test_gauge_colors_by_band():
    colors = {
        10: "#10B981",
        50: "#F59E0B",
        75: "#F97316",
        95: "#EF4444",
    }
    for score, color in colors.items():
        assert color in three_risk_gauge_html(score, "BLOCK")


@pytest.mark.parametrize("bad", [101, -1, 7.5, "90", None, True])
def test_gauge_rejects_out_of_range_score(bad):
    with pytest.raises(ValueError):
        three_risk_gauge_html(bad, "BLOCK")
