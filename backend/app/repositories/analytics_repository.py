"""
All queries use SQL aggregates pushed to Postgres — no row-fetching in Python.
asyncio.gather() in the service layer fires all five concurrently.
"""

from datetime import datetime, timedelta

from sqlalchemy import Float, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.models.quiz import Quiz, QuizAttempt


async def count_documents(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(Document).where(Document.user_id == user_id)
    )
    return result.scalar_one()


async def count_quizzes(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(Quiz).where(Quiz.user_id == user_id)
    )
    return result.scalar_one()


async def count_chat_messages(db: AsyncSession, user_id: int) -> int:
    """Count user-role messages across all sessions owned by this user."""
    result = await db.execute(
        select(func.count())
        .select_from(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id, ChatMessage.role == "user")
    )
    return result.scalar_one()


async def weekly_score_trend(
    db: AsyncSession, user_id: int, weeks: int = 8
) -> list[dict]:
    """
    For each calendar week in the last `weeks` weeks, compute avg(score/total)*100
    over quiz attempts that have a non-null score.
    Returns rows ordered oldest-first so the frontend can draw a left-to-right line chart.
    """
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    # DATE_TRUNC truncates a timestamp to the start of its week (Monday in Postgres).
    # We cast score/total to float before dividing to avoid integer division.
    stmt = (
        select(
            func.date_trunc("week", QuizAttempt.completed_at).label("week_start"),
            (func.avg(QuizAttempt.score.cast(Float) / QuizAttempt.total) * 100).label("avg_score_pct"),
            func.count().label("attempts"),
        )
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.completed_at >= cutoff,
            QuizAttempt.score.isnot(None),
            QuizAttempt.total.isnot(None),
            QuizAttempt.total > 0,
        )
        .group_by(text("week_start"))
        .order_by(text("week_start"))
    )

    result = await db.execute(stmt)
    return [
        {"week_start": row.week_start, "avg_score_pct": round(row.avg_score_pct, 1), "attempts": row.attempts}
        for row in result.fetchall()
    ]


async def most_studied_documents(
    db: AsyncSession, user_id: int, limit: int = 5
) -> list[dict]:
    """
    Return the top `limit` documents by number of quizzes generated,
    including the document filename for display.
    """
    stmt = (
        select(
            Document.id.label("document_id"),
            Document.filename,
            func.count(Quiz.id).label("quiz_count"),
        )
        .join(Quiz, Quiz.document_id == Document.id)
        .where(Document.user_id == user_id)
        .group_by(Document.id, Document.filename)
        .order_by(func.count(Quiz.id).desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    return [
        {"document_id": row.document_id, "filename": row.filename, "quiz_count": row.quiz_count}
        for row in result.fetchall()
    ]
