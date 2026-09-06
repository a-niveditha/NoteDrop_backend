import uuid
import datetime
from typing import Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: uuid.UUID
    message: str
    paper_ids: Optional[list[uuid.UUID]] = None


class ChatResponse(BaseModel):
    reply: str


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    message: str
    paper_ids: Optional[list[uuid.UUID]] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True