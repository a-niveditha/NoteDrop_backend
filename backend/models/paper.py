import uuid
import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False)
    title = Column(String, nullable=True)
    authors = Column(String, nullable=True)
    arxiv_id = Column(String, nullable=True)
    pdf_url = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    indexing_status = Column(String, default="pending")  # pending | ready | failed
    added_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.timezone.utc)