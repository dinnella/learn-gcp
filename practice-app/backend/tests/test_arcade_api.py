"""API integration tests for arcade mode."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _seed(db, exams=("architect", "devops", "genai"),
          difficulties=("easy", "medium", "hard"), per=10):
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


def _correct_index_for(sid, qid):
    from app.db import get_db, SESSIONS
    s = get_db().collection(SESSIONS).document(sid).get().to_dict()
    order = (s.get("option_orders") or {}).get(qid) or [0, 1, 2, 3]
    return order.index(0)


def _wrong_index_for(sid, qid):
    return (_correct_index_for(sid, qid) + 1) % 4


def test_start_returns_60s_timer_and_first_question(client):
    r = client.post("/api/arcade/sessions", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "arcade"
    assert body["starting_seconds"] == 60
    assert body["time_remaining_ms"] == 60000
    assert body["first_question"]["points_if_correct"] in (500, 1000, 2000)
    assert body["first_question"]["time_bonus_seconds"] in (10, 15, 20)


def test_correct_answer_adds_points_and_time(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    fq = body["first_question"]
    correct = _correct_index_for(sid, fq["id"])
    r = client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": fq["id"], "selected_index": correct,
        "confidence": "confident", "client_elapsed_ms": 2000,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["correct"] is True
    expected_pts = fq["points_if_correct"]
    expected_bonus = fq["time_bonus_seconds"]
    assert d["points_awarded"] == expected_pts
    assert d["time_bonus_seconds"] == expected_bonus
    # 60000 - 2000 + bonus*1000
    assert d["time_remaining_ms"] == 60000 - 2000 + expected_bonus * 1000
    assert d["score_total"] == expected_pts


def test_wrong_answer_only_debits_time(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    fq = body["first_question"]
    wrong = _wrong_index_for(sid, fq["id"])
    r = client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": fq["id"], "selected_index": wrong,
        "confidence": "guess", "client_elapsed_ms": 5000,
    })
    d = r.json()
    assert d["correct"] is False
    assert d["points_awarded"] == 0
    assert d["time_bonus_seconds"] == 0
    assert d["time_penalty_seconds"] == 10
    # 60000 - 5000 elapsed - 10000 penalty
    assert d["time_remaining_ms"] == 60000 - 5000 - 10000


def test_session_ends_when_time_runs_out(client):
    body = client.post("/api/arcade/sessions", json={"starting_seconds": 30}).json()
    sid = body["session_id"]
    fq = body["first_question"]
    # Burn far more than 30s with one answer (clamped at 60s, but more than 30s remaining).
    r = client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": fq["id"], "selected_index": 0,
        "confidence": "guess", "client_elapsed_ms": 60000,
    })
    d = r.json()
    assert d["ended"] is True
    assert d["ended_reason"] == "time"
    assert d["time_remaining_ms"] == 0


def test_client_cannot_underreport_elapsed_time(client, monkeypatch):
    """A scripted client sending client_elapsed_ms=0 must still be debited
    for the wallclock time the server measured since the previous tick."""
    body = client.post("/api/arcade/sessions", json={"starting_seconds": 60}).json()
    sid = body["session_id"]
    fq = body["first_question"]

    # Backdate last_tick_at so the server measures ~10s of elapsed time.
    from app.db import get_db, SESSIONS
    from datetime import datetime, timedelta, timezone
    backdated = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    get_db().collection(SESSIONS).document(sid).update({"last_tick_at": backdated})

    # Cheating client claims 0 ms elapsed.
    correct = _correct_index_for(sid, fq["id"])
    r = client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": fq["id"], "selected_index": correct,
        "confidence": "confident", "client_elapsed_ms": 0,
    }).json()
    # Server-measured elapsed (~10000 ms) is debited even though the client
    # claimed 0. Bonus is then added back for the correct answer.
    expected_bonus_ms = fq["time_bonus_seconds"] * 1000
    # Allow ~100ms slop for test timing.
    assert 60000 - 10000 + expected_bonus_ms - 200 <= r["time_remaining_ms"] <= 60000 - 10000 + expected_bonus_ms + 200


def _answer_correct(client, sid, qid):
    correct = _correct_index_for(sid, qid)
    return client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": qid, "selected_index": correct,
        "confidence": "confident", "client_elapsed_ms": 100,
    }).json()


def test_level_up_pending_after_10_correct(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    last = None
    for _ in range(10):
        last = _answer_correct(client, sid, qid)
        if last.get("level_up_pending"):
            break
        qid = last["next_question"]["id"]
    assert last["level_up_pending"] is True
    assert last["next_question"] is None
    assert last["correct_in_level"] == 10

    # Next /answer call must 400
    r = client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": "anything", "selected_index": 0,
        "confidence": "guess", "client_elapsed_ms": 100,
    })
    assert r.status_code == 400


def test_continue_resets_timer_and_increments_level(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    for _ in range(10):
        d = _answer_correct(client, sid, qid)
        if d.get("level_up_pending"):
            break
        qid = d["next_question"]["id"]
    r = client.post(f"/api/arcade/sessions/{sid}/continue")
    assert r.status_code == 200
    body2 = r.json()
    assert body2["level"] == 2
    assert body2["time_remaining_ms"] == 55_000  # level 2 reset = 55s
    assert body2["next_question"] is not None


def test_continue_rejected_when_no_pending(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    r = client.post(f"/api/arcade/sessions/{body['session_id']}/continue")
    assert r.status_code == 400


def test_summary_includes_level_and_streak(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    client.post(f"/api/arcade/sessions/{sid}/abandon",
                json={"abandon_secret": body["abandon_secret"]})
    s = client.get(f"/api/arcade/sessions/{sid}").json()
    assert "level_reached" in s
    assert "max_streak" in s
    assert "per_exam" in s


def test_score_submission_idempotent(client):
    body = client.post("/api/arcade/sessions", json={"starting_seconds": 30}).json()
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    # Run timer down
    end = client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": qid, "selected_index": 0,
        "confidence": "guess", "client_elapsed_ms": 60000,
    }).json()
    token = end["submit_token"]
    assert token
    client.post(f"/api/arcade/sessions/{sid}/score",
                json={"player_name": "Dup", "submit_token": token})
    client.post(f"/api/arcade/sessions/{sid}/score",
                json={"player_name": "Dup", "submit_token": token})
    lb = client.get("/api/arcade/leaderboard").json()
    dup = [e for e in lb["entries"] if e["player_name"] == "Dup"]
    assert len(dup) == 1


def test_abandon_marks_session_and_blocks_answer(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    qid = body["first_question"]["id"]
    secret = body["abandon_secret"]
    r = client.post(f"/api/arcade/sessions/{sid}/abandon",
                    json={"abandon_secret": secret})
    assert r.status_code == 200
    assert r.json()["ended_reason"] == "abandoned"
    r2 = client.post(f"/api/arcade/sessions/{sid}/answer", json={
        "question_id": qid, "selected_index": 0,
        "confidence": "guess", "client_elapsed_ms": 100,
    })
    assert r2.status_code == 400


def test_abandon_rejected_without_secret(client):
    """Without the per-session abandon secret a third party with the sid
    cannot grief the player by abandoning their run."""
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    r = client.post(f"/api/arcade/sessions/{sid}/abandon", json={})
    assert r.status_code == 401
    r2 = client.post(f"/api/arcade/sessions/{sid}/abandon",
                     json={"abandon_secret": "wrong"})
    assert r2.status_code == 401


def test_abandoned_run_cannot_submit_score(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    client.post(f"/api/arcade/sessions/{sid}/abandon",
                json={"abandon_secret": body["abandon_secret"]})
    r = client.post(f"/api/arcade/sessions/{sid}/score",
                    json={"player_name": "Cheater",
                          "submit_token": "abandoned-no-token"})
    assert r.status_code == 400


def test_abandon_idempotent(client):
    body = client.post("/api/arcade/sessions", json={}).json()
    sid = body["session_id"]
    secret = body["abandon_secret"]
    a = client.post(f"/api/arcade/sessions/{sid}/abandon",
                    json={"abandon_secret": secret}).json()
    b = client.post(f"/api/arcade/sessions/{sid}/abandon",
                    json={"abandon_secret": secret}).json()
    assert a["ended_reason"] == b["ended_reason"] == "abandoned"
