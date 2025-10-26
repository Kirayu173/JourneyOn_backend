from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.schemas.common import Envelope
from app.db.session import get_db
from app.services.user_service import create_user, authenticate_user_by_identifier
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> Envelope[dict[str, Any]]:
    """Register a new user, then issue a JWT token."""
    if not req.username or not req.password or not req.email:
        raise HTTPException(status_code=400, detail="invalid_registration_payload")

    user = create_user(db, username=req.username, email=req.email, password=req.password)
    token = create_access_token({"sub": str(user.id), "username": user.username, "email": user.email})
    return Envelope(code=0, msg="ok", data={"user": {"id": user.id, "username": user.username, "email": user.email}, "token": token})


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)) -> Envelope[dict[str, Any]]:
    """Authenticate by username/email and password, returning a JWT."""
    if not req.username_or_email or not req.password:
        raise HTTPException(status_code=400, detail="invalid_login_payload")

    user = authenticate_user_by_identifier(db, req.username_or_email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_access_token({"sub": str(user.id), "username": user.username, "email": user.email})
    return Envelope(code=0, msg="ok", data={"user": {"id": user.id, "username": user.username, "email": user.email}, "token": token})