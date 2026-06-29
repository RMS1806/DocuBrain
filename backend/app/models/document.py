from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_document_user_id", "user_id"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    minio_path = Column(String, nullable=False)
    content_type = Column(String)
    file_size = Column(Integer)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")
    summary = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    owner = relationship("User", back_populates="documents")
