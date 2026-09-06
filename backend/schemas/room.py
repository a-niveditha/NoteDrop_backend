import uuid
import datetime
from pydantic import BaseModel


class RoomCreate(BaseModel):
    name: str
    created_by: uuid.UUID


class RoomJoin(BaseModel):
    code: str
    user_id: uuid.UUID


class RoomOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    created_by: uuid.UUID | None
    created_at: datetime.datetime

    class Config:
        from_attributes = True