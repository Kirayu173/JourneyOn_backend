from __future__ import annotations

from typing import Dict

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.core.security import verify_token

# OAuth2 scheme used for token extraction (Authorization: Bearer <token>)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Decode JWT and load the current user from the database."""
    try:
        payload = verify_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="invalid_token")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="invalid_token_subject")

    user = db.get(User, int(sub))
    if user is None:
        raise HTTPException(status_code=401, detail="user_not_found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure that the current user is an administrator."""

    meta: Dict | None = getattr(user, "meta", None)
    is_admin = False
    if isinstance(meta, dict):
        is_admin = bool(meta.get("is_admin"))
    if not is_admin:
        raise HTTPException(status_code=403, detail="admin_required")
    return user