"""Unit tests for arcade mode."""
from __future__ import annotations

import pytest


def test_points_for_difficulty():
    from app.arcade import points_for
    assert points_for("easy") == 500
    assert points_for("medium") == 1000
    assert points_for("hard") == 2000


def test_time_bonus_for_difficulty():
    from app.arcade import time_bonus_for
    assert time_bonus_for("easy") == 10
    assert time_bonus_for("medium") == 15
    assert time_bonus_for("hard") == 20


def test_wrong_answer_penalty_constant():
    from app.arcade import WRONG_PENALTY_S
    assert WRONG_PENALTY_S == 10


def test_level_config_caps_at_max_row():
    from app.arcade import level_config, LEVEL_CONFIG
    reset, mix = level_config(99)
    last = LEVEL_CONFIG[-1]
    assert reset == last[0]
    assert mix == {"easy": last[1], "medium": last[2], "hard": last[3]}


def test_level_config_first_row():
    from app.arcade import level_config
    reset, mix = level_config(1)
    assert reset == 60
    assert mix["easy"] == 0.40


def test_weighted_difficulty_with_zero_easy():
    """At level 5+, easy weight is 0 — easy should never be picked."""
    from app.arcade import _weighted_difficulty
    mix = {"easy": 0.0, "medium": 0.3, "hard": 0.7}
    seen = set()
    for _ in range(200):
        seen.add(_weighted_difficulty(mix))
    assert "easy" not in seen
