from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quiz import Quiz, QuizAttempt, QuizItem


async def create_quiz(
    db: AsyncSession,
    user_id: int,
    document_id: int,
    quiz_type: str,
    items_data: list[dict],
) -> Quiz:
    quiz = Quiz(
        user_id=user_id,
        document_id=document_id,
        quiz_type=quiz_type,
        item_count=len(items_data),
    )
    db.add(quiz)
    await db.flush()  # populate quiz.id before inserting items

    for i, item in enumerate(items_data):
        db.add(QuizItem(quiz_id=quiz.id, order_index=i, **item))

    await db.commit()

    result = await db.execute(
        select(Quiz).where(Quiz.id == quiz.id).options(selectinload(Quiz.items))
    )
    return result.scalars().first()


async def get_quiz(db: AsyncSession, quiz_id: int, user_id: int) -> Quiz | None:
    result = await db.execute(
        select(Quiz)
        .where(Quiz.id == quiz_id, Quiz.user_id == user_id)
        .options(selectinload(Quiz.items))
    )
    return result.scalars().first()


async def list_quizzes(db: AsyncSession, user_id: int) -> list[Quiz]:
    result = await db.execute(
        select(Quiz).where(Quiz.user_id == user_id).order_by(Quiz.created_at.desc())
    )
    return list(result.scalars().all())


# ── Attempt CRUD ──────────────────────────────────────────────────────────────

async def create_attempt(
    db: AsyncSession,
    user_id: int,
    quiz_id: int,
    answers: list | None,
    score: int | None,
    total: int | None,
) -> QuizAttempt:
    attempt = QuizAttempt(
        user_id=user_id,
        quiz_id=quiz_id,
        answers=answers,
        score=score,
        total=total,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def list_attempts(db: AsyncSession, user_id: int, limit: int = 20) -> list[QuizAttempt]:
    """Load attempts with their parent quiz (for document_id and quiz_type)."""
    result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user_id)
        .options(selectinload(QuizAttempt.quiz))
        .order_by(QuizAttempt.completed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
