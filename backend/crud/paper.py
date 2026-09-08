import uuid
from sqlalchemy.orm import Session

from models.paper import Paper


def get_papers_by_ids(db: Session, paper_ids: list[uuid.UUID]) -> list[Paper]:
    if not paper_ids:
        return []
    return db.query(Paper).filter(Paper.id.in_(paper_ids)).all()


def create_paper(
    db: Session,
    room_id: uuid.UUID,
    added_by: uuid.UUID,
    title: str | None = None,
    authors: str | None = None,
    arxiv_id: str | None = None,
    pdf_url: str | None = None,
) -> Paper:
    paper = Paper(
        room_id=room_id,
        added_by=added_by,
        title=title,
        authors=authors,
        arxiv_id=arxiv_id,
        pdf_url=pdf_url,
        indexing_status="pending",
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


def update_paper_after_processing(
    db: Session,
    paper: Paper,
    parsed_text: str,
    summary: str,
    status: str = "ready",
) -> Paper:
    paper.parsed_text = parsed_text
    paper.summary = summary
    paper.indexing_status = status
    db.commit()
    db.refresh(paper)
    return paper


def get_papers_for_room(db: Session, room_id: uuid.UUID) -> list[Paper]:
    return db.query(Paper).filter(Paper.room_id == room_id).all()