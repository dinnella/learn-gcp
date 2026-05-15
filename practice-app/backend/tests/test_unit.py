"""Unit tests — pure logic, no I/O."""
from __future__ import annotations

import pytest

from app.sessions import PASS_THRESHOLD, WEAK_SECTION_THRESHOLD, _grade, _suggested_action
from app.section_titles import title_for
from app.models import QuestionForClient


# ---------------------------------------------------------------------------
# _grade
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pct,expected", [
    (100.0, "A"), (90.0, "A"),
    (89.9,  "B"), (80.0, "B"),
    (79.9,  "C"), (70.0, "C"),
    (69.9,  "D"), (60.0, "D"),
    (59.9,  "F"), (0.0,  "F"),
])
def test_grade_bands(pct, expected):
    assert _grade(pct) == expected


def test_pass_threshold_boundary():
    assert _grade(PASS_THRESHOLD) == "C"       # exactly 70 → passes mock, grade C
    assert _grade(PASS_THRESHOLD - 0.1) == "D" # just below → fail


# ---------------------------------------------------------------------------
# _suggested_action
# ---------------------------------------------------------------------------

def test_suggested_action_low():
    action = _suggested_action(40.0)
    assert "Foundational" in action

def test_suggested_action_mid():
    action = _suggested_action(60.0)
    assert "focus" in action.lower()

def test_suggested_action_strong():
    action = _suggested_action(85.0)
    assert "hard" in action.lower()


# ---------------------------------------------------------------------------
# title_for — case normalisation (DevOps-x.y vs DEVOPS-x.y)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code,expected_fragment", [
    ("DEVOPS-1.1",   "SRE culture"),
    ("devops-1.1",   "SRE culture"),   # lowercase
    ("DevOps-1.1",   "SRE culture"),   # mixed — exactly how the seed stores it
    ("DEVOPS-2.1",   "CI/CD"),
    ("PCA-1.1",      "Compliance"),
    ("pca-1.1",      "Compliance"),
    ("UNKNOWN-9.9",  "UNKNOWN-9.9"),   # unknown code falls back to itself
])
def test_title_for(code, expected_fragment):
    assert expected_fragment in title_for(code)


# ---------------------------------------------------------------------------
# correct_index never leaks through QuestionForClient
# ---------------------------------------------------------------------------

def test_question_for_client_has_no_correct_index():
    q = QuestionForClient(
        id="q1", exam="architect", section="PCA-1.1", section_title="Compliance",
        difficulty="medium", text="?", options=["A", "B", "C", "D"],
    )
    assert not hasattr(q, "correct_index")
    assert "correct_index" not in q.model_dump()


def test_question_for_client_strips_extra_fields():
    """Pydantic should not pass extra fields through to the client model."""
    data = dict(
        id="q1", exam="architect", section="PCA-1.1", section_title="Compliance",
        difficulty="medium", text="?", options=["A", "B", "C", "D"],
        correct_index=2, explanation="secret",
    )
    # model_validate with extra fields should not expose correct_index
    q = QuestionForClient.model_validate(data)
    assert "correct_index" not in q.model_dump()
