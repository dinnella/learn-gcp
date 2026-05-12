"""Question loading + lookup.

In dev, questions are loaded from the seed JSON file into the Firestore
emulator on demand (via `make seed`). In prod, the same JSON is uploaded
to GCS and loaded into Firestore by a one-shot job — see infra/seed_job.

Read paths use only Firestore so dev and prod behave identically.
"""
from __future__ import annotations

import random
from typing import Iterable

from .db import QUESTIONS, get_db
from .models import Question


def _doc_to_question(doc) -> Question:
    data = doc.to_dict()
    data["id"] = doc.id
    return Question(**data)


def list_sections(exam: str) -> list[str]:
    db = get_db()
    sections: set[str] = set()
    for d in db.collection(QUESTIONS).where("exam", "==", exam).stream():
        sections.add(d.to_dict().get("section", "unknown"))
    return sorted(sections)


def sample_question_ids(
    exam: str, n: int, sections: Iterable[str] | None = None
) -> list[str]:
    """Pick `n` random question IDs for the requested exam (and optional sections)."""
    db = get_db()
    q = db.collection(QUESTIONS).where("exam", "==", exam)
    if sections:
        q = q.where("section", "in", list(sections)[:30])  # Firestore `in` cap
    docs = list(q.stream())
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


def get_question_correct_index(qid: str) -> int | None:
    """Hidden lookup of the correct answer (used by /answer endpoint)."""
    snap = get_db().collection(QUESTIONS).document(qid).get()
    if not snap.exists:
        return None
    return snap.to_dict().get("correct_index")
