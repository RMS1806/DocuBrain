from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ChatSessionResponse(BaseModel):
    id: int
    title: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class SendMessageResponse(BaseModel):
    message: ChatMessageResponse
    ai_message: ChatMessageResponse
    sources: List[str] = []
