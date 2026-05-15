"""API integration tests for progressive mode."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _seed(db, exams=("architect", "devops", "genai"),
          difficulties=("easy", "medium", "hard"), per=4):
    for exam in exams:
        for diff in difficulties:
            for i in range(per):
                qid = f"{exam}-{diff}-{i:03d}"
                db.seed_question(qid, {
                    "id": qid, "exam": exam, "section": f"{exam.upper()}-1.1",
                    "difficulty": diff, "text": f"Q {qid}",
                    "options": ["A", "B", "C", "D"], "correct_index": 0,
                    "explanation": "x", "doc_links": [{"title": "T", "url": "https://x"}],
                })


@pytest.fixture()
def client(fake_db):
    _seed(fake_db)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True)


def _start(client):
    r = client.post("/api/progressive/sessions", json={"player_name": "Ada"})
    assert r.status_code == 200, r.text
    return r.json()


def test_start_returns_medium_first_question(client):
    body = _start(client)
    assert body["mode"] == "progressive"
    assert body["max_strikes"] == 3
    assert body["first_question"]["difficulty"] == "medium"


def test_correct_answer_steps_up(client):
    body = _start(client)
    sid = body["session_id"]
    fq = body["first_question"]
    correct = _correct_index_for(client, sid, fq["id"])
    r = client.post(f"/api/progressive/sessions/{sid}/answer", json={
        "question_id": fq["id"], "selected_index": correct, "confidence": "confident",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["correct"] is True
    assert data["points_awarded"] == 2  # medium
    assert data["next_question"]["difficulty"] == "hard"


def _answer(client, sid, qid, selected_index):
    return client.post(f"/api/progressive/sessions/{sid}/answer", json={
        "question_id": qid, "selected_index": selected_index, "confidence": "guess",
    })


def _correct_index_for(client, sid, qid):
    """Probe by reading the session option order is internal — we cheat using db."""
    from app.db import get_db, SESSIONS
    s = get_db().collection(SESSIONS).document(sid).get().to_dict()
    order = (s.get("option_orders") or {}).get(qid) or [0, 1, 2, 3]
    # Canonical 0 lives at display position order.index(0)
    return order.index(0)


def _wrong_index_for(client, sid, qid):
    return (_correct_index_for(client, sid, qid) + 1) % 4


def test_three_strikes_ends_session(client):
    body = _start(client)
    sid = body["session_id"]
    qid = body["first_question"]["id"]

    seen_ended = False
    for _ in range(5):
        wrong = _wrong_index_for(client, sid, qid)
        r = _answer(client, sid, qid, wrong)
        assert r.status_code == 200
        data = r.json()
        if data["ended"]:
            assert data["ended_reason"] == "strikes"
            seen_ended = True
            break
        qid = data["next_question"]["id"]
    assert seen_ended


def test_session_ends_on_hard_exhaustion(fake_db):
    # Only easy + medium questions, no hard.
    _seed(fake_db, difficulties=("easy", "medium"))
    from app.main import app
    c = TestClient(app, raise_server_exceptions=True)
    r = c.post("/api/progressive/sessions", json={"player_name": "Ada"})
    assert r.status_code == 200
    body = r.json()
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    correct = _correct_index_for(c, sid, qid)
    r2 = c.post(f"/api/progressive/sessions/{sid}/answer", json={
        "question_id": qid, "selected_index": correct, "confidence": "confident",
    })
    data = r2.json()
    assert data["ended"]
    assert data["ended_reason"] == "hard_exhausted"


def test_summary_includes_per_exam_breakdown(client):
    body = _start(client)
    sid = body["session_id"]
    # Abandon immediately → summary still queryable
    client.post(f"/api/progressive/sessions/{sid}/abandon")
    r = client.get(f"/api/progressive/sessions/{sid}")
    assert r.status_code == 200
    s = r.json()
    assert "per_exam" in s
    assert "exams" in s


def test_score_submission_idempotent(client):
    body = _start(client)
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    # Force end via 3 strikes
    for _ in range(5):
        wrong = _wrong_index_for(client, sid, qid)
        r = _answer(client, sid, qid, wrong)
        d = r.json()
        if d["ended"]:
            break
        qid = d["next_question"]["id"]
    client.post(f"/api/progressive/sessions/{sid}/score", json={"player_name": "Dup"})
    client.post(f"/api/progressive/sessions/{sid}/score", json={"player_name": "Dup"})
    lb = client.get("/api/progressive/leaderboard").json()
    dup = [e for e in lb["entries"] if e["player_name"] == "Dup"]
    assert len(dup) == 1


def test_leaderboard_separate_from_classic(client):
    """Posting a progressive score does NOT show up on classic leaderboard."""
    body = _start(client)
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    for _ in range(5):
        wrong = _wrong_index_for(client, sid, qid)
        r = _answer(client, sid, qid, wrong)
        d = r.json()
        if d["ended"]:
            break
        qid = d["next_question"]["id"]
    client.post(f"/api/progressive/sessions/{sid}/score", json={"player_name": "ProgOnly"})
    classic_lb = client.get("/api/leaderboard/architect").json()
    names = [e["player_name"] for e in classic_lb["entries"]]
    assert "ProgOnly" not in names


def test_abandon_marks_session_and_blocks_answer(client):
    body = _start(client)
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    r = client.post(f"/api/progressive/sessions/{sid}/abandon")
    assert r.status_code == 200
    assert r.json()["ended_reason"] == "abandoned"
    r2 = client.post(f"/api/progressive/sessions/{sid}/answer", json={
        "question_id": qid, "selected_index": 0, "confidence": "guess",
    })
    assert r2.status_code == 400


def test_abandoned_run_cannot_submit_score(client):
    body = _start(client)
    sid = body["session_id"]
    client.post(f"/api/progressive/sessions/{sid}/abandon")
    r = client.post(f"/api/progressive/sessions/{sid}/score",
                    json={"player_name": "Cheater"})
    assert r.status_code == 400


def test_abandon_idempotent(client):
    body = _start(client)
    sid = body["session_id"]
    a = client.post(f"/api/progressive/sessions/{sid}/abandon").json()
    b = client.post(f"/api/progressive/sessions/{sid}/abandon").json()
    assert a["ended_reason"] == b["ended_reason"] == "abandoned"
