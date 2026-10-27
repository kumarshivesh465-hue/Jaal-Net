"""Boundary tests for styles.py per CONTRACTS.md section 4."""

import pytest

from styles import DARK_THEME_CSS, row_class, score_class, score_color


@pytest.mark.parametrize("score,expected", [
    (0,   "score-safe"),
    (29,  "score-safe"),
    (30,  "score-monitor"),
    (69,  "score-monitor"),
    (70,  "score-stepup"),
    (89,  "score-stepup"),
    (90,  "score-block"),
    (100, "score-block"),
])
def test_score_class_boundaries(score, expected):
    assert score_class(score) == expected


@pytest.mark.parametrize("score", [-1, 101, 200])
def test_score_class_out_of_range(score):
    with pytest.raises(ValueError):
        score_class(score)


@pytest.mark.parametrize("score,expected", [
    (0,   "safe"),
    (29,  "safe"),
    (30,  "monitor"),
    (69,  "monitor"),
    (70,  "stepup"),
    (89,  "stepup"),
    (90,  "block"),
    (100, "block"),
])
def test_row_class_boundaries(score, expected):
    assert row_class(score) == expected


@pytest.mark.parametrize("score", [-1, 101])
def test_row_class_out_of_range(score):
    with pytest.raises(ValueError):
        row_class(score)


def test_score_color_returns_hex():
    for score in (0, 30, 70, 90, 100):
        color = score_color(score)
        assert color.startswith("#")
        assert len(color) == 7


def test_score_color_matches_score_class():
    """Colors must be consistent with class boundaries."""
    assert score_color(10) == score_color(20)
    assert score_color(10) != score_color(50)
    assert score_color(50) != score_color(80)
    assert score_color(80) != score_color(95)


def test_css_is_wrapped_in_style_tag():
    assert "<style>" in DARK_THEME_CSS
    assert "</style>" in DARK_THEME_CSS
