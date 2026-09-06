import uuid
import datetime
from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True