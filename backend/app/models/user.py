from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="client")  # "client" | "professional"

    documents = relationship("Document", back_populates="owner")
    chat_sessions = relationship(
        "ChatSession", back_populates="owner", cascade="all, delete-orphan"
    )


class ProfessionalLink(Base):
    __tablename__ = "professional_links"
    __table_args__ = (
        Index("ix_prof_link_lookup", "client_id", "professional_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), index=True)
    professional_id = Column(Integer, ForeignKey("users.id"), index=True)
    status = Column(String, default="active")
    created_at = Column(DateTime)
