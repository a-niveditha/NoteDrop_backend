from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.room import RoomCreate, RoomJoin, RoomOut
from crud.room import create_room, get_room_by_code, add_room_member

router = APIRouter(prefix="/room", tags=["room"])


@router.post("", response_model=RoomOut)
def create_new_room(payload: RoomCreate, db: Session = Depends(get_db)):
    return create_room(db, payload.name, payload.created_by)


@router.post("/join", response_model=RoomOut)
def join_room(payload: RoomJoin, db: Session = Depends(get_db)):
    room = get_room_by_code(db, payload.code)
    if not room:
        raise HTTPException(404, "No room found with that code")

    add_room_member(db, room.id, payload.user_id)
    return room