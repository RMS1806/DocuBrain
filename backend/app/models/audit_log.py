"""
app/models/audit_log.py

Append-only audit log. Rows are inserted and never updated or deleted.
The application layer enforces this — no UPDATE or DELETE is ever issued
against this table. A future hardening step can add a Postgres rule or
row-level security policy to enforce it at the DB layer as well.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # SET NULL on user delete: keep the audit record even if the user is removed
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
