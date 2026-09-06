from sqlalchemy.orm import Session

from models.user import User


def create_user(db: Session, name: str) -> User:
    user = User(name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user