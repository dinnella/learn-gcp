"""Pydantic models for the practice-test API.

Kept intentionally small — we use Firestore document shapes directly,
and only model the boundaries (request/response).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Exam = Literal["pca", "devops"]
Confidence = Literal["confident", "narrowed", "guess"]


class Question(BaseModel):
    id: str
    exam: Exam
    section: str           # e.g. "PCA-3.1", "DevOps-4.3"
    text: str
    options: list[str]     # exactly 4 options
    # `correct` is intentionally absent in API responses to clients mid-quiz.
    explanation: str | None = None


class QuestionForClient(BaseModel):
    """Question without the answer key."""
    id: str
    exam: Exam
    section: str
    text: str
    options: list[str]


class StartSessionRequest(BaseModel):
    exam: Exam
    num_questions: int = Field(default=10, ge=1, le=50)
    sections: list[str] | None = None  # filter; None = any


class AnswerRequest(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=3)
    confidence: Confidence = "confident"


class AnswerResponse(BaseModel):
    correct: bool
    correct_index: int
    explanation: str | None = None
    next_question: QuestionForClient | None = None
    progress: dict       # {"answered": n, "total": m}


class SessionSummary(BaseModel):
    id: str
    exam: Exam
    started_at: str
    finished_at: str | None
    answered: int
    total: int
    score_pct: float | None
    per_section: dict[str, dict]   # section -> {"correct": n, "total": m, "pct": float}


class SessionStartResponse(BaseModel):
    session_id: str
    total: int
    first_question: QuestionForClient
