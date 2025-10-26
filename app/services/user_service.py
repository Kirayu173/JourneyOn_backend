from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import User
from app.core.security import hash_password, verify_password


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, username: str, email: str, password: str) -> User:
    """Create a new user with hashed password.

    Raises HTTPException 409 on uniqueness conflicts.
    """
    user = User(username=username, email=email, password_hash=hash_password(password))
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="user_already_exists")


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate by email and password."""
    user = get_user_by_email(db, email)
    if not user or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def authenticate_user_by_identifier(db: Session, username_or_email: str, password: str) -> Optional[User]:
    """Authenticate by username or email, returning the User or None."""
    user = None
    if "@" in username_or_email:
        user = get_user_by_email(db, username_or_email)
    else:
        user = get_user_by_username(db, username_or_email)
    if not user or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user