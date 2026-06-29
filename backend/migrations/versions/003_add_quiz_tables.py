"""add quizzes and quiz_items tables

Revision ID: 003
Revises: 002
Create Date: 2026-06-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quizzes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quiz_type", sa.String(20), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"])
    op.create_index("ix_quizzes_document_id", "quizzes", ["document_id"])

    op.create_table(
        "quiz_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "quiz_id",
            sa.Integer(),
            sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("content_front", sa.Text(), nullable=False),
        sa.Column("content_back", sa.Text(), nullable=True),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("correct_answer", sa.Integer(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
    )
    op.create_index("ix_quiz_items_quiz_id", "quiz_items", ["quiz_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_items_quiz_id", table_name="quiz_items")
    op.drop_table("quiz_items")
    op.drop_index("ix_quizzes_document_id", table_name="quizzes")
    op.drop_index("ix_quizzes_user_id", table_name="quizzes")
    op.drop_table("quizzes")
