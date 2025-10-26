from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.schemas.audit import AuditLogResponse
from app.schemas.common import Envelope
from app.services.audit_service import list_logs

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Envelope[List[AuditLogResponse]])
def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
    trip_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
) -> Envelope[List[AuditLogResponse]]:
    limit = max(1, min(limit, 500))
    logs = list_logs(db, limit=limit, offset=offset, user_id=user_id, trip_id=trip_id)
    return Envelope(
        code=0,
        msg="ok",
        data=[AuditLogResponse.model_validate(log) for log in logs],
    )
