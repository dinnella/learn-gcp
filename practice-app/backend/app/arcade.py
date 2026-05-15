"""Arcade game mode: rapid-fire timed mode with level-ups."""
from __future__ import annotations

import random
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from .db import ARCADE_SCORES, SESSIONS, get_db
from .models import (
    ArcadeLeaderboardResponse,
    ArcadeScoreEntry,
    ArcadeSessionSummary,
)
from .questions import get_question_full, list_exams, pick_one_question
from .section_titles import title_for


# (reset_seconds, easy_w, medium_w, hard_w) — tunable post user-testing
LEVEL_CONFIG = [
    (60, 0.40, 0.50, 0.10),
    (55, 0.20, 0.55, 0.25),
    (50, 0.10, 0.50, 0.40),
    (45, 0.05, 0.40, 0.55),
    (45, 0.00, 0.30, 0.70),
]

POINTS = {"easy": 500, "medium": 1000, "hard": 2000}
TIME_BONUS = {"easy": 10, "medium": 15, "hard": 20}
ELAPSED_CLAMP_MS = 60_000
WRONG_PENALTY_S = 10  # Each wrong answer also costs 10s on top of elapsed.
LEVEL_UP_THRESHOLD = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def points_for(diff: str) -> int:
    return POINTS.get(diff, 0)


def time_bonus_for(diff: str) -> int:
    return TIME_BONUS.get(diff, 0)


def level_config(level: int) -> tuple[int, dict[str, float]]:
    row = LEVEL_CONFIG[min(max(level, 1) - 1, len(LEVEL_CONFIG) - 1)]
    return row[0], {"easy": row[1], "medium": row[2], "hard": row[3]}


def _weighted_difficulty(mix: dict[str, float]) -> str:
    items = list(mix.items())
    weights = [w for _, w in items]
    total = sum(weights)
    if total <= 0:
        return "medium"
    r = random.random() * total
    acc = 0.0
    for diff, w in items:
        acc += w
        if r <= acc:
            return diff
    return items[-1][0]


def _shuffled_options_for(qid: str) -> list[int]:
    full = get_question_full(qid)
    n = len(full["options"]) if full else 4
    perm = list(range(n))
    random.shuffle(perm)
    return perm


def _arcade_question_payload(q, order: list[int]) -> dict:
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
        "points_if_correct": points_for(q.difficulty),
        "time_bonus_seconds": time_bonus_for(q.difficulty),
    }


def pick_next_arcade_question(session: dict):
    """Sample a question for the current level. Returns Question or None."""
    _, mix = level_config(int(session.get("level", 1)))
    served = list(session.get("served_qids", []))
    exams = session.get("exams", [])

    # Try up to 3 weighted samples
    for _ in range(3):
        target = _weighted_difficulty(mix)
        q = pick_one_question(exams, target, served)
        if q is not None:
            return q

    # Fallback: any unserved
    return pick_one_question(exams, None, served)


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def start_arcade_session(player_name: str | None, starting_seconds: int) -> dict:
    exams = list_exams()
    if not exams:
        raise ValueError("question bank is empty")

    pseudo_session = {"level": 1, "served_qids": [], "exams": exams}
    first_q = pick_next_arcade_question(pseudo_session)
    if first_q is None:
        raise ValueError("no questions available")

    sid = uuid.uuid4().hex[:12]
    order = _shuffled_options_for(first_q.id)
    starting_ms = starting_seconds * 1000
    doc = {
        "mode": "arcade",
        "exams": exams,
        "started_at": _now_iso(),
        "finished_at": None,
        "player_name": player_name,
        "starting_seconds": starting_seconds,
        "time_remaining_ms": starting_ms,
        "last_tick_at": _now_iso(),
        "level": 1,
        "correct_in_level": 0,
        "correct_total": 0,
        "answered_total": 0,
        "max_streak": 0,
        "current_streak": 0,
        "score_total": 0,
        "longest_combo_pts": 0,
        "is_paused": False,
        "paused_at": None,
        "level_up_pending": False,
        "served_qids": [first_q.id],
        "current_qid": first_q.id,
        "option_orders": {first_q.id: order},
        "answers": [],
        "ended_reason": None,
    }
    get_db().collection(SESSIONS).document(sid).set(doc)
    return {
        "session_id": sid,
        "starting_seconds": starting_seconds,
        "time_remaining_ms": starting_ms,
        "first_question": _arcade_question_payload(first_q, order),
    }


def _load(sid: str) -> dict | None:
    snap = get_db().collection(SESSIONS).document(sid).get()
    return snap.to_dict() if snap.exists else None


def record_arcade_answer(
    sid: str,
    question_id: str,
    selected_index: int,
    confidence: str,
    client_elapsed_ms: int,
) -> dict:
    db = get_db()
    ref = db.collection(SESSIONS).document(sid)
    snap = ref.get()
    if not snap.exists:
        raise KeyError("session not found")
    session = snap.to_dict()
    if session.get("mode") != "arcade":
        raise ValueError("not an arcade session")
    if session.get("finished_at"):
        raise ValueError("session already finished")
    if session.get("level_up_pending") or session.get("is_paused"):
        raise ValueError("level-up pending — call /continue first")
    if session.get("current_qid") != question_id:
        raise ValueError("question_id does not match the current served question")

    full = get_question_full(question_id)
    if full is None:
        raise KeyError("question not found")

    # Debit elapsed time (clamped).
    elapsed = max(0, min(client_elapsed_ms, ELAPSED_CLAMP_MS))
    time_remaining_ms = int(session.get("time_remaining_ms", 0)) - elapsed

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

    # Time-out check (no credit for this answer).
    if time_remaining_ms <= 0:
        time_remaining_ms = 0
        new_answer = {
            "question_id": question_id,
            "exam": full.get("exam"),
            "difficulty": diff,
            "selected_index": selected_index,
            "correct_index": display_correct,
            "correct": False,
            "points_awarded": 0,
            "time_bonus_seconds": 0,
            "confidence": confidence,
            "ts": _now_iso(),
            "ended_during": True,
        }
        answers = list(session.get("answers", [])) + [new_answer]
        ref.update({
            "answers": answers,
            "answered_total": int(session.get("answered_total", 0)) + 1,
            "time_remaining_ms": 0,
            "last_tick_at": _now_iso(),
            "finished_at": _now_iso(),
            "ended_reason": "time",
        })
        return {
            "correct": False,
            "correct_index": display_correct,
            "points_awarded": 0,
            "time_bonus_seconds": 0,
            "time_penalty_seconds": 0,
            "time_remaining_ms": 0,
            "score_total": int(session.get("score_total", 0)),
            "correct_total": int(session.get("correct_total", 0)),
            "correct_in_level": int(session.get("correct_in_level", 0)),
            "level": int(session.get("level", 1)),
            "max_streak": int(session.get("max_streak", 0)),
            "current_streak": int(session.get("current_streak", 0)),
            "explanation": full.get("explanation"),
            "doc_links": full.get("doc_links", []),
            "next_question": None,
            "level_up_pending": False,
            "ended": True,
            "ended_reason": "time",
        }

    # Grade and update.
    points = points_for(diff) if is_correct else 0
    bonus_s = time_bonus_for(diff) if is_correct else 0
    penalty_s = 0 if is_correct else WRONG_PENALTY_S
    if is_correct:
        time_remaining_ms += bonus_s * 1000
    else:
        time_remaining_ms -= penalty_s * 1000
        if time_remaining_ms < 0:
            time_remaining_ms = 0

    score_total = int(session.get("score_total", 0)) + points
    answered_total = int(session.get("answered_total", 0)) + 1
    correct_total = int(session.get("correct_total", 0)) + (1 if is_correct else 0)
    correct_in_level = int(session.get("correct_in_level", 0)) + (1 if is_correct else 0)
    streak = int(session.get("current_streak", 0)) + 1 if is_correct else 0
    max_streak = max(int(session.get("max_streak", 0)), streak)
    longest_combo_pts = max(int(session.get("longest_combo_pts", 0)), points)

    new_answer = {
        "question_id": question_id,
        "exam": full.get("exam"),
        "difficulty": diff,
        "selected_index": selected_index,
        "correct_index": display_correct,
        "correct": is_correct,
        "points_awarded": points,
        "time_bonus_seconds": bonus_s,
        "time_penalty_seconds": penalty_s,
        "confidence": confidence,
        "ts": _now_iso(),
    }
    answers = list(session.get("answers", [])) + [new_answer]

    update: dict = {
        "answers": answers,
        "answered_total": answered_total,
        "correct_total": correct_total,
        "correct_in_level": correct_in_level,
        "current_streak": streak,
        "max_streak": max_streak,
        "score_total": score_total,
        "longest_combo_pts": longest_combo_pts,
        "time_remaining_ms": time_remaining_ms,
        "last_tick_at": _now_iso(),
    }

    level = int(session.get("level", 1))
    next_q_payload = None
    level_up_pending = False
    ended = False
    ended_reason: str | None = None

    if correct_in_level >= LEVEL_UP_THRESHOLD:
        level_up_pending = True
        update["level_up_pending"] = True
        update["is_paused"] = True
        update["paused_at"] = _now_iso()
        update["current_qid"] = None
    elif time_remaining_ms <= 0:
        # Wrong-answer penalty drained the clock.
        ended = True
        ended_reason = "time"
        update["finished_at"] = _now_iso()
        update["ended_reason"] = "time"
        update["current_qid"] = None
    else:
        # Build session-shaped dict to feed the picker.
        served = list(session.get("served_qids", []))
        next_q = pick_next_arcade_question({
            "level": level,
            "served_qids": served,
            "exams": session.get("exams", []),
        })
        if next_q is None:
            ended = True
            ended_reason = "exhausted"
            update["finished_at"] = _now_iso()
            update["ended_reason"] = "exhausted"
            update["current_qid"] = None
        else:
            served.append(next_q.id)
            order2 = _shuffled_options_for(next_q.id)
            option_orders = dict(session.get("option_orders", {}))
            option_orders[next_q.id] = order2
            update["served_qids"] = served
            update["option_orders"] = option_orders
            update["current_qid"] = next_q.id
            next_q_payload = _arcade_question_payload(next_q, order2)

    ref.update(update)

    return {
        "correct": is_correct,
        "correct_index": display_correct,
        "points_awarded": points,
        "time_bonus_seconds": bonus_s,
        "time_penalty_seconds": penalty_s,
        "time_remaining_ms": time_remaining_ms,
        "score_total": score_total,
        "correct_total": correct_total,
        "correct_in_level": correct_in_level,
        "level": level,
        "max_streak": max_streak,
        "current_streak": streak,
        "explanation": full.get("explanation"),
        "doc_links": full.get("doc_links", []),
        "next_question": next_q_payload,
        "level_up_pending": level_up_pending,
        "ended": ended,
        "ended_reason": ended_reason,
    }


def continue_arcade_session(sid: str) -> dict:
    db = get_db()
    ref = db.collection(SESSIONS).document(sid)
    snap = ref.get()
    if not snap.exists:
        raise KeyError("session not found")
    session = snap.to_dict()
    if session.get("mode") != "arcade":
        raise ValueError("not an arcade session")
    if session.get("finished_at"):
        raise ValueError("session already finished")
    if not session.get("level_up_pending"):
        raise ValueError("no level-up pending")

    new_level = int(session.get("level", 1)) + 1
    reset_seconds, _ = level_config(new_level)
    time_remaining_ms = reset_seconds * 1000

    served = list(session.get("served_qids", []))
    next_q = pick_next_arcade_question({
        "level": new_level,
        "served_qids": served,
        "exams": session.get("exams", []),
    })
    if next_q is None:
        ref.update({
            "finished_at": _now_iso(),
            "ended_reason": "exhausted",
            "level_up_pending": False,
            "is_paused": False,
            "level": new_level,
            "correct_in_level": 0,
            "time_remaining_ms": time_remaining_ms,
            "current_qid": None,
        })
        raise ValueError("question pool exhausted")

    order = _shuffled_options_for(next_q.id)
    option_orders = dict(session.get("option_orders", {}))
    option_orders[next_q.id] = order
    served.append(next_q.id)

    ref.update({
        "level": new_level,
        "correct_in_level": 0,
        "is_paused": False,
        "level_up_pending": False,
        "time_remaining_ms": time_remaining_ms,
        "last_tick_at": _now_iso(),
        "served_qids": served,
        "option_orders": option_orders,
        "current_qid": next_q.id,
    })
    return {
        "level": new_level,
        "time_remaining_ms": time_remaining_ms,
        "next_question": _arcade_question_payload(next_q, order),
    }


def abandon_arcade_session(sid: str) -> ArcadeSessionSummary:
    db = get_db()
    ref = db.collection(SESSIONS).document(sid)
    snap = ref.get()
    if not snap.exists:
        raise KeyError("session not found")
    session = snap.to_dict()
    if session.get("mode") != "arcade":
        raise ValueError("not an arcade session")
    finished = session.get("finished_at")
    if finished and session.get("ended_reason") != "abandoned":
        raise ValueError("session already finished")
    if not finished:
        ref.update({
            "finished_at": _now_iso(),
            "ended_reason": "abandoned",
            "is_paused": True,
        })
    summary = arcade_summary(sid)
    assert summary is not None
    return summary


def arcade_summary(sid: str) -> ArcadeSessionSummary | None:
    s = _load(sid)
    if s is None or s.get("mode") != "arcade":
        return None
    answers = s.get("answers", [])
    answered_total = int(s.get("answered_total", len(answers)))
    correct_total = int(s.get("correct_total",
                              sum(1 for a in answers if a["correct"])))
    accuracy_pct = round(100 * correct_total / answered_total, 1) if answered_total else 0.0

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

    duration_seconds: int | None = None
    started = s.get("started_at")
    finished = s.get("finished_at")
    if started and finished:
        try:
            t0 = datetime.fromisoformat(started)
            t1 = datetime.fromisoformat(finished)
            duration_seconds = int((t1 - t0).total_seconds())
        except Exception:
            duration_seconds = None

    return ArcadeSessionSummary(
        id=sid,
        started_at=started,
        finished_at=finished,
        score_total=int(s.get("score_total", 0)),
        level_reached=int(s.get("level", 1)),
        correct_total=correct_total,
        answered_total=answered_total,
        accuracy_pct=accuracy_pct,
        max_streak=int(s.get("max_streak", 0)),
        duration_seconds=duration_seconds,
        per_difficulty=per_difficulty,
        per_exam=dict(per_exam),
        ended_reason=s.get("ended_reason"),
        player_name=s.get("player_name"),
    )


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

def submit_arcade_score(sid: str, player_name: str) -> ArcadeScoreEntry:
    db = get_db()
    s = _load(sid)
    if s is None or s.get("mode") != "arcade":
        raise KeyError("session not found")
    if not s.get("finished_at"):
        raise ValueError("session not finished")
    if s.get("ended_reason") == "abandoned":
        raise ValueError("Abandoned runs cannot be submitted")

    duration_seconds = 0
    try:
        t0 = datetime.fromisoformat(s["started_at"])
        t1 = datetime.fromisoformat(s["finished_at"])
        duration_seconds = int((t1 - t0).total_seconds())
    except Exception:
        pass

    entry = ArcadeScoreEntry(
        player_name=(player_name.strip()[:32] or "anonymous"),
        score_total=int(s.get("score_total", 0)),
        level_reached=int(s.get("level", 1)),
        correct_total=int(s.get("correct_total", 0)),
        answered_total=int(s.get("answered_total", 0)),
        max_streak=int(s.get("max_streak", 0)),
        longest_combo_pts=int(s.get("longest_combo_pts", 0)),
        duration_seconds=duration_seconds,
        finished_at=s["finished_at"],
        session_id=sid,
    )
    db.collection(ARCADE_SCORES).document(sid).set(entry.model_dump())
    db.collection(SESSIONS).document(sid).update({"player_name": entry.player_name})
    return entry


def arcade_leaderboard(limit: int = 20) -> ArcadeLeaderboardResponse:
    db = get_db()
    docs = list(db.collection(ARCADE_SCORES).stream())
    entries = [ArcadeScoreEntry(**d.to_dict()) for d in docs]
    entries.sort(key=lambda e: (-e.score_total, -e.level_reached,
                                -e.correct_total, e.finished_at))
    return ArcadeLeaderboardResponse(entries=entries[:limit], total_runs=len(entries))
