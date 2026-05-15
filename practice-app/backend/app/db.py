"""Firestore client wrapper.

Auto-uses the emulator when FIRESTORE_EMULATOR_HOST is set (the official
google-cloud-firestore client checks this env var on startup). In production
the client uses Application Default Credentials (the Cloud Run service account).
"""
from __future__ import annotations

import os
from functools import lru_cache

from google.cloud import firestore


@lru_cache(maxsize=1)
def get_db() -> firestore.Client:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "local-dev")
    # Constructor reads FIRESTORE_EMULATOR_HOST automatically when present.
    return firestore.Client(project=project)


# Collection names — single source of truth.
QUESTIONS = "questions"
SESSIONS = "sessions"
SCORES = "scores"
PROGRESSIVE_SCORES = "progressive_scores"
ARCADE_SCORES = "arcade_scores"
