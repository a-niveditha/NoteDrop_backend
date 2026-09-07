import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.chat import ChatRequest, ChatResponse, ChatMessageOut
from crud.chat import save_chat, get_chat_history, history_to_dicts
from crud.paper import get_papers_by_ids
from crud.note import get_shared_notes_for_room, notes_to_dicts
from ai.chat import answer  # swap this import target once teammate's real version lands

router = APIRouter(prefix="/rooms/{room_id}/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def send_message(room_id: uuid.UUID, payload: ChatRequest, db: Session = Depends(get_db)):
    # 1. Gate: every selected paper must be fully indexed before it can be chatted about
    if payload.paper_ids:
        papers = get_papers_by_ids(db, payload.paper_ids)

        found_ids = {p.id for p in papers}
        missing = [str(pid) for pid in payload.paper_ids if pid not in found_ids]
        if missing:
            raise HTTPException(404, f"Paper(s) not found: {missing}")

        not_ready = [str(p.id) for p in papers if p.indexing_status != "ready"]
        if not_ready:
            raise HTTPException(400, f"Paper(s) still processing, try again shortly: {not_ready}")

    # 2. Save the user's message
    save_chat(db, room_id, payload.user_id, "user", payload.message, payload.paper_ids)

    # 3. Pull this user's recent history in this room, for conversational context
    history_rows = get_chat_history(db, room_id, payload.user_id)
    history = history_to_dicts(history_rows)

    # 4. Pull every shared note in the room — always all of them, not user-selected,
    #    so the AI has full visibility into what the team has already found/flagged
    shared_note_rows = get_shared_notes_for_room(db, room_id)
    shared_notes = notes_to_dicts(shared_note_rows)

    # 5. Call the AI function (stub for now, swapped for real RAG later)
    reply = answer(payload.paper_ids or [], payload.message, history, shared_notes)

    # 6. Save and return the assistant's reply
    save_chat(db, room_id, payload.user_id, "assistant", reply, payload.paper_ids)

    return ChatResponse(reply=reply)


@router.get("", response_model=list[ChatMessageOut])
def get_messages(room_id: uuid.UUID, user_id: uuid.UUID, db: Session = Depends(get_db)):
    # Chat is local to each user — only ever returns their own messages in this room
    messages = get_chat_history(db, room_id, user_id, limit=100)
    return messages