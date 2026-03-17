"""
backend/app/models.py

SQLAlchemy ORM models for DocuBrain.

Enterprise additions vs the prototype:
- FK columns now carry index=True so joins are O(log N) instead of sequential scans.
- Composite indices on hot lookup patterns (professional link checks, session list by user).
- Base is imported from the new async-aware database module.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String, default="client")  # "client" | "professional"

    documents = relationship("Document", back_populates="owner")
    chat_sessions = relationship(
        "ChatSession", back_populates="owner", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        # Fast lookup: "give me all documents for user X"
        Index("ix_document_user_id", "user_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    minio_path = Column(String)
    content_type = Column(String)
    file_size = Column(Integer)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")
    summary = Column(Text, nullable=True)

    # index=True on the FK so filter(Document.user_id == x) uses the index.
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    owner = relationship("User", back_populates="documents")


class ProfessionalLink(Base):
    __tablename__ = "professional_links"
    __table_args__ = (
        # Composite index: covers the "is user X linked to professional Y?" query
        # used in every document-sharing and chat auth check.
        Index("ix_prof_link_lookup", "client_id", "professional_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    # index=True makes single-column lookups ("all clients for pro Y") fast too.
    client_id = Column(Integer, ForeignKey("users.id"), index=True)
    professional_id = Column(Integer, ForeignKey("users.id"), index=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Chat Memory Models ─────────────────────────────────────────────────────────

class ChatSession(Base):
    """
    A named conversation thread belonging to a single user.
    Title is auto-generated from the user's first message.
    """
    __tablename__ = "chat_sessions"
    __table_args__ = (
        # Composite index: covers "list all sessions for user X ordered newest first"
        Index("ix_chat_session_user_time", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    # Standalone index for single-column filters (ownership checks).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """
    A single turn within a ChatSession.
    role: 'user' | 'assistant'
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    # Index on FK: "fetch all messages in session X" is the hot path.
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String, nullable=False)   # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")