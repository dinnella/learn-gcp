"""Session lifecycle: start a quiz, record answers, compute summary."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from google.cloud import firestore

from .db import SESSIONS, get_db
from .models import SessionSummary
from .questions import get_question, get_question_correct_index, sample_question_ids


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_session(exam: str, num_questions: int, sections: list[str] | None) -> dict:
    qids = sample_question_ids(exam, num_questions, sections)
    if not qids:
        raise ValueError(
            f"No questions available for exam={exam} sections={sections}. "
            "Did you run `make seed`?"
        )
    sid = uuid.uuid4().hex[:12]
    doc = {
        "exam": exam,
        "started_at": _now_iso(),
        "finished_at": None,
        "question_ids": qids,
        "answers": [],   # list of {question_id, selected_index, correct, confidence, ts}
    }
    get_db().collection(SESSIONS).document(sid).set(doc)
    return {"session_id": sid, "total": len(qids), "first_qid": qids[0]}


def _load(sid: str) -> dict | None:
    snap = get_db().collection(SESSIONS).document(sid).get()
    return snap.to_dict() if snap.exists else None


def record_answer(
    sid: str, question_id: str, selected_index: int, confidence: str
) -> dict:
    db = get_db()
    ref = db.collection(SESSIONS).document(sid)
    snap = ref.get()
    if not snap.exists:
        raise KeyError("session not found")
    session = snap.to_dict()
    if session.get("finished_at"):
        raise ValueError("session already finished")
    if question_id not in session["question_ids"]:
        raise ValueError("question not part of this session")
    if any(a["question_id"] == question_id for a in session["answers"]):
        raise ValueError("question already answered")

    correct_index = get_question_correct_index(question_id)
    if correct_index is None:
        raise KeyError("question not found")
    is_correct = selected_index == correct_index

    new_answer = {
        "question_id": question_id,
        "selected_index": selected_index,
        "correct_index": correct_index,
        "correct": is_correct,
        "confidence": confidence,
        "ts": _now_iso(),
    }
    session["answers"].append(new_answer)
    answered = len(session["answers"])
    total = len(session["question_ids"])
    finished = answered >= total
    update: dict = {"answers": firestore.ArrayUnion([new_answer])}
    if finished:
        update["finished_at"] = _now_iso()
    ref.update(update)

    next_qid = None
    if not finished:
        next_qid = session["question_ids"][answered]

    return {
        "correct": is_correct,
        "correct_index": correct_index,
        "next_qid": next_qid,
        "answered": answered,
        "total": total,
    }


def summary(sid: str) -> SessionSummary | None:
    s = _load(sid)
    if s is None:
        return None
    answered = len(s["answers"])
    total = len(s["question_ids"])
    score_pct: float | None = None
    per_section: dict[str, dict] = {}

    if answered:
        # Per-section scoring requires looking up each question's section.
        for ans in s["answers"]:
            q = get_question(ans["question_id"])
            sec = q.section if q else "unknown"
            row = per_section.setdefault(sec, {"correct": 0, "total": 0})
            row["total"] += 1
            if ans["correct"]:
                row["correct"] += 1
        for row in per_section.values():
            row["pct"] = round(100 * row["correct"] / row["total"], 1)
        correct = sum(1 for a in s["answers"] if a["correct"])
        score_pct = round(100 * correct / answered, 1)

    return SessionSummary(
        id=sid,
        exam=s["exam"],
        started_at=s["started_at"],
        finished_at=s.get("finished_at"),
        answered=answered,
        total=total,
        score_pct=score_pct,
        per_section=per_section,
    )
