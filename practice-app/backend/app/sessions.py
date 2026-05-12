"""Session lifecycle, report card, leaderboard."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from google.cloud import firestore

from .db import SCORES, SESSIONS, get_db
from .models import (
    DocLink,
    LeaderboardResponse,
    ReportCard,
    ReportCardRecommendation,
    ScoreEntry,
    SessionSummary,
)
from .questions import get_question_full, sample_question_ids
from .section_titles import title_for


PASS_THRESHOLD = 70.0       # % considered "passing" on a mock
WEAK_SECTION_THRESHOLD = 70.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------
# Sessions
# ------------------------------------------------------------------

def start_session(
    exam: str,
    num_questions: int,
    sections: list[str] | None,
    difficulties: list[str] | None,
    player_name: str | None,
) -> dict:
    qids = sample_question_ids(exam, num_questions, sections, difficulties)
    if not qids:
        raise ValueError(
            f"No questions for exam={exam} sections={sections} difficulties={difficulties}. "
            "Try widening filters or run `make seed`."
        )
    sid = uuid.uuid4().hex[:12]
    doc = {
        "exam": exam,
        "started_at": _now_iso(),
        "finished_at": None,
        "question_ids": qids,
        "answers": [],
        "player_name": player_name,
        "filters": {"sections": sections, "difficulties": difficulties},
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

    full = get_question_full(question_id)
    if full is None:
        raise KeyError("question not found")
    correct_index = full["correct_index"]
    is_correct = selected_index == correct_index

    new_answer = {
        "question_id": question_id,
        "selected_index": selected_index,
        "correct_index": correct_index,
        "correct": is_correct,
        "confidence": confidence,
        "ts": _now_iso(),
    }
    answered = len(session["answers"]) + 1
    total = len(session["question_ids"])
    finished = answered >= total
    update: dict = {"answers": firestore.ArrayUnion([new_answer])}
    if finished:
        update["finished_at"] = _now_iso()
    ref.update(update)

    next_qid = session["question_ids"][answered] if not finished else None
    return {
        "correct": is_correct,
        "correct_index": correct_index,
        "explanation": full.get("explanation"),
        "doc_links": full.get("doc_links", []),
        "next_qid": next_qid,
        "answered": answered,
        "total": total,
    }


# ------------------------------------------------------------------
# Summary + report card
# ------------------------------------------------------------------

def _grade(pct: float) -> str:
    return "A" if pct >= 90 else "B" if pct >= 80 else "C" if pct >= 70 else "D" if pct >= 60 else "F"


def _suggested_action(score_pct: float) -> str:
    if score_pct < 50:
        return "Foundational gap — read the linked docs end-to-end, then retry only this section."
    if score_pct < 70:
        return "Skim the linked docs, focus on the bullets you missed, then retry with `hard` only."
    return "Strong — keep this section in your mix at 'hard' to maintain."


def _build_report_card(
    exam: str, per_section: dict[str, dict], score_pct: float, missed_docs: list[dict]
) -> ReportCard:
    weak = [sec for sec, row in per_section.items() if row["pct"] < WEAK_SECTION_THRESHOLD]

    # Group missed-question doc links by section, dedupe by URL.
    docs_by_section: dict[str, dict[str, str]] = defaultdict(dict)
    for entry in missed_docs:
        for d in entry["docs"]:
            docs_by_section[entry["section"]][d["url"]] = d["title"]

    recs: list[ReportCardRecommendation] = []
    for sec in sorted(per_section, key=lambda s: per_section[s]["pct"]):
        row = per_section[sec]
        if row["pct"] >= 90:
            continue   # skip strong sections
        recs.append(
            ReportCardRecommendation(
                section=sec,
                section_title=title_for(sec),
                score_pct=row["pct"],
                suggested_action=_suggested_action(row["pct"]),
                docs=[
                    DocLink(title=t, url=u)
                    for u, t in docs_by_section.get(sec, {}).items()
                ],
            )
        )

    # Build the next-session interactive prompt.
    if weak:
        weak_titles = ', '.join(title_for(s) for s in weak)
        prompt = (
            f"You're under {WEAK_SECTION_THRESHOLD:.0f}% on {len(weak)} topic(s): "
            f"{weak_titles}. Want a focused 10-question drill on those at any difficulty?"
        )
        next_cfg = {"exam": exam, "num_questions": 10, "sections": weak, "difficulties": None}
    elif score_pct < 90:
        prompt = "Solid run. Want a 15-question 'hard' set across all sections to push higher?"
        next_cfg = {"exam": exam, "num_questions": 15, "sections": None, "difficulties": ["hard"]}
    else:
        prompt = "Excellent. Try a 25-question full-length mock at any difficulty?"
        next_cfg = {"exam": exam, "num_questions": 25, "sections": None, "difficulties": None}

    return ReportCard(
        overall_grade=_grade(score_pct),
        passed_mock=score_pct >= PASS_THRESHOLD,
        weak_sections=weak,
        recommendations=recs,
        next_session_prompt=prompt,
        next_session_config=next_cfg,
    )


def summary(sid: str) -> SessionSummary | None:
    s = _load(sid)
    if s is None:
        return None
    answered = len(s["answers"])
    total = len(s["question_ids"])
    score_pct: float | None = None
    per_section: dict[str, dict] = {}
    per_difficulty: dict[str, dict] = {"easy": {"correct": 0, "total": 0},
                                       "medium": {"correct": 0, "total": 0},
                                       "hard": {"correct": 0, "total": 0}}
    missed_docs: list[dict] = []

    if answered:
        for ans in s["answers"]:
            full = get_question_full(ans["question_id"])
            if not full:
                continue
            sec = full.get("section", "unknown")
            diff = full.get("difficulty", "medium")
            row = per_section.setdefault(sec, {"correct": 0, "total": 0})
            row["total"] += 1
            per_difficulty[diff]["total"] += 1
            if ans["correct"]:
                row["correct"] += 1
                per_difficulty[diff]["correct"] += 1
            else:
                missed_docs.append({"section": sec, "docs": full.get("doc_links", [])})

        for row in per_section.values():
            row["pct"] = round(100 * row["correct"] / row["total"], 1)
        for row in per_difficulty.values():
            row["pct"] = round(100 * row["correct"] / row["total"], 1) if row["total"] else 0.0

        correct = sum(1 for a in s["answers"] if a["correct"])
        score_pct = round(100 * correct / answered, 1)

    report_card = None
    if s.get("finished_at") and score_pct is not None:
        report_card = _build_report_card(s["exam"], per_section, score_pct, missed_docs)

    return SessionSummary(
        id=sid,
        exam=s["exam"],
        started_at=s["started_at"],
        finished_at=s.get("finished_at"),
        answered=answered,
        total=total,
        score_pct=score_pct,
        per_section=per_section,
        per_difficulty=per_difficulty,
        player_name=s.get("player_name"),
        report_card=report_card,
    )


# ------------------------------------------------------------------
# Leaderboard
# ------------------------------------------------------------------

def submit_score(sid: str, player_name: str) -> ScoreEntry:
    db = get_db()
    s = _load(sid)
    if s is None:
        raise KeyError("session not found")
    if not s.get("finished_at"):
        raise ValueError("session not finished — finish all questions first")

    answered = len(s["answers"])
    correct = sum(1 for a in s["answers"] if a["correct"])
    score_pct = round(100 * correct / answered, 1)

    # Difficulty mix of *answered* questions (more honest than configured filter).
    diff_mix: dict[str, int] = defaultdict(int)
    for ans in s["answers"]:
        full = get_question_full(ans["question_id"])
        if full:
            diff_mix[full.get("difficulty", "medium")] += 1

    entry = ScoreEntry(
        player_name=player_name.strip()[:32] or "anonymous",
        exam=s["exam"],
        score_pct=score_pct,
        answered=answered,
        total=len(s["question_ids"]),
        difficulty_mix=dict(diff_mix),
        finished_at=s["finished_at"],
        session_id=sid,
    )
    # Score docs are keyed by session_id so re-submission is idempotent.
    db.collection(SCORES).document(sid).set(entry.model_dump())
    # Mirror the player_name onto the session for convenience.
    db.collection(SESSIONS).document(sid).update({"player_name": entry.player_name})
    return entry


def leaderboard(exam: str, limit: int = 20) -> LeaderboardResponse:
    db = get_db()
    docs = list(db.collection(SCORES).where("exam", "==", exam).stream())
    entries = [ScoreEntry(**d.to_dict()) for d in docs]
    # Sort: score desc, then more-questions-answered desc, then earliest finish_at.
    entries.sort(
        key=lambda e: (-e.score_pct, -e.answered, e.finished_at)
    )
    return LeaderboardResponse(exam=exam, entries=entries[:limit])
