"""Smoke test: app.py imports cleanly and config is wired.

Does not start Streamlit. Uses import-time checks.
"""


def test_app_module_imports():
    import app  # noqa: F401


def test_config_thresholds_ordered():
    from config import THRESHOLD_BLOCK, THRESHOLD_MONITOR, THRESHOLD_STEPUP

    assert THRESHOLD_MONITOR < THRESHOLD_STEPUP < THRESHOLD_BLOCK


def test_config_ring_ids_match_data_rings():
    from config import RING_IDS
    from data import RINGS

    assert set(RING_IDS) == set(RINGS.keys())


def test_config_model_version_matches_registry_string():
    from config import MODEL_VERSION

    assert MODEL_VERSION == "TGAT+SAGE-v1.2"


def test_config_edge_types_present():
    from config import EDGE_TYPES

    assert set(EDGE_TYPES) == {"normal", "ring", "layering", "circular"}


def test_config_actions_match_schema_enum():
    from config import ACTIONS

    assert ACTIONS == ["ALLOW", "MONITOR", "STEP_UP", "BLOCK"]
