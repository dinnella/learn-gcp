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
from . import progressive as progressive_svc
from . import arcade as arcade_svc
from .db import QUESTIONS, get_db
from .models import (
    AnswerRequest,
    AnswerResponse,
    ArcadeAnswerRequest,
    ArcadeAnswerResponse,
    ArcadeContinueResponse,
    ArcadeLeaderboardResponse,
    ArcadeQuestionForClient,
    ArcadeScoreEntry,
    ArcadeSessionStartResponse,
    ArcadeSessionSummary,
    DocLink,
    LeaderboardResponse,
    ProgressiveAnswerResponse,
    ProgressiveLeaderboardResponse,
    ProgressiveScoreEntry,
    ProgressiveSessionStartResponse,
    ProgressiveSessionSummary,
    QuestionForClient,
    ScoreEntry,
    SessionStartResponse,
    SessionSummary,
    StartArcadeSessionRequest,
    StartProgressiveSessionRequest,
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
_APP_ENV = os.environ.get("APP_ENV", "").strip().lower()
if _APP_ENV == "production" and not _EDGE_SECRET:
    # Fail closed: in production, refuse to boot without the shared secret.
    # Without it the middleware would let direct *.run.app traffic bypass
    # Cloudflare's WAF and rate limit entirely.
    raise RuntimeError(
        "EDGE_SHARED_SECRET is required when APP_ENV=production; refusing to start."
    )
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
                "id": "architect",
                "name": "Professional Cloud Architect",
                "sections": _sections_with_titles("architect"),
                "difficulties": list_difficulties("architect"),
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
        abandon_secret=result.get("abandon_secret"),
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
        submit_token=result.get("submit_token"),
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
    # One-time eligibility token issued by the server when the run finished.
    # Without a valid, unexpired, unspent token the leaderboard write is rejected.
    submit_token: str = Field(min_length=8, max_length=128)


class AbandonRequest(BaseModel):
    # Per-session secret returned in the start response. Required to abandon
    # the run so a third party who only knows the session ID cannot grief
    # an active player. Optional in the type only for backward-compat; the
    # server treats absence as failure when a hash is stored on the doc.
    abandon_secret: str | None = Field(default=None, max_length=128)


@app.post("/api/sessions/{sid}/score", response_model=ScoreEntry)
def submit_score(sid: str, req: SubmitScoreRequest) -> ScoreEntry:
    try:
        return sessions_svc.submit_score(sid, req.player_name, req.submit_token)
    except PermissionError as e:
        raise HTTPException(401, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/leaderboard/{exam}", response_model=LeaderboardResponse)
def leaderboard(exam: str, limit: int = 20) -> LeaderboardResponse:
    if exam not in ("architect", "devops", "genai"):
        raise HTTPException(400, "exam must be 'architect', 'devops', or 'genai'")
    return sessions_svc.leaderboard(exam, min(limit, 100))


# ---------- Progressive mode ----------

@app.post("/api/progressive/sessions", response_model=ProgressiveSessionStartResponse)
def progressive_start(req: StartProgressiveSessionRequest) -> ProgressiveSessionStartResponse:
    try:
        result = progressive_svc.start_progressive_session(req.player_name, req.max_strikes)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    fq = result["first_question"]
    return ProgressiveSessionStartResponse(
        session_id=result["session_id"],
        max_strikes=result["max_strikes"],
        first_question=QuestionForClient(**fq),
        abandon_secret=result.get("abandon_secret"),
    )


@app.post("/api/progressive/sessions/{sid}/answer", response_model=ProgressiveAnswerResponse)
def progressive_answer(sid: str, req: AnswerRequest) -> ProgressiveAnswerResponse:
    try:
        result = progressive_svc.record_progressive_answer(
            sid, req.question_id, req.selected_index, req.confidence
        )
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    nq_payload = result.get("next_question")
    nq_model = QuestionForClient(**nq_payload) if nq_payload else None
    return ProgressiveAnswerResponse(
        correct=result["correct"],
        correct_index=result["correct_index"],
        points_awarded=result["points_awarded"],
        explanation=result["explanation"],
        doc_links=[DocLink(**d) for d in result["doc_links"]],
        next_question=nq_model,
        progress=result["progress"],
        ended=result["ended"],
        ended_reason=result["ended_reason"],
        submit_token=result.get("submit_token"),
    )


@app.get("/api/progressive/sessions/{sid}", response_model=ProgressiveSessionSummary)
def progressive_summary(sid: str) -> ProgressiveSessionSummary:
    s = progressive_svc.progressive_summary(sid)
    if s is None:
        raise HTTPException(404, "session not found")
    return s


@app.post("/api/progressive/sessions/{sid}/score", response_model=ProgressiveScoreEntry)
def progressive_submit_score(sid: str, req: SubmitScoreRequest) -> ProgressiveScoreEntry:
    try:
        return progressive_svc.submit_progressive_score(sid, req.player_name, req.submit_token)
    except PermissionError as e:
        raise HTTPException(401, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/progressive/leaderboard", response_model=ProgressiveLeaderboardResponse)
def progressive_lb(limit: int = 20) -> ProgressiveLeaderboardResponse:
    return progressive_svc.progressive_leaderboard(min(limit, 100))


@app.post("/api/progressive/sessions/{sid}/abandon", response_model=ProgressiveSessionSummary)
def progressive_abandon(sid: str, req: AbandonRequest | None = None) -> ProgressiveSessionSummary:
    secret = req.abandon_secret if req else None
    try:
        return progressive_svc.abandon_progressive_session(sid, secret)
    except PermissionError as e:
        raise HTTPException(401, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ---------- Arcade mode ----------

@app.post("/api/arcade/sessions", response_model=ArcadeSessionStartResponse)
def arcade_start(req: StartArcadeSessionRequest) -> ArcadeSessionStartResponse:
    try:
        result = arcade_svc.start_arcade_session(req.player_name, req.starting_seconds)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return ArcadeSessionStartResponse(
        session_id=result["session_id"],
        starting_seconds=result["starting_seconds"],
        time_remaining_ms=result["time_remaining_ms"],
        first_question=ArcadeQuestionForClient(**result["first_question"]),
        abandon_secret=result.get("abandon_secret"),
    )


@app.post("/api/arcade/sessions/{sid}/answer", response_model=ArcadeAnswerResponse)
def arcade_answer(sid: str, req: ArcadeAnswerRequest) -> ArcadeAnswerResponse:
    try:
        r = arcade_svc.record_arcade_answer(
            sid, req.question_id, req.selected_index, req.confidence, req.client_elapsed_ms
        )
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    nq = ArcadeQuestionForClient(**r["next_question"]) if r["next_question"] else None
    return ArcadeAnswerResponse(
        correct=r["correct"],
        correct_index=r["correct_index"],
        points_awarded=r["points_awarded"],
        time_bonus_seconds=r["time_bonus_seconds"],
        time_penalty_seconds=r.get("time_penalty_seconds", 0),
        time_remaining_ms=r["time_remaining_ms"],
        score_total=r["score_total"],
        correct_total=r["correct_total"],
        correct_in_level=r["correct_in_level"],
        level=r["level"],
        max_streak=r["max_streak"],
        current_streak=r["current_streak"],
        explanation=r["explanation"],
        doc_links=[DocLink(**d) for d in r["doc_links"]],
        next_question=nq,
        level_up_pending=r["level_up_pending"],
        ended=r["ended"],
        ended_reason=r["ended_reason"],
        submit_token=r.get("submit_token"),
    )


@app.post("/api/arcade/sessions/{sid}/continue", response_model=ArcadeContinueResponse)
def arcade_continue(sid: str) -> ArcadeContinueResponse:
    try:
        r = arcade_svc.continue_arcade_session(sid)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return ArcadeContinueResponse(
        level=r["level"],
        time_remaining_ms=r["time_remaining_ms"],
        next_question=ArcadeQuestionForClient(**r["next_question"]),
    )


@app.get("/api/arcade/sessions/{sid}", response_model=ArcadeSessionSummary)
def arcade_session_summary(sid: str) -> ArcadeSessionSummary:
    s = arcade_svc.arcade_summary(sid)
    if s is None:
        raise HTTPException(404, "session not found")
    return s


@app.post("/api/arcade/sessions/{sid}/score", response_model=ArcadeScoreEntry)
def arcade_submit_score(sid: str, req: SubmitScoreRequest) -> ArcadeScoreEntry:
    try:
        return arcade_svc.submit_arcade_score(sid, req.player_name, req.submit_token)
    except PermissionError as e:
        raise HTTPException(401, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/arcade/leaderboard", response_model=ArcadeLeaderboardResponse)
def arcade_lb(limit: int = 20) -> ArcadeLeaderboardResponse:
    return arcade_svc.arcade_leaderboard(min(limit, 100))


@app.post("/api/arcade/sessions/{sid}/abandon", response_model=ArcadeSessionSummary)
def arcade_abandon(sid: str, req: AbandonRequest | None = None) -> ArcadeSessionSummary:
    secret = req.abandon_secret if req else None
    try:
        return arcade_svc.abandon_arcade_session(sid, secret)
    except PermissionError as e:
        raise HTTPException(401, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ---------- Static SPA ----------

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(
        _STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles that adds Cache-Control: no-cache so Cloudflare/browsers
    always revalidate JS and CSS after a new deploy."""

    async def __call__(self, scope, receive, send) -> None:  # type: ignore[override]
        async def patched_send(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"cache-control", b"no-cache, must-revalidate"))
                message["headers"] = headers
            await send(message)

        await super().__call__(scope, receive, patched_send)


app.mount("/static", NoCacheStaticFiles(directory=_STATIC_DIR), name="static")
