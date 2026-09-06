import uuid
from sqlalchemy.orm import Session

from models.paper import Paper


def get_papers_by_ids(db: Session, paper_ids: list[uuid.UUID]) -> list[Paper]:
    if not paper_ids:
        return []
    return db.query(Paper).filter(Paper.id.in_(paper_ids)).all()