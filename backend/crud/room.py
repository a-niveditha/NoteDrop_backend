import random
import string
import uuid
from sqlalchemy.orm import Session

from models.room import Room, RoomMember


def _generate_room_code(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_room(db: Session, name: str, created_by: uuid.UUID) -> Room:
    # Keep generating a code until we get one that isn't already taken
    # (collisions are rare at 6 chars, but cheap to guard against)
    while True:
        code = _generate_room_code()
        if not db.query(Room).filter(Room.code == code).first():
            break

    room = Room(name=name, code=code, created_by=created_by)
    db.add(room)
    db.commit()
    db.refresh(room)

    # Creator automatically becomes the first member
    membership = RoomMember(room_id=room.id, user_id=created_by)
    db.add(membership)
    db.commit()

    return room


def get_room_by_code(db: Session, code: str) -> Room | None:
    return db.query(Room).filter(Room.code == code).first()


def add_room_member(db: Session, room_id: uuid.UUID, user_id: uuid.UUID) -> RoomMember:
    existing = (
        db.query(RoomMember)
        .filter(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
        .first()
    )
    if existing:
        return existing

    membership = RoomMember(room_id=room_id, user_id=user_id)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership