"""Progressive game mode: adaptive difficulty, 3 strikes, weighted scoring."""
from __future__ import annotations

import random
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from .db import PROGRESSIVE_SCORES, SESSIONS, get_db
from .models import (
    ProgressiveLeaderboardResponse,
    ProgressiveScoreEntry,
    ProgressiveSessionSummary,
)
from .questions import (
    count_questions,
    get_question_full,
    list_exams,
    pick_one_question,
)


POINTS = {"easy": 1, "medium": 2, "hard": 4}
LADDER = ["easy", "medium", "hard"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_difficulty(current: str, was_correct: bool) -> str:
    i = LADDER.index(current) if current in LADDER else 1
    if was_correct:
        return LADDER[min(i + 1, 2)]
    return LADDER[max(i - 1, 0)]


def _shuffled_options_for(qid: str) -> list[int]:
    full = get_question_full(qid)
    n = len(full["options"]) if full else 4
    perm = list(range(n))
    random.shuffle(perm)
    return perm


def _question_for_client_dict(q, order: list[int]) -> dict:
    """Build a QuestionForClient-shaped dict with options reordered."""
    from .section_titles import title_for
    options = q.options
    if order and len(order) == len(options):
        options = [options[i] for i in order]
    return {
        "id": q.id,
        "exam": q.exam,
        "section": q.section,
        "section_title": title_for(q.section),
        "difficulty": q.difficulty,
        "text": q.text,
        "options": options,
    }


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def start_progressive_session(player_name: str | None, max_strikes: int) -> dict:
    exams = list_exams()
    if not exams:
        raise ValueError("question bank is empty")

    # First question is always medium; fall back if no medium available.
    first_q = pick_one_question(exams, "medium", [])
    current_difficulty = "medium"
    if first_q is None:
        for fb in ("easy", "hard"):
            first_q = pick_one_question(exams, fb, [])
            if first_q:
                current_difficulty = fb
                break
    if first_q is None:
        raise ValueError("no questions available")

    sid = uuid.uuid4().hex[:12]
    order = _shuffled_options_for(first_q.id)
    doc = {
        "mode": "progressive",
        "exams": exams,
        "started_at": _now_iso(),
        "finished_at": None,
        "player_name": player_name,
        "max_strikes": max_strikes,
        "strikes": 0,
        "current_difficulty": current_difficulty,
        "current_qid": first_q.id,
        "served_qids": [first_q.id],
        "option_orders": {first_q.id: order},
        "answers": [],
        "score_total": 0,
        "current_streak": 0,
        "max_streak": 0,
        "ended_reason": None,
    }
    get_db().collection(SESSIONS).document(sid).set(doc)
    return {
        "session_id": sid,
        "max_strikes": max_strikes,
        "first_question": _question_for_client_dict(first_q, order),
    }


def _load(sid: str) -> dict | None:
    snap = get_db().collection(SESSIONS).document(sid).get()
    return snap.to_dict() if snap.exists else None


def record_progressive_answer(
    sid: str, question_id: str, selected_index: int, confidence: str
) -> dict:
    db = get_db()
    ref = db.collection(SESSIONS).document(sid)
    snap = ref.get()
    if not snap.exists:
        raise KeyError("session not found")
    session = snap.to_dict()
    if session.get("mode") != "progressive":
        raise ValueError("not a progressive session")
    if session.get("finished_at"):
        raise ValueError("session already finished")
    if session.get("current_qid") != question_id:
        raise ValueError("question_id does not match the current served question")

    full = get_question_full(question_id)
    if full is None:
        raise KeyError("question not found")

    canonical_correct = full["correct_index"]
    order = (session.get("option_orders") or {}).get(question_id) or []
    if order and 0 <= selected_index < len(order):
        canonical_selected = order[selected_index]
    else:
        canonical_selected = selected_index
    is_correct = canonical_selected == canonical_correct
    if order and canonical_correct in order:
        display_correct = order.index(canonical_correct)
    else:
        display_correct = canonical_correct

    diff = full.get("difficulty", "medium")
    points = POINTS.get(diff, 0) if is_correct else 0

    new_answer = {
        "question_id": question_id,
        "exam": full.get("exam"),
        "difficulty": diff,
        "selected_index": selected_index,
        "correct_index": display_correct,
        "correct": is_correct,
        "points_awarded": points,
        "confidence": confidence,
        "ts": _now_iso(),
    }

    strikes = int(session.get("strikes", 0)) + (0 if is_correct else 1)
    streak = int(session.get("current_streak", 0)) + 1 if is_correct else 0
    max_streak = max(int(session.get("max_streak", 0)), streak)
    score_total = int(session.get("score_total", 0)) + points
    next_difficulty = _next_difficulty(session.get("current_difficulty", "medium"), is_correct)

    answers = list(session.get("answers", [])) + [new_answer]
    served = list(session.get("served_qids", []))
    option_orders = dict(session.get("option_orders", {}))
    max_strikes = int(session.get("max_strikes", 3))

    update: dict = {
        "answers": answers,
        "strikes": strikes,
        "current_streak": streak,
        "max_streak": max_streak,
        "score_total": score_total,
        "current_difficulty": next_difficulty,
    }

    ended = False
    ended_reason: str | None = None
    next_q_payload = None

    if strikes >= max_strikes:
        ended = True
        ended_reason = "strikes"
    elif count_questions(session["exams"], "hard", served) == 0:
        ended = True
        ended_reason = "hard_exhausted"
    else:
        # Pick next question at next_difficulty with fallback.
        nq = pick_one_question(session["exams"], next_difficulty, served)
        if nq is None:
            for fb in _fallback_order(next_difficulty):
                nq = pick_one_question(session["exams"], fb, served)
                if nq:
                    update["current_difficulty"] = fb
                    next_difficulty = fb
                    break
        if nq is None:
            ended = True
            ended_reason = "hard_exhausted"
        else:
            served.append(nq.id)
            order2 = _shuffled_options_for(nq.id)
            option_orders[nq.id] = order2
            update["served_qids"] = served
            update["option_orders"] = option_orders
            update["current_qid"] = nq.id
            next_q_payload = _question_for_client_dict(nq, order2)

    if ended:
        update["finished_at"] = _now_iso()
        update["ended_reason"] = ended_reason

    ref.update(update)

    answered = len(answers)
    correct = sum(1 for a in answers if a["correct"])
    return {
        "correct": is_correct,
        "correct_index": display_correct,
        "points_awarded": points,
        "explanation": full.get("explanation"),
        "doc_links": full.get("doc_links", []),
        "next_question": next_q_payload,
        "progress": {
            "answered": answered,
            "correct": correct,
            "strikes": strikes,
            "max_strikes": max_strikes,
            "score_total": score_total,
            "current_difficulty": next_difficulty,
            "max_streak": max_streak,
            "current_streak": streak,
        },
        "ended": ended,
        "ended_reason": ended_reason,
    }


def _fallback_order(target: str) -> list[str]:
    if target == "hard":
        return ["medium", "easy"]
    if target == "medium":
        return ["easy", "hard"]
    return ["medium", "hard"]


def abandon_progressive_session(sid: str) -> ProgressiveSessionSummary:
    db = get_db()
    ref = db.collection(SESSIONS).document(sid)
    snap = ref.get()
    if not snap.exists:
        raise KeyError("session not found")
    session = snap.to_dict()
    if session.get("mode") != "progressive":
        raise ValueError("not a progressive session")
    finished = session.get("finished_at")
    if finished and session.get("ended_reason") != "abandoned":
        raise ValueError("session already finished")
    if not finished:
        ref.update({
            "finished_at": _now_iso(),
            "ended_reason": "abandoned",
        })
    summary = progressive_summary(sid)
    assert summary is not None
    return summary


def progressive_summary(sid: str) -> ProgressiveSessionSummary | None:
    s = _load(sid)
    if s is None or s.get("mode") != "progressive":
        return None
    answers = s.get("answers", [])
    answered = len(answers)
    correct = sum(1 for a in answers if a["correct"])
    accuracy_pct = round(100 * correct / answered, 1) if answered else 0.0

    per_difficulty: dict[str, dict] = {
        "easy": {"served": 0, "correct": 0, "points": 0},
        "medium": {"served": 0, "correct": 0, "points": 0},
        "hard": {"served": 0, "correct": 0, "points": 0},
    }
    per_exam: dict[str, dict] = defaultdict(
        lambda: {"served": 0, "correct": 0, "points": 0}
    )
    for a in answers:
        d = a.get("difficulty", "medium")
        e = a.get("exam", "?")
        per_difficulty.setdefault(d, {"served": 0, "correct": 0, "points": 0})
        per_difficulty[d]["served"] += 1
        per_exam[e]["served"] += 1
        if a["correct"]:
            per_difficulty[d]["correct"] += 1
            per_exam[e]["correct"] += 1
            per_difficulty[d]["points"] += int(a.get("points_awarded", 0))
            per_exam[e]["points"] += int(a.get("points_awarded", 0))

    score_total = int(s.get("score_total", 0))
    percentile: float | None = None
    if s.get("finished_at") and s.get("ended_reason") != "abandoned":
        percentile = _percentile(score_total)

    return ProgressiveSessionSummary(
        id=sid,
        exams=list(s.get("exams", [])),
        started_at=s["started_at"],
        finished_at=s.get("finished_at"),
        answered=answered,
        correct=correct,
        accuracy_pct=accuracy_pct,
        max_streak=int(s.get("max_streak", 0)),
        score_total=score_total,
        strikes=int(s.get("strikes", 0)),
        max_strikes=int(s.get("max_strikes", 3)),
        ended_reason=s.get("ended_reason"),
        per_difficulty=per_difficulty,
        per_exam=dict(per_exam),
        percentile=percentile,
        player_name=s.get("player_name"),
    )


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

def _all_scores() -> list[int]:
    db = get_db()
    return [int(d.to_dict().get("score_total", 0))
            for d in db.collection(PROGRESSIVE_SCORES).stream()]


def _percentile(score_total: int) -> float:
    scores = _all_scores()
    if not scores:
        return 100.0
    beaten = sum(1 for s in scores if score_total >= s)
    return round(100.0 * beaten / len(scores), 1)


def submit_progressive_score(sid: str, player_name: str) -> ProgressiveScoreEntry:
    db = get_db()
    s = _load(sid)
    if s is None or s.get("mode") != "progressive":
        raise KeyError("session not found")
    if not s.get("finished_at"):
        raise ValueError("session not finished")
    if s.get("ended_reason") == "abandoned":
        raise ValueError("Abandoned runs cannot be submitted")

    answers = s.get("answers", [])
    answered = len(answers)
    correct = sum(1 for a in answers if a["correct"])

    diff_mix: dict[str, int] = defaultdict(int)
    per_exam: dict[str, dict] = defaultdict(
        lambda: {"served": 0, "correct": 0, "points": 0}
    )
    for a in answers:
        diff_mix[a.get("difficulty", "medium")] += 1
        e = a.get("exam", "?")
        per_exam[e]["served"] += 1
        if a["correct"]:
            per_exam[e]["correct"] += 1
            per_exam[e]["points"] += int(a.get("points_awarded", 0))

    entry = ProgressiveScoreEntry(
        player_name=(player_name.strip()[:32] or "anonymous"),
        score_total=int(s.get("score_total", 0)),
        answered=answered,
        correct=correct,
        max_streak=int(s.get("max_streak", 0)),
        difficulty_mix=dict(diff_mix),
        per_exam=dict(per_exam),
        ended_reason=s.get("ended_reason"),
        finished_at=s["finished_at"],
        session_id=sid,
    )
    db.collection(PROGRESSIVE_SCORES).document(sid).set(entry.model_dump())
    db.collection(SESSIONS).document(sid).update({"player_name": entry.player_name})
    return entry


def progressive_leaderboard(limit: int = 20) -> ProgressiveLeaderboardResponse:
    db = get_db()
    docs = list(db.collection(PROGRESSIVE_SCORES).stream())
    entries = [ProgressiveScoreEntry(**d.to_dict()) for d in docs]
    entries.sort(key=lambda e: (-e.score_total, -e.correct, e.finished_at))
    return ProgressiveLeaderboardResponse(
        entries=entries[:limit],
        total_runs=len(entries),
    )
