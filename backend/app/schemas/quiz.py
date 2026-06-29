from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class QuizGenerateRequest(BaseModel):
    document_id: int
    quiz_type: Literal["quiz", "flashcard"] = "quiz"
    count: int = Field(default=10, ge=3, le=30, description="Number of questions/cards to generate")


class QuizItemResponse(BaseModel):
    id: int
    order_index: int
    content_front: str
    content_back: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[int] = None
    explanation: Optional[str] = None

    class Config:
        from_attributes = True


class QuizResponse(BaseModel):
    id: int
    document_id: int
    quiz_type: str
    item_count: int
    created_at: datetime
    items: List[QuizItemResponse]

    class Config:
        from_attributes = True


class QuizListItem(BaseModel):
    id: int
    document_id: int
    quiz_type: str
    item_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Attempt schemas ───────────────────────────────────────────────────────────

class QuizAttemptRequest(BaseModel):
    """
    Submit answers for a quiz. Each element is the 0-based option index the user picked.
    Send null for a skipped question. For flashcard reviews, send an empty list.
    """
    answers: List[Optional[int]] = Field(default_factory=list)


class AttemptBreakdownItem(BaseModel):
    item_id: int
    question: str
    your_answer: Optional[int]
    correct_answer: Optional[int]
    is_correct: bool
    explanation: Optional[str]


class QuizAttemptResponse(BaseModel):
    attempt_id: int
    quiz_type: str
    score: Optional[int] = None
    total: Optional[int] = None
    score_pct: Optional[float] = None
    breakdown: Optional[List[AttemptBreakdownItem]] = None
    message: Optional[str] = None


# ── Progress schemas ──────────────────────────────────────────────────────────

class RecentAttempt(BaseModel):
    attempt_id: int
    quiz_id: int
    quiz_type: str
    document_id: int
    score: Optional[int]
    total: Optional[int]
    score_pct: Optional[float]
    completed_at: datetime


class ProgressStats(BaseModel):
    total_quizzes_attempted: int
    total_questions_answered: int
    average_score_pct: Optional[float]
    best_score_pct: Optional[float]
    documents_studied: int
    recent_attempts: List[RecentAttempt]
