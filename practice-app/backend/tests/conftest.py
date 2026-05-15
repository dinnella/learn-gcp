"""Shared fixtures for the practice-app test suite.

Fast unit/integration tests use an in-process mock Firestore so they run
anywhere without Docker.  The `emulator` mark requires FIRESTORE_EMULATOR_HOST
to be set (i.e. inside `make test` / the compose stack) and is skipped otherwise.
"""
from __future__ import annotations

import os
import pytest


# ---------------------------------------------------------------------------
# Emulator guard — skip slow tests when the stack isn't running
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "emulator: requires the Firestore emulator (FIRESTORE_EMULATOR_HOST set)",
    )


def pytest_runtest_setup(item):
    if any(item.iter_markers("emulator")):
        if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
            pytest.skip("Firestore emulator not running — set FIRESTORE_EMULATOR_HOST")


# ---------------------------------------------------------------------------
# Minimal in-memory Firestore mock used by unit / integration tests
# ---------------------------------------------------------------------------

class _FakeDoc:
    def __init__(self, doc_id: str, data: dict | None = None):
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict:
        return dict(self._data) if self._data else {}


class _FakeDocRef:
    def __init__(self, store: dict, col: str, doc_id: str):
        self._store = store
        self._key = (col, doc_id)
        self._doc_id = doc_id

    def get(self):
        return _FakeDoc(self._doc_id, self._store.get(self._key))

    def set(self, data: dict):
        self._store[self._key] = dict(data)

    def create(self, data: dict):
        if self._key in self._store:
            from google.api_core import exceptions as gax
            raise gax.AlreadyExists(f"document {self._key} already exists")
        self._store[self._key] = dict(data)

    def update(self, data: dict):
        import copy
        from google.cloud import firestore
        existing = dict(self._store.get(self._key, {}))
        for k, v in data.items():
            if isinstance(v, firestore.ArrayUnion):
                existing.setdefault(k, [])
                existing[k] = existing[k] + list(v._values)
            else:
                existing[k] = v
        self._store[self._key] = existing


class _FakeQuery:
    def __init__(self, docs):
        self._docs = docs

    def where(self, *args, **kwargs):
        return self  # filters ignored — tests control the data directly

    def limit(self, n):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def stream(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._store, self._name, doc_id)

    def where(self, *args, **kwargs) -> _FakeQuery:
        docs = [
            _FakeDocWithId(k[1], v)
            for k, v in self._store.items()
            if k[0] == self._name
        ]
        return _FakeQuery(docs)

    def limit(self, n):
        return self.where()

    def order_by(self, *args, **kwargs):
        return self.where()

    def stream(self):
        return self.where().stream()


class _FakeDocWithId:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return True

    def to_dict(self) -> dict:
        return dict(self._data)


class FakeDB:
    """In-memory drop-in for google.cloud.firestore.Client."""

    def __init__(self):
        self._store: dict = {}

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self._store, name)

    def seed_question(self, qid: str, data: dict):
        """Helper: pre-populate a question document."""
        self._store[("questions", qid)] = data

    def seed_session(self, sid: str, data: dict):
        """Helper: pre-populate a session document."""
        self._store[("sessions", sid)] = data


@pytest.fixture()
def fake_db(monkeypatch) -> FakeDB:
    """Replace the real Firestore client with FakeDB for the duration of the test."""
    db = FakeDB()
    import app.db as db_module
    # Clear any cached real client, then replace the function itself.
    try:
        db_module.get_db.cache_clear()
    except AttributeError:
        pass
    monkeypatch.setattr(db_module, "get_db", lambda: db)
    # Patch through to sessions and questions modules too so all imports agree.
    import app.sessions as sessions_module
    import app.questions as questions_module
    monkeypatch.setattr(sessions_module, "get_db", lambda: db)
    monkeypatch.setattr(questions_module, "get_db", lambda: db)
    # Same for the new mode services
    import app.progressive as progressive_module
    import app.arcade as arcade_module
    monkeypatch.setattr(progressive_module, "get_db", lambda: db)
    monkeypatch.setattr(arcade_module, "get_db", lambda: db)
    return db
