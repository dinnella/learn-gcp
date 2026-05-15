"""Unit tests for progressive mode — pure logic where possible."""
from __future__ import annotations

import pytest


def test_next_difficulty_steps_up_on_correct():
    from app.progressive import _next_difficulty
    assert _next_difficulty("easy", True) == "medium"
    assert _next_difficulty("medium", True) == "hard"
    assert _next_difficulty("hard", True) == "hard"


def test_next_difficulty_steps_down_on_wrong():
    from app.progressive import _next_difficulty
    assert _next_difficulty("hard", False) == "medium"
    assert _next_difficulty("medium", False) == "easy"
    assert _next_difficulty("easy", False) == "easy"


def test_points_table():
    from app.progressive import POINTS
    assert POINTS == {"easy": 1, "medium": 2, "hard": 4}


def test_percentile_solo_run_returns_100(fake_db):
    from app.progressive import _percentile
    assert _percentile(0) == 100.0


def test_percentile_after_some_scores(fake_db):
    from app.db import PROGRESSIVE_SCORES
    db = fake_db
    db._store[(PROGRESSIVE_SCORES, "a")] = {"score_total": 10}
    db._store[(PROGRESSIVE_SCORES, "b")] = {"score_total": 20}
    db._store[(PROGRESSIVE_SCORES, "c")] = {"score_total": 30}
    from app.progressive import _percentile
    # Score 20 beats or ties 2 of 3 => 66.7%
    assert _percentile(20) == 66.7


def _seed_qs(db, exams=("architect",), difficulties=("easy", "medium", "hard"), per=2):
    """Seed N questions per (exam, difficulty)."""
    n = 0
    for exam in exams:
        for diff in difficulties:
            for i in range(per):
                qid = f"{exam}-{diff}-{i:03d}"
                db.seed_question(qid, {
                    "id": qid, "exam": exam, "section": f"{exam.upper()}-1.1",
                    "difficulty": diff, "text": f"Q {qid}",
                    "options": ["A", "B", "C", "D"], "correct_index": 0,
                    "explanation": "x", "doc_links": [],
                })
                n += 1
    return n


def test_pick_one_question_filters_by_difficulty(fake_db):
    _seed_qs(fake_db)
    from app.questions import pick_one_question
    q = pick_one_question(["architect"], "hard", [])
    assert q is not None
    assert q.difficulty == "hard"


def test_pick_one_question_returns_none_when_exhausted(fake_db):
    _seed_qs(fake_db, difficulties=("easy",), per=1)
    from app.questions import pick_one_question
    q = pick_one_question(["architect"], "hard", [])
    assert q is None


def test_count_questions_excludes_served(fake_db):
    _seed_qs(fake_db, difficulties=("hard",), per=3)
    from app.questions import count_questions
    assert count_questions(["architect"], "hard", []) == 3
    assert count_questions(["architect"], "hard", ["architect-hard-000", "architect-hard-001"]) == 1


def test_list_exams_is_dynamic(fake_db):
    _seed_qs(fake_db, exams=("architect", "devops", "aws-saa"))
    from app.questions import list_exams
    assert list_exams() == ["architect", "aws-saa", "devops"]
