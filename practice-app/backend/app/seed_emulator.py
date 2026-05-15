"""One-shot seeder: load all seed/*.json files into Firestore.

Each exam lives in its own file (pca.json, devops.json, genai.json …).
Files whose name starts with an underscore are skipped (migration helpers).

Idempotent: docs are written with their natural ID so re-runs overwrite
rather than duplicate. Safe against both the emulator and a real Firestore
project — chooses based on FIRESTORE_EMULATOR_HOST or GOOGLE_CLOUD_PROJECT.

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


def _seed_dir() -> Path:
    # /srv/seed in the container; ../seed when run from repo.
    candidates = [
        Path("/srv/seed"),
        Path(__file__).resolve().parent.parent / "seed",
    ]
    for p in candidates:
        if p.is_dir():
            return p
    raise FileNotFoundError("could not find seed directory")


def _load_questions() -> list[dict]:
    """Load and deduplicate questions from all non-underscore *.json files."""
    seed_dir = _seed_dir()
    files = sorted(f for f in seed_dir.glob("*.json") if not f.name.startswith("_"))
    if not files:
        raise FileNotFoundError(f"no *.json seed files found in {seed_dir}")

    seen: set[str] = set()
    questions: list[dict] = []
    for path in files:
        with path.open() as f:
            batch = json.load(f)
        dups = [q["id"] for q in batch if q["id"] in seen]
        if dups:
            raise ValueError(
                f"{path.name} contains IDs already seen in earlier files: {dups}"
            )
        seen.update(q["id"] for q in batch)
        questions.extend(batch)
        print(f"  {path.name}: {len(batch)} questions")

    return questions


def main() -> int:
    db = get_db()
    target = (
        f"emulator at {os.environ['FIRESTORE_EMULATOR_HOST']}"
        if "FIRESTORE_EMULATOR_HOST" in os.environ
        else f"project {os.environ.get('GOOGLE_CLOUD_PROJECT', '?')}"
    )
    print(f"Seeding -> {target}")

    questions = _load_questions()

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
