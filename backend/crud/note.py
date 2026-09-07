import uuid
from sqlalchemy.orm import Session

from models.note import SharedNote


def get_shared_notes_for_room(db: Session, room_id: uuid.UUID) -> list[SharedNote]:
    """
    Returns every shared note in the room, regardless of who wrote it or which
    paper (if any) it's attached to. Used to give the chat AI full context on
    what the team has already noted, not just raw paper text.
    """
    return (
        db.query(SharedNote)
        .filter(SharedNote.room_id == room_id)
        .order_by(SharedNote.created_at.asc())
        .all()
    )


def notes_to_dicts(notes: list[SharedNote]) -> list[dict]:
    """Convert SharedNote rows into plain dicts for passing to the AI function."""
    return [
        {
            "type": n.type,
            "content": n.content,
            "paper_id": str(n.paper_id) if n.paper_id else None,
        }
        for n in notes
    ]