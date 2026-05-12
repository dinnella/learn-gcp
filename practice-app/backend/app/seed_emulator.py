"""One-shot seeder: load seed/questions.json into Firestore.

Idempotent: docs are written with their natural ID (q-0001, …) so re-runs
overwrite rather than duplicate. Safe against both the emulator and a real
Firestore in your project — chooses based on FIRESTORE_EMULATOR_HOST or
GOOGLE_CLOUD_PROJECT.

Usage:
  Local (compose):
    make seed                                     # runs `python -m app.seed_emulator` in container
  Prod (against your real project):
    GOOGLE_CLOUD_PROJECT=my-proj python backend/app/seed_emulator.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .db import QUESTIONS, get_db


def _seed_path() -> Path:
    # /srv/seed in the container; ../seed when run from repo.
    candidates = [
        Path("/srv/seed/questions.json"),
        Path(__file__).resolve().parent.parent / "seed" / "questions.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("could not find seed/questions.json")


def main() -> int:
    db = get_db()
    target = (
        f"emulator at {os.environ['FIRESTORE_EMULATOR_HOST']}"
        if "FIRESTORE_EMULATOR_HOST" in os.environ
        else f"project {os.environ.get('GOOGLE_CLOUD_PROJECT', '?')}"
    )
    path = _seed_path()
    print(f"Seeding {path} -> {target}")

    with path.open() as f:
        questions = json.load(f)

    batch = db.batch()
    written = 0
    for q in questions:
        ref = db.collection(QUESTIONS).document(q["id"])
        batch.set(ref, q)
        written += 1
        if written % 400 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()
    print(f"✔ wrote {written} questions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
