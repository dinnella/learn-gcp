"""Question loading + lookup with difficulty + section filters."""
from __future__ import annotations

import random
from typing import Iterable

from .db import QUESTIONS, get_db
from .models import Question


def _doc_to_question(doc) -> Question:
    data = doc.to_dict()
    data["id"] = doc.id
    data.pop("correct_index", None)  # never expose
    return Question(**data)


def list_sections(exam: str) -> list[str]:
    db = get_db()
    sections: set[str] = set()
    for d in db.collection(QUESTIONS).where("exam", "==", exam).stream():
        sections.add(d.to_dict().get("section", "unknown"))
    return sorted(sections)


def list_difficulties(exam: str) -> dict[str, int]:
    db = get_db()
    counts: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    for d in db.collection(QUESTIONS).where("exam", "==", exam).stream():
        diff = d.to_dict().get("difficulty", "medium")
        counts[diff] = counts.get(diff, 0) + 1
    return counts


def sample_question_ids(
    exam: str,
    n: int,
    sections: Iterable[str] | None = None,
    difficulties: Iterable[str] | None = None,
) -> list[str]:
    """Pick `n` random question IDs matching the filters.

    Filtering is done client-side after a single exam-scoped query because
    Firestore composite indexes aren't pre-created in the emulator and the
    dataset is small (<10k questions in the foreseeable future).
    """
    db = get_db()
    docs = list(db.collection(QUESTIONS).where("exam", "==", exam).stream())

    sec_set = set(sections) if sections else None
    diff_set = set(difficulties) if difficulties else None

    def keep(d) -> bool:
        data = d.to_dict()
        if sec_set and data.get("section") not in sec_set:
            return False
        if diff_set and data.get("difficulty", "medium") not in diff_set:
            return False
        return True

    docs = [d for d in docs if keep(d)]
    if not docs:
        return []
    if len(docs) <= n:
        random.shuffle(docs)
        return [d.id for d in docs]
    return [d.id for d in random.sample(docs, n)]


def get_question(qid: str) -> Question | None:
    snap = get_db().collection(QUESTIONS).document(qid).get()
    if not snap.exists:
        return None
    return _doc_to_question(snap)


def get_question_full(qid: str) -> dict | None:
    """Returns the full document including correct_index. Server-side only."""
    snap = get_db().collection(QUESTIONS).document(qid).get()
    if not snap.exists:
        return None
    data = snap.to_dict()
    data["id"] = snap.id
    return data


def get_question_correct_index(qid: str) -> int | None:
    full = get_question_full(qid)
    return full["correct_index"] if full else None
