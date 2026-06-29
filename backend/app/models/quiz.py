"""
app/models/quiz.py

Quiz, flashcard, and attempt storage models.

Nullable columns let one QuizItem table serve both types:
  - Quiz type  : content_front=question, options=["A","B","C","D"], correct_answer=0, explanation="..."
  - Flashcard  : content_front=front, content_back=back, options=null, correct_answer=null

QuizAttempt records a user's answers and score for one sitting.
Flashcard review sessions store score=null, total=null (no right/wrong).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quiz_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "quiz" | "flashcard"
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    items: Mapped[list["QuizItem"]] = relationship(
        "QuizItem", back_populates="quiz", cascade="all, delete-orphan", order_by="QuizItem.order_index"
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        "QuizAttempt", back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_front: Mapped[str] = mapped_column(Text, nullable=False)
    content_back: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    options: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    correct_answer: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="items")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quiz_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Each element is the 0-based option index the user picked (null = skipped).
    # Null for flashcard reviews — there are no right/wrong answers.
    answers: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="attempts")
