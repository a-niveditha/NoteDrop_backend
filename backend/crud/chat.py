import uuid
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.chat import Chat


def save_chat(
    db: Session,
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    message: str,
    paper_ids: list[uuid.UUID] | None = None,
) -> Chat:
    chat = Chat(
        room_id=room_id,
        user_id=user_id,
        role=role,
        message=message,
        paper_ids=paper_ids,
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def get_chat_history(
    db: Session,
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[Chat]:
    """
    Returns this user's chat messages in this room, most recent first (then
    reversed to chronological order for feeding into the AI as context).
    Chat is local to each user — never pulls other users' messages.
    """
    messages = (
        db.query(Chat)
        .filter(and_(Chat.room_id == room_id, Chat.user_id == user_id))
        .order_by(Chat.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


def history_to_dicts(messages: list[Chat]) -> list[dict]:
    """Convert Chat rows into plain dicts for passing to the AI function."""
    return [{"role": m.role, "content": m.message} for m in messages]