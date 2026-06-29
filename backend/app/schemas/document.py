from datetime import datetime
from pydantic import BaseModel


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
