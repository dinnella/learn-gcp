"""Pydantic models for the practice-test API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Exam = Literal["pca", "devops"]
Difficulty = Literal["easy", "medium", "hard"]
Confidence = Literal["confident", "narrowed", "guess"]


class DocLink(BaseModel):
    title: str
    url: str


class Question(BaseModel):
    id: str
    exam: Exam
    section: str
    difficulty: Difficulty = "medium"
    text: str
    options: list[str]
    explanation: str | None = None
    doc_links: list[DocLink] = Field(default_factory=list)
    # `correct_index` is read separately so it never leaks via response_model.


class QuestionForClient(BaseModel):
    """Question without the answer key."""
    id: str
    exam: Exam
    section: str
    difficulty: Difficulty
    text: str
    options: list[str]


class StartSessionRequest(BaseModel):
    exam: Exam
    num_questions: int = Field(default=10, ge=1, le=50)
    sections: list[str] | None = None
    difficulties: list[Difficulty] | None = None
    player_name: str | None = Field(default=None, max_length=32)


class AnswerRequest(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=3)
    confidence: Confidence = "confident"


class AnswerResponse(BaseModel):
    correct: bool
    correct_index: int
    explanation: str | None = None
    doc_links: list[DocLink] = Field(default_factory=list)
    next_question: QuestionForClient | None = None
    progress: dict


class ReportCardRecommendation(BaseModel):
    section: str
    score_pct: float
    suggested_action: str
    docs: list[DocLink] = Field(default_factory=list)


class ReportCard(BaseModel):
    overall_grade: str         # A / B / C / D / F
    passed_mock: bool
    weak_sections: list[str]
    recommendations: list[ReportCardRecommendation]
    next_session_prompt: str
    next_session_config: dict  # ready-to-POST body for /api/sessions


class SessionSummary(BaseModel):
    id: str
    exam: Exam
    started_at: str
    finished_at: str | None
    answered: int
    total: int
    score_pct: float | None
    per_section: dict[str, dict]
    per_difficulty: dict[str, dict]
    player_name: str | None = None
    report_card: ReportCard | None = None


class SessionStartResponse(BaseModel):
    session_id: str
    total: int
    first_question: QuestionForClient


class ScoreEntry(BaseModel):
    player_name: str = Field(min_length=1, max_length=32)
    exam: Exam
    score_pct: float
    answered: int
    total: int
    difficulty_mix: dict[str, int]
    finished_at: str
    session_id: str


class LeaderboardResponse(BaseModel):
    exam: Exam
    entries: list[ScoreEntry]
