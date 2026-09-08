import uuid
import datetime
from pydantic import BaseModel


class PaperOut(BaseModel):
    id: uuid.UUID
    room_id: uuid.UUID
    title: str | None
    authors: str | None
    arxiv_id: str | None
    pdf_url: str | None
    summary: str | None
    indexing_status: str
    added_by: uuid.UUID | None
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class ArxivImportRequest(BaseModel):
    user_id: uuid.UUID
    arxiv_id: str
    pdf_url: str
    title: str | None = None
    authors: str | None = None
