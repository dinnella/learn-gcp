"""Session lifecycle, report card, leaderboard."""
from __future__ import annotations

import random
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
from .tokens import (
    hash_submit_token,
    mint_session_secret,
    mint_submit_token,
    secret_matches,
    token_expired,
    token_hash_matches,
)


PASS_THRESHOLD = 70.0       # % considered "passing" on a mock
WEAK_SECTION_THRESHOLD = 70.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_option_orders(qids: list[str]) -> dict[str, list[int]]:
    """Random per-question option permutation (display→original index).

    Stored on the session so the same shuffle is re-applied for both
    serving the question and grading the answer.
    """
    orders: dict[str, list[int]] = {}
    for qid in qids:
        full = get_question_full(qid)
        n = len(full["options"]) if full else 4
        perm = list(range(n))
        random.shuffle(perm)
        orders[qid] = perm
    return orders


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
    # Full uuid hex = 128 bits of entropy. Truncating to 12 hex chars (48 bits)
    # made session IDs guessable enough to grief other players via /abandon.
    sid = uuid.uuid4().hex
    option_orders = _build_option_orders(qids)
    abandon_secret_raw, abandon_secret_hash = mint_session_secret()
    doc = {
        "exam": exam,
        "started_at": _now_iso(),
        "finished_at": None,
        "question_ids": qids,
        "option_orders": option_orders,
        "answers": [],
        "player_name": player_name,
        "filters": {"sections": sections, "difficulties": difficulties},
        "abandon_secret_hash": abandon_secret_hash,
    }
    get_db().collection(SESSIONS).document(sid).set(doc)
    return {
        "session_id": sid,
        "total": len(qids),
        "first_qid": qids[0],
        "first_order": option_orders[qids[0]],
        "abandon_secret": abandon_secret_raw,
    }


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
    canonical_correct = full["correct_index"]

    # Translate the user's display-space pick back to canonical via the
    # per-session option permutation so grading aligns with the JSON.
    order = (session.get("option_orders") or {}).get(question_id)
    if order and 0 <= selected_index < len(order):
        canonical_selected = order[selected_index]
    else:
        canonical_selected = selected_index
    is_correct = canonical_selected == canonical_correct

    # The client thinks in display space — translate the correct index back
    # so the UI can highlight the right option after answering.
    if order and canonical_correct in order:
        display_correct = order.index(canonical_correct)
    else:
        display_correct = canonical_correct

    new_answer = {
        "question_id": question_id,
        "selected_index": selected_index,
        "correct_index": display_correct,
        "correct": is_correct,
        "confidence": confidence,
        "ts": _now_iso(),
    }
    answered = len(session["answers"]) + 1
    total = len(session["question_ids"])
    finished = answered >= total
    update: dict = {"answers": firestore.ArrayUnion([new_answer])}
    submit_token: str | None = None
    if finished:
        update["finished_at"] = _now_iso()
        submit_token, expires = mint_submit_token()
        # Store ONLY the sha256 hash of the raw token. The raw value is
        # returned to the client exactly once (in this answer response) and
        # is never readable from the session document by anyone who later
        # learns the session ID.
        update["submit_token_hash"] = hash_submit_token(submit_token)
        update["submit_token_expires_at"] = expires
        update["submit_token_used"] = False
    ref.update(update)

    next_qid = session["question_ids"][answered] if not finished else None
    next_order = (
        (session.get("option_orders") or {}).get(next_qid) if next_qid else None
    )
    return {
        "correct": is_correct,
        "correct_index": display_correct,
        "explanation": full.get("explanation"),
        "doc_links": full.get("doc_links", []),
        "next_qid": next_qid,
        "next_order": next_order,
        "answered": answered,
        "total": total,
        "submit_token": submit_token,
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
        # Tokens are intentionally NOT echoed from the summary endpoint.
        # The raw token is delivered exactly once (in the final /answer
        # response) and lives only in the client's memory after that. This
        # closes the leak where anyone who learned the session ID could GET
        # the summary and steal the token.
        submit_token=None,
    )


# ------------------------------------------------------------------
# Leaderboard
# ------------------------------------------------------------------

def submit_score(sid: str, player_name: str, submit_token: str) -> ScoreEntry:
    db = get_db()
    s = _load(sid)
    if s is None:
        raise KeyError("session not found")
    if not s.get("finished_at"):
        raise ValueError("session not finished — finish all questions first")

    # --- Eligibility token: write-once leaderboard protection -------------
    stored_hash = s.get("submit_token_hash")
    expires = s.get("submit_token_expires_at")
    if not token_hash_matches(stored_hash, submit_token):
        raise PermissionError("invalid submit_token")
    doc_id = hash_submit_token(submit_token)
    existing = db.collection(SCORES).document(doc_id).get()
    if existing.exists:
        # Token already spent on a prior call — return the original entry
        # so legitimate retries (network blips) stay idempotent. The original
        # entry can never be modified.
        return ScoreEntry(**existing.to_dict())
    if token_expired(expires):
        raise PermissionError("submit_token expired")

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
    # Write-once: .create() raises if the doc already exists, so a stolen
    # token can never overwrite an existing leaderboard entry.
    try:
        db.collection(SCORES).document(doc_id).create(entry.model_dump())
    except Exception as e:
        existing = db.collection(SCORES).document(doc_id).get()
        if existing.exists:
            return ScoreEntry(**existing.to_dict())
        raise PermissionError("leaderboard write rejected") from e
    # Burn the token and mirror the player_name onto the session.
    db.collection(SESSIONS).document(sid).update({
        "player_name": entry.player_name,
        "submit_token_used": True,
    })
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
