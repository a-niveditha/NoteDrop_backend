import os
import shutil
import uuid

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ai.pdf_parser import extract_text
from crud.paper import create_paper, get_papers_for_room, update_paper_after_processing
from database import get_db
from schemas.paper import ArxivImportRequest, PaperOut

router = APIRouter(prefix="/rooms/{room_id}/papers", tags=["papers"])

STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "papers")


def _process_paper(db: Session, paper, file_path: str):
    # Never leaves a paper stuck on "pending" — always ends in ready or failed.
    try:
        text = extract_text(file_path)
        update_paper_after_processing(db, paper, parsed_text=text, summary="", status="ready")
    except Exception:
        update_paper_after_processing(db, paper, parsed_text="", summary="", status="failed")


@router.post("/upload", response_model=PaperOut)
def upload_paper(
    room_id: uuid.UUID,
    user_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    paper = create_paper(db, room_id=room_id, added_by=user_id, title=file.filename)

    os.makedirs(STORAGE_DIR, exist_ok=True)
    file_path = os.path.join(STORAGE_DIR, f"{paper.id}.pdf")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    _process_paper(db, paper, file_path)
    return paper


@router.post("/from-arxiv", response_model=PaperOut)
def add_paper_from_arxiv(room_id: uuid.UUID, payload: ArxivImportRequest, db: Session = Depends(get_db)):
    paper = create_paper(
        db,
        room_id=room_id,
        added_by=payload.user_id,
        title=payload.title,
        authors=payload.authors,
        arxiv_id=payload.arxiv_id,
        pdf_url=payload.pdf_url,
    )

    os.makedirs(STORAGE_DIR, exist_ok=True)
    file_path = os.path.join(STORAGE_DIR, f"{paper.id}.pdf")
    try:
        response = requests.get(payload.pdf_url, timeout=30)
        response.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(response.content)
    except Exception:
        update_paper_after_processing(db, paper, parsed_text="", summary="", status="failed")
        return paper

    _process_paper(db, paper, file_path)
    return paper


@router.get("", response_model=list[PaperOut])
def list_papers(room_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_papers_for_room(db, room_id)
