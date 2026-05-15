"""Security tests for the eligibility-token leaderboard protection.

These cover the regression that motivated the feature: a leaderboard
entry was overwritten by an unauthenticated client.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _seed(db, exams=("architect",), difficulties=("easy", "medium", "hard"), per=10):
    for exam in exams:
        for diff in difficulties:
            for i in range(per):
                qid = f"{exam}-{diff}-{i:03d}"
                db.seed_question(qid, {
                    "id": qid, "exam": exam, "section": f"{exam.upper()}-1.1",
                    "difficulty": diff, "text": f"Q {qid}",
                    "options": ["A", "B", "C", "D"], "correct_index": 0,
                    "explanation": "x", "doc_links": [],
                })


@pytest.fixture()
def client(fake_db):
    _seed(fake_db)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


def _finish_arcade(client) -> tuple[str, str]:
    """Start an arcade run and force the timer to zero. Returns (sid, token)."""
    body = client.post("/api/arcade/sessions", json={"starting_seconds": 30}).json()
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    end = client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": qid, "selected_index": 0,
        "confidence": "guess", "client_elapsed_ms": 60000,
    }).json()
    assert end["ended"] is True
    return sid, end["submit_token"]


# -- The token must actually be issued by the server ------------------------

def test_score_rejected_without_token(client):
    sid, _ = _finish_arcade(client)
    r = client.post(f"/api/arcade/sessions/{sid}/score",
                    json={"player_name": "NoToken"})
    # Pydantic 422 is fine — request is structurally invalid.
    assert r.status_code in (400, 422)


def test_score_rejected_with_wrong_token(client):
    sid, _ = _finish_arcade(client)
    r = client.post(f"/api/arcade/sessions/{sid}/score",
                    json={"player_name": "Forger",
                          "submit_token": "definitely-not-the-real-token"})
    assert r.status_code == 401
    lb = client.get("/api/arcade/leaderboard").json()
    assert all(e["player_name"] != "Forger" for e in lb["entries"])


def test_score_rejected_with_other_sessions_token(client):
    """A token issued for run A cannot be spent against run B."""
    sid_a, token_a = _finish_arcade(client)
    sid_b, _token_b = _finish_arcade(client)
    r = client.post(f"/api/arcade/sessions/{sid_b}/score",
                    json={"player_name": "Cross", "submit_token": token_a})
    assert r.status_code == 401


# -- Write-once: nobody can overwrite an existing entry ---------------------

def test_existing_entry_cannot_be_overwritten(client):
    sid, token = _finish_arcade(client)
    first = client.post(f"/api/arcade/sessions/{sid}/score",
                        json={"player_name": "RealPlayer",
                              "submit_token": token}).json()
    # Same token, different name → returns the original (write-once).
    second = client.post(f"/api/arcade/sessions/{sid}/score",
                         json={"player_name": "Hacker",
                               "submit_token": token}).json()
    assert second["player_name"] == "RealPlayer" == first["player_name"]
    lb = client.get("/api/arcade/leaderboard").json()
    assert all(e["player_name"] != "Hacker" for e in lb["entries"])


# -- Token has a TTL --------------------------------------------------------

def test_expired_token_is_rejected(client, monkeypatch):
    sid, token = _finish_arcade(client)
    # Backdate the stored expiry so token_expired() returns True.
    from app.db import get_db, SESSIONS
    get_db().collection(SESSIONS).document(sid).update(
        {"submit_token_expires_at": "2000-01-01T00:00:00+00:00"}
    )
    r = client.post(f"/api/arcade/sessions/{sid}/score",
                    json={"player_name": "Late", "submit_token": token})
    assert r.status_code == 401


# -- Summary endpoint never echoes the token (tokens live only in client memory) --

def test_summary_never_echoes_token(client):
    """The summary endpoint must NOT return the raw submit_token. The token
    is delivered exactly once in the answer response that ends the run, and
    only its sha256 hash is stored on the session document. This closes the
    leak where anyone who learned the session ID could GET /summary and
    steal the leaderboard write capability."""
    sid, token = _finish_arcade(client)
    s = client.get(f"/api/arcade/sessions/{sid}").json()
    assert s.get("submit_token") is None
    # The token from the answer response is still spendable.
    r = client.post(f"/api/arcade/sessions/{sid}/score",
                    json={"player_name": "Legit", "submit_token": token})
    assert r.status_code == 200


def test_session_doc_does_not_store_raw_token(client):
    """Defense in depth: even direct DB access reveals only the hash."""
    sid, token = _finish_arcade(client)
    from app.db import get_db, SESSIONS
    doc = get_db().collection(SESSIONS).document(sid).get().to_dict()
    assert "submit_token" not in doc, "raw token must never be persisted"
    assert "submit_token_hash" in doc
    # Hash on disk equals sha256 of the raw token returned to the client.
    import hashlib
    assert doc["submit_token_hash"] == hashlib.sha256(token.encode()).hexdigest()
