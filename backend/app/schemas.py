from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Auth ───────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: str = "client"

class UserResponse(UserBase):
    id: int
    role: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


# ── Documents ──────────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: int
    filename: str
    content_type: str | None = None
    file_size: int | None = None
    upload_date: datetime
    status: str
    summary: str | None = None

    class Config:
        from_attributes = True


# ── Legacy single-shot chat (kept for backward compat) ─────────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []


# ── Persistent Chat Sessions ───────────────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Chat"

class ChatSessionResponse(BaseModel):
    id: int
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str       # 'user' | 'assistant'
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class SendMessageRequest(BaseModel):
    content: str
    target_user_id: Optional[int] = None   # Professionals can query a client's docs

class SendMessageResponse(BaseModel):
    message: ChatMessageResponse
    ai_message: ChatMessageResponse
    sources: List[str] = []