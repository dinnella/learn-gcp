"""FastAPI entrypoint."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import sessions as sessions_svc
from .db import QUESTIONS, get_db
from .models import (
    AnswerRequest,
    AnswerResponse,
    DocLink,
    LeaderboardResponse,
    QuestionForClient,
    ScoreEntry,
    SessionStartResponse,
    SessionSummary,
    StartSessionRequest,
)
from .questions import get_question, list_difficulties, list_sections


logging.basicConfig(level=os.environ.get("APP_LOG_LEVEL", "INFO"))
log = logging.getLogger("practice-app")

app = FastAPI(
    title="GCP cert practice tests",
    version="0.2.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


# ---------- API ----------

@app.get("/api/health")
def health() -> dict:
    try:
        list(get_db().collection(QUESTIONS).limit(1).stream())
        return {"status": "ok", "env": os.environ.get("APP_ENV", "unknown")}
    except Exception as exc:
        raise HTTPException(503, f"firestore unreachable: {exc}") from exc


@app.get("/api/exams")
def exams() -> dict:
    return {
        "exams": [
            {
                "id": "pca",
                "name": "Professional Cloud Architect",
                "sections": list_sections("pca"),
                "difficulties": list_difficulties("pca"),
            },
            {
                "id": "devops",
                "name": "Professional Cloud DevOps Engineer",
                "sections": list_sections("devops"),
                "difficulties": list_difficulties("devops"),
            },
        ]
    }


@app.post("/api/sessions", response_model=SessionStartResponse)
def start(req: StartSessionRequest) -> SessionStartResponse:
    try:
        result = sessions_svc.start_session(
            req.exam, req.num_questions, req.sections, req.difficulties, req.player_name
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    q = get_question(result["first_qid"])
    if q is None:
        raise HTTPException(500, "first question vanished mid-session")
    return SessionStartResponse(
        session_id=result["session_id"],
        total=result["total"],
        first_question=QuestionForClient(**q.model_dump(exclude={"explanation", "doc_links"})),
    )


@app.post("/api/sessions/{sid}/answer", response_model=AnswerResponse)
def answer(sid: str, req: AnswerRequest) -> AnswerResponse:
    try:
        result = sessions_svc.record_answer(
            sid, req.question_id, req.selected_index, req.confidence
        )
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    next_q = None
    if result["next_qid"]:
        nq = get_question(result["next_qid"])
        if nq:
            next_q = QuestionForClient(**nq.model_dump(exclude={"explanation", "doc_links"}))
    return AnswerResponse(
        correct=result["correct"],
        correct_index=result["correct_index"],
        explanation=result["explanation"],
        doc_links=[DocLink(**d) for d in result["doc_links"]],
        next_question=next_q,
        progress={"answered": result["answered"], "total": result["total"]},
    )


@app.get("/api/sessions/{sid}", response_model=SessionSummary)
def session_summary(sid: str) -> SessionSummary:
    s = sessions_svc.summary(sid)
    if s is None:
        raise HTTPException(404, "session not found")
    return s


# ---------- Leaderboard ----------

class SubmitScoreRequest(BaseModel):
    player_name: str = Field(min_length=1, max_length=32)


@app.post("/api/sessions/{sid}/score", response_model=ScoreEntry)
def submit_score(sid: str, req: SubmitScoreRequest) -> ScoreEntry:
    try:
        return sessions_svc.submit_score(sid, req.player_name)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/leaderboard/{exam}", response_model=LeaderboardResponse)
def leaderboard(exam: str, limit: int = 20) -> LeaderboardResponse:
    if exam not in ("pca", "devops"):
        raise HTTPException(400, "exam must be 'pca' or 'devops'")
    return sessions_svc.leaderboard(exam, min(limit, 100))


# ---------- Static SPA ----------

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
