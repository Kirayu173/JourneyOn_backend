from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.common import Envelope
from app.services.user_service import update_user_profile


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=Envelope[dict[str, Any]])
def get_me(current_user: User = Depends(get_current_user)) -> Envelope[dict[str, Any]]:
    data = {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "meta": getattr(current_user, "meta", {}) or {},
    }
    return Envelope(code=0, msg="ok", data=data)


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    meta: dict | None = None


@router.patch("/me", response_model=Envelope[dict[str, Any]])
def patch_me(
    req: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[dict[str, Any]]:
    try:
        user = update_user_profile(
            db,
            user_id=current_user.id,
            display_name=req.display_name,
            email=req.email,
            meta=req.meta,
        )
    except HTTPException:
        raise
    data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "meta": getattr(user, "meta", {}) or {},
    }
    return Envelope(code=0, msg="ok", data=data)

