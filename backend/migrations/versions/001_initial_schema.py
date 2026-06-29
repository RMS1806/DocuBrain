"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="client"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("minio_path", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("upload_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=True, server_default="pending"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_documents_id", "documents", ["id"])
    op.create_index("ix_document_user_id", "documents", ["user_id"])

    # ── professional_links ────────────────────────────────────────────────────
    op.create_table(
        "professional_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("professional_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(), nullable=True, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_professional_links_id", "professional_links", ["id"])
    op.create_index("ix_professional_links_client_id", "professional_links", ["client_id"])
    op.create_index("ix_professional_links_professional_id", "professional_links", ["professional_id"])
    op.create_index("ix_prof_link_lookup", "professional_links", ["client_id", "professional_id"])

    # ── chat_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=True, server_default="New Chat"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chat_sessions_id", "chat_sessions", ["id"])
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_session_user_time", "chat_sessions", ["user_id", "created_at"])

    # ── chat_messages ─────────────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chat_messages_id", "chat_messages", ["id"])
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("professional_links")
    op.drop_table("documents")
    op.drop_table("users")
