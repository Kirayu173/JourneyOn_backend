from __future__ import annotations

from base64 import b64decode
from binascii import Error as BinasciiError
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.common import Envelope
from app.schemas.report_schemas import ReportResponse
from app.services import report_service
from app.storage import StorageError, get_storage

router = APIRouter(prefix="/trips/{trip_id}/reports", tags=["reports"])


class ReportUploadRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    content_type: str | None = None
    data: str = Field(..., description="Base64 encoded file content")
    format: str | None = None


@router.post("", response_model=Envelope[ReportResponse])
def upload_report(
    trip_id: int,
    payload: ReportUploadRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Envelope[ReportResponse]:
    try:
        file_bytes = b64decode(payload.data)
    except (BinasciiError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid_base64") from exc

    storage = get_storage()
    buffer = BytesIO(file_bytes)
    try:
        storage_key = storage.save_file(
            buffer,
            filename=payload.filename,
            directory=f"trips/{trip_id}/reports",
        )
    except StorageError as exc:
        raise HTTPException(status_code=500, detail="storage_error") from exc

    inferred_format = payload.format
    if inferred_format is None and payload.filename:
        suffix = Path(payload.filename).suffix
        if suffix:
            inferred_format = suffix[1:].lower()
    report = report_service.create_report(
        db,
        trip_id=trip_id,
        user_id=current_user.id,
        filename=payload.filename,
        format=inferred_format,
        content_type=payload.content_type,
        file_size=len(file_bytes),
        storage_key=storage_key,
    )
    return Envelope(code=0, msg="ok", data=ReportResponse.model_validate(report))


@router.get("", response_model=Envelope[list[ReportResponse]])
def list_reports(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Envelope[list[ReportResponse]]:
    reports = report_service.list_reports(db, trip_id=trip_id, user_id=current_user.id)
    return Envelope(
        code=0,
        msg="ok",
        data=[ReportResponse.model_validate(r) for r in reports],
    )


@router.get("/{report_id}", response_model=Envelope[ReportResponse])
def get_report(
    trip_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Envelope[ReportResponse]:
    report = report_service.get_report(
        db,
        report_id=report_id,
        user_id=current_user.id,
        trip_id=trip_id,
    )
    return Envelope(code=0, msg="ok", data=ReportResponse.model_validate(report))


@router.get("/{report_id}/download")
def download_report(
    trip_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> FileResponse:
    report = report_service.get_report(
        db,
        report_id=report_id,
        user_id=current_user.id,
        trip_id=trip_id,
    )
    storage = get_storage()
    try:
        path = storage.resolve_path(report.storage_key)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail="file_missing") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="file_missing")
    filename = report.filename or Path(path).name
    media_type = report.content_type or "application/octet-stream"
    return FileResponse(path, filename=filename, media_type=media_type)


@router.delete("/{report_id}", response_model=Envelope[None])
def delete_report(
    trip_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Envelope[None]:
    storage_key = report_service.delete_report(
        db,
        report_id=report_id,
        user_id=current_user.id,
        trip_id=trip_id,
    )
    storage = get_storage()
    storage.delete_file(storage_key)
    return Envelope(code=0, msg="ok", data=None)
