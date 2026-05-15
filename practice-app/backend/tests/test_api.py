"""Integration tests — full HTTP cycle via FastAPI TestClient + FakeDB.

These run without Docker; the FakeDB fixture from conftest.py replaces
the real Firestore client for the duration of each test.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Minimal seed data reused across tests
# ---------------------------------------------------------------------------

Q1 = {
    "id": "pca-1.1-001",
    "exam": "architect",
    "section": "PCA-1.1",
    "difficulty": "medium",
    "text": "Which service provides managed relational DB?",
    "options": ["Cloud Spanner", "BigQuery", "Pub/Sub", "Dataflow"],
    "correct_index": 0,
    "explanation": "Cloud Spanner is the managed relational DB.",
    "doc_links": [{"title": "Spanner docs", "url": "https://cloud.google.com/spanner"}],
}

Q2 = {
    "id": "pca-1.2-001",
    "exam": "architect",
    "section": "PCA-1.2",
    "difficulty": "hard",
    "text": "Best compute for short-lived event-driven workloads?",
    "options": ["GKE", "Cloud Run", "Compute Engine", "App Engine Flex"],
    "correct_index": 1,
    "explanation": "Cloud Run scales to zero.",
    "doc_links": [],
}


@pytest.fixture()
def client(fake_db):
    """TestClient with FakeDB injected and two seed questions loaded."""
    fake_db.seed_question("pca-1.1-001", Q1)
    fake_db.seed_question("pca-1.2-001", Q2)

    # Import app *after* monkeypatch so it picks up the fake db
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# /api/exams
# ---------------------------------------------------------------------------

def test_exams_lists_architect(client):
    r = client.get("/api/exams")
    assert r.status_code == 200
    exams = {e["id"]: e for e in r.json()["exams"]}
    assert "architect" in exams
    # Section titles should be human-readable, not raw codes
    arch_titles = [s["title"] for s in exams["architect"]["sections"]]
    assert any("Compliance" in t for t in arch_titles)
    assert any("compute" in t.lower() for t in arch_titles)


def test_exams_devops_sections_have_titles(client):
    """DevOps sections must resolve to descriptive titles, not 'DevOps-x.y'."""
    # Seed a devops question so the section appears
    from tests.conftest import FakeDB
    import app.db as db_module
    db = db_module.get_db()
    db.seed_question("devops-1.1-001", {
        "id": "devops-1.1-001", "exam": "devops", "section": "DevOps-1.1",
        "difficulty": "medium", "text": "Q", "options": ["A", "B", "C", "D"],
        "correct_index": 0, "explanation": "", "doc_links": [],
    })
    r = client.get("/api/exams")
    exams = {e["id"]: e for e in r.json()["exams"]}
    if exams.get("devops", {}).get("sections"):
        for sec in exams["devops"]["sections"]:
            # Title must not be the raw code like "DevOps-1.1"
            assert sec["title"] != sec["id"], (
                f"Section {sec['id']} still shows raw code as title"
            )


# ---------------------------------------------------------------------------
# POST /api/sessions  →  answer  →  summary
# ---------------------------------------------------------------------------

def _start_session(client, n=2, exam="architect"):
    return client.post("/api/sessions", json={
        "exam": exam, "num_questions": n,
        "sections": None, "difficulties": None,
    })


def test_start_session_returns_first_question(client):
    r = _start_session(client)
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    assert body["total"] == 2
    fq = body["first_question"]
    assert fq["exam"] == "architect"
    assert len(fq["options"]) == 4
    # correct_index must never appear in the client response
    assert "correct_index" not in fq


def test_start_session_no_questions_raises_400(client):
    r = client.post("/api/sessions", json={
        "exam": "architect", "num_questions": 5,
        "sections": ["PCA-NONEXISTENT"], "difficulties": None,
    })
    assert r.status_code == 400


def test_answer_correct_and_next_question(client):
    sid = _start_session(client).json()["session_id"]

    # Fetch current state to know first question id
    r_sess = client.get(f"/api/sessions/{sid}")
    # Session not finished yet — no report card
    assert r_sess.json()["report_card"] is None

    # Peek at what the first question is via start response
    fq = _start_session(client).json()["first_question"]
    # Answer whatever index — we just want the response shape
    r = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": fq["id"],
        "selected_index": 0,
        "confidence": "confident",
    })
    assert r.status_code == 200
    body = r.json()
    assert "correct" in body
    assert isinstance(body["correct_index"], int)
    assert body["progress"]["answered"] == 1
    assert body["progress"]["total"] == 2


def test_answer_duplicate_raises_400(client):
    fq = _start_session(client).json()
    sid = fq["session_id"]
    qid = fq["first_question"]["id"]
    payload = {"question_id": qid, "selected_index": 0, "confidence": "guess"}
    client.post(f"/api/sessions/{sid}/answer", json=payload)
    r2 = client.post(f"/api/sessions/{sid}/answer", json=payload)
    assert r2.status_code == 400


def test_full_session_produces_report_card(client):
    """Answer all questions in a 2-question session; report card must appear."""
    start = _start_session(client, n=2).json()
    sid = start["session_id"]
    q1_id = start["first_question"]["id"]

    r1 = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": q1_id, "selected_index": 0, "confidence": "confident",
    })
    assert r1.status_code == 200
    q2 = r1.json().get("next_question")
    assert q2 is not None, "Expected a second question"
    assert "correct_index" not in q2

    r2 = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": q2["id"], "selected_index": 0, "confidence": "narrowed",
    })
    assert r2.status_code == 200
    assert r2.json()["next_question"] is None  # session done

    summary = client.get(f"/api/sessions/{sid}").json()
    rc = summary["report_card"]
    assert rc is not None
    assert rc["overall_grade"] in ("A", "B", "C", "D", "F")
    assert isinstance(rc["passed_mock"], bool)
    assert "next_session_config" in rc
    assert "next_session_prompt" in rc


def test_report_card_next_session_config_is_postable(client):
    """next_session_config must be a valid body for POST /api/sessions."""
    start = _start_session(client, n=2).json()
    sid = start["session_id"]
    q1_id = start["first_question"]["id"]

    r1 = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": q1_id, "selected_index": 0, "confidence": "confident",
    })
    q2 = r1.json()["next_question"]
    client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": q2["id"], "selected_index": 0, "confidence": "narrowed",
    })

    cfg = client.get(f"/api/sessions/{sid}").json()["report_card"]["next_session_config"]
    # Should be directly POST-able
    r = client.post("/api/sessions", json=cfg)
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

def test_leaderboard_empty(client):
    r = client.get("/api/leaderboard/architect")
    assert r.status_code == 200
    assert r.json()["entries"] == []


def test_leaderboard_invalid_exam(client):
    r = client.get("/api/leaderboard/unknown")
    assert r.status_code == 400


def test_submit_score_and_appears_on_leaderboard(client):
    start = _start_session(client, n=2).json()
    sid = start["session_id"]
    q1_id = start["first_question"]["id"]

    r1 = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": q1_id, "selected_index": 0, "confidence": "confident",
    })
    q2 = r1.json()["next_question"]
    end = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": q2["id"], "selected_index": 0, "confidence": "narrowed",
    }).json()
    token = end["submit_token"]
    assert token

    r_score = client.post(f"/api/sessions/{sid}/score",
                          json={"player_name": "Testy McTestface",
                                "submit_token": token})
    assert r_score.status_code == 200
    entry = r_score.json()
    assert entry["player_name"] == "Testy McTestface"
    assert entry["exam"] == "architect"
    assert isinstance(entry["score_pct"], float)

    lb = client.get("/api/leaderboard/architect").json()
    names = [e["player_name"] for e in lb["entries"]]
    assert "Testy McTestface" in names


def test_submit_score_idempotent(client):
    """Submitting score twice for the same session should not duplicate the entry."""
    start = _start_session(client, n=2).json()
    sid = start["session_id"]
    q1_id = start["first_question"]["id"]

    r1 = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": q1_id, "selected_index": 0, "confidence": "confident",
    })
    q2 = r1.json()["next_question"]
    end = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": q2["id"], "selected_index": 0, "confidence": "narrowed",
    }).json()
    token = end["submit_token"]

    client.post(f"/api/sessions/{sid}/score",
                json={"player_name": "Dup", "submit_token": token})
    client.post(f"/api/sessions/{sid}/score",
                json={"player_name": "Dup", "submit_token": token})

    lb = client.get("/api/leaderboard/architect").json()
    dup_entries = [e for e in lb["entries"] if e["player_name"] == "Dup"]
    assert len(dup_entries) == 1, "Duplicate score entries should be deduplicated"


# ---------------------------------------------------------------------------
# Security — correct_index never appears anywhere in API responses
# ---------------------------------------------------------------------------

def test_correct_index_never_in_start_response(client):
    body = _start_session(client).json()
    assert "correct_index" not in str(body)


def test_correct_index_never_in_answer_response(client):
    start = _start_session(client).json()
    sid = start["session_id"]
    qid = start["first_question"]["id"]
    r = client.post(f"/api/sessions/{sid}/answer", json={
        "question_id": qid, "selected_index": 0, "confidence": "confident",
    })
    body = r.json()
    # correct_index IS in AnswerResponse (to highlight the right option) — that's intentional.
    # But it must not appear in the nested next_question object.
    nq = body.get("next_question") or {}
    assert "correct_index" not in nq
