"""Pydantic models for the practice-test API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Exam = Literal["architect", "devops", "genai"]
Difficulty = Literal["easy", "medium", "hard"]
Confidence = Literal["confident", "narrowed", "guess"]
SessionMode = Literal["classic", "progressive", "arcade"]


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
    section_title: str
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
    section_title: str
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


# ---------------------------------------------------------------------------
# Progressive mode
# ---------------------------------------------------------------------------

ProgressiveEndedReason = Literal["strikes", "hard_exhausted", "abandoned"]


class StartProgressiveSessionRequest(BaseModel):
    player_name: str | None = Field(default=None, max_length=32)
    max_strikes: int = Field(default=3, ge=1, le=5)


class ProgressiveSessionStartResponse(BaseModel):
    session_id: str
    mode: SessionMode = "progressive"
    max_strikes: int
    first_question: QuestionForClient


class ProgressiveAnswerResponse(BaseModel):
    correct: bool
    correct_index: int
    points_awarded: int
    explanation: str | None = None
    doc_links: list[DocLink] = Field(default_factory=list)
    next_question: QuestionForClient | None = None
    progress: dict
    ended: bool = False
    ended_reason: ProgressiveEndedReason | None = None


class ProgressiveSessionSummary(BaseModel):
    id: str
    mode: SessionMode = "progressive"
    exams: list[str]
    started_at: str
    finished_at: str | None
    answered: int
    correct: int
    accuracy_pct: float
    max_streak: int
    score_total: int
    strikes: int
    max_strikes: int
    ended_reason: ProgressiveEndedReason | None
    per_difficulty: dict[str, dict]
    per_exam: dict[str, dict]
    percentile: float | None = None
    player_name: str | None = None


class ProgressiveScoreEntry(BaseModel):
    player_name: str = Field(min_length=1, max_length=32)
    score_total: int
    answered: int
    correct: int
    max_streak: int
    difficulty_mix: dict[str, int]
    per_exam: dict[str, dict]
    ended_reason: Literal["strikes", "hard_exhausted"]
    finished_at: str
    session_id: str


class ProgressiveLeaderboardResponse(BaseModel):
    entries: list[ProgressiveScoreEntry]
    total_runs: int


# ---------------------------------------------------------------------------
# Arcade mode
# ---------------------------------------------------------------------------

ArcadeEndedReason = Literal["time", "exhausted", "abandoned"]


class StartArcadeSessionRequest(BaseModel):
    player_name: str | None = Field(default=None, max_length=32)
    starting_seconds: int = Field(default=60, ge=30, le=600)


class ArcadeQuestionForClient(BaseModel):
    id: str
    exam: str
    section: str
    section_title: str
    difficulty: Difficulty
    text: str
    options: list[str]
    points_if_correct: int
    time_bonus_seconds: int


class ArcadeSessionStartResponse(BaseModel):
    session_id: str
    mode: SessionMode = "arcade"
    starting_seconds: int
    time_remaining_ms: int
    first_question: ArcadeQuestionForClient


class ArcadeAnswerRequest(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=3)
    confidence: Confidence = "confident"
    client_elapsed_ms: int = Field(ge=0)


class ArcadeAnswerResponse(BaseModel):
    correct: bool
    correct_index: int
    points_awarded: int
    time_bonus_seconds: int
    time_penalty_seconds: int = 0
    time_remaining_ms: int
    score_total: int
    correct_total: int
    correct_in_level: int
    level: int
    max_streak: int
    current_streak: int
    explanation: str | None = None
    doc_links: list[DocLink] = Field(default_factory=list)
    next_question: ArcadeQuestionForClient | None = None
    level_up_pending: bool = False
    ended: bool = False
    ended_reason: ArcadeEndedReason | None = None


class ArcadeContinueResponse(BaseModel):
    level: int
    time_remaining_ms: int
    next_question: ArcadeQuestionForClient


class ArcadeSessionSummary(BaseModel):
    id: str
    mode: SessionMode = "arcade"
    started_at: str
    finished_at: str | None
    score_total: int
    level_reached: int
    correct_total: int
    answered_total: int
    accuracy_pct: float
    max_streak: int
    duration_seconds: int | None
    per_difficulty: dict[str, dict]
    per_exam: dict[str, dict]
    ended_reason: ArcadeEndedReason | None
    player_name: str | None = None


class ArcadeScoreEntry(BaseModel):
    player_name: str = Field(min_length=1, max_length=32)
    score_total: int
    level_reached: int
    correct_total: int
    answered_total: int
    max_streak: int
    longest_combo_pts: int
    duration_seconds: int
    finished_at: str
    session_id: str


class ArcadeLeaderboardResponse(BaseModel):
    entries: list[ArcadeScoreEntry]
    total_runs: int
