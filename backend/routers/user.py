from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.user import UserCreate, UserOut
from crud.user import create_user

router = APIRouter(prefix="/user", tags=["user"])


@router.post("", response_model=UserOut)
def create_new_user(payload: UserCreate, db: Session = Depends(get_db)):
    # No password, no verification — just a name, per the lightweight auth plan.
    # Frontend stores the returned id (e.g. in localStorage) and sends it as
    # user_id on every subsequent request.
    return create_user(db, payload.name)