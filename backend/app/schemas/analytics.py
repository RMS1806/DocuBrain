from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class WeeklyScoreTrend(BaseModel):
    week_start: datetime
    avg_score_pct: float
    attempts: int


class MostStudiedDocument(BaseModel):
    document_id: int
    filename: str
    quiz_count: int


class AnalyticsDashboard(BaseModel):
    documents_uploaded: int
    quizzes_generated: int
    chat_messages_sent: int
    weekly_score_trend: List[WeeklyScoreTrend]
    most_studied_documents: List[MostStudiedDocument]
