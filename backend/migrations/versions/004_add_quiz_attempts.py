"""add quiz_attempts table

Revision ID: 004
Revises: 003
Create Date: 2026-06-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quiz_id",
            sa.Integer(),
            sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # answers: [0, 2, null, 1, ...] — null means the user skipped that question.
        # Null for the entire column on flashcard reviews.
        sa.Column("answers", postgresql.JSONB(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=True),
        sa.Column(
            "completed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])
    op.create_index("ix_quiz_attempts_completed_at", "quiz_attempts", ["completed_at"])


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_completed_at", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_quiz_id", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
