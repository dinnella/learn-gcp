"""FastAPI entrypoint."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

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
from .questions import get_question, get_question_shuffled, list_difficulties, list_sections
from .section_titles import title_for


logging.basicConfig(level=os.environ.get("APP_LOG_LEVEL", "INFO"))
log = logging.getLogger("practice-app")

app = FastAPI(
    title="Next3k LevelUp — GCP cert practice",
    version="0.2.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


# ---------- Security headers ----------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set conservative security headers on every response.

    HSTS is only emitted when the request arrived over HTTPS (Cloud Run /
    the load balancer set `X-Forwarded-Proto: https`) so local HTTP dev
    isn't pinned to HTTPS in the browser.
    """

    CSP = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", self.CSP)
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ---------- Edge auth (Cloudflare-in-front) ----------

class EdgeAuthMiddleware(BaseHTTPMiddleware):
    """Require a shared-secret header on every request when EDGE_SHARED_SECRET is set.

    Pattern: Cloudflare sits in front of Cloud Run as a proxied CNAME and a
    Transform Rule injects `X-Edge-Auth: <secret>` on every origin request.
    Without that header (i.e. a direct hit to `*.run.app`), the request is
    rejected with 403. This gives us "only Cloudflare can reach the origin"
    semantics without paying for a GCP load balancer.

    `/api/health` is exempted so Cloud Run's startup probe still works.
    Local dev (no env var set) skips the check entirely.
    """

    EXEMPT_PATHS = {"/api/health"}
    HEADER_NAME = "x-edge-auth"

    def __init__(self, app, secret: str | None) -> None:
        super().__init__(app)
        self._secret = secret

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._secret and request.url.path not in self.EXEMPT_PATHS:
            presented = request.headers.get(self.HEADER_NAME, "")
            if not _secrets_compare(presented, self._secret):
                return Response(status_code=403, content="forbidden")
        return await call_next(request)


def _secrets_compare(a: str, b: str) -> bool:
    """Constant-time string comparison."""
    import hmac
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


_EDGE_SECRET = os.environ.get("EDGE_SHARED_SECRET", "").strip() or None
if _EDGE_SECRET:
    log.info("edge-auth: enabled (origin requires X-Edge-Auth header)")
else:
    log.info("edge-auth: disabled (no EDGE_SHARED_SECRET set)")
app.add_middleware(EdgeAuthMiddleware, secret=_EDGE_SECRET)


# ---------- API ----------

@app.get("/api/health")
def health() -> dict:
    try:
        list(get_db().collection(QUESTIONS).limit(1).stream())
        return {"status": "ok", "env": os.environ.get("APP_ENV", "unknown")}
    except Exception as exc:
        raise HTTPException(503, f"firestore unreachable: {exc}") from exc


def _sections_with_titles(exam: str) -> list[dict]:
    return [{"id": s, "title": title_for(s)} for s in list_sections(exam)]


@app.get("/api/exams")
def exams() -> dict:
    return {
        "exams": [
            {
                "id": "pca",
                "name": "Professional Cloud Architect",
                "sections": _sections_with_titles("pca"),
                "difficulties": list_difficulties("pca"),
            },
            {
                "id": "devops",
                "name": "Professional Cloud DevOps Engineer",
                "sections": _sections_with_titles("devops"),
                "difficulties": list_difficulties("devops"),
            },
            {
                "id": "genai",
                "name": "Generative AI Leader",
                "sections": _sections_with_titles("genai"),
                "difficulties": list_difficulties("genai"),
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
    q = get_question_shuffled(result["first_qid"], result.get("first_order") or [])
    if q is None:
        raise HTTPException(500, "first question vanished mid-session")
    return SessionStartResponse(
        session_id=result["session_id"],
        total=result["total"],
        first_question=QuestionForClient(
            **q.model_dump(exclude={"explanation", "doc_links"}),
            section_title=title_for(q.section),
        ),
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
        nq = get_question_shuffled(result["next_qid"], result.get("next_order") or [])
        if nq:
            next_q = QuestionForClient(
                **nq.model_dump(exclude={"explanation", "doc_links"}),
                section_title=title_for(nq.section),
            )
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
    if exam not in ("pca", "devops", "genai"):
        raise HTTPException(400, "exam must be 'pca', 'devops', or 'genai'")
    return sessions_svc.leaderboard(exam, min(limit, 100))


# ---------- Static SPA ----------

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
