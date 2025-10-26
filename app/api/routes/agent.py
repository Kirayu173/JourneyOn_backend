from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.agents.streaming import StreamingAgentSession
from app.api.deps import get_current_user
from app.core.security import verify_token
from app.db.session import SessionLocal, get_db
from app.schemas.agent_schemas import AgentEvent
from app.schemas.common import Envelope
from app.services.conversation_service import save_message

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    trip_id: int
    stage: str
    message: str
    client_ctx: dict | None = None


@router.post("/chat", response_model=Envelope[dict[str, Any]])
async def agent_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Envelope[dict[str, Any]]:
    conv = save_message(
        db,
        trip_id=req.trip_id,
        user_id=current_user.id,
        stage=req.stage,
        role="user",
        message=req.message,
        message_meta={
            "client_ctx": req.client_ctx or {},
            "endpoint_version": "v2-sync",
        },
    )

    orchestrator = Orchestrator(db)
    reply = await orchestrator.chat(
        trip_id=req.trip_id,
        stage=req.stage,
        message=req.message,
        user_id=current_user.id,
        client_ctx=req.client_ctx or {},
    )

    return Envelope(
        code=0,
        msg="ok",
        data={
            "conversation": {
                "id": conv.id,
                "role": conv.role,
                "stage": conv.stage,
                "created_at": conv.created_at.isoformat(),
                "message_meta": conv.message_meta,
            },
            "agent": reply,
        },
    )


async def _event_source(stream: AsyncGenerator[AgentEvent, None]) -> AsyncGenerator[bytes, None]:
    async for event in stream:
        payload = event.model_dump(mode="json")
        chunk = (
            f"event: {event.event.value}\n"
            f"id: {event.sequence}\n"
            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        )
        yield chunk.encode("utf-8")


@router.post("/chat/stream")
async def agent_chat_stream(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> StreamingResponse:
    save_message(
        db,
        trip_id=req.trip_id,
        user_id=current_user.id,
        stage=req.stage,
        role="user",
        message=req.message,
        message_meta={
            "client_ctx": req.client_ctx or {},
            "endpoint_version": "v2-stream",
        },
    )

    session = StreamingAgentSession(db)
    stream = session.run(
        trip_id=req.trip_id,
        stage=req.stage,
        message_text=req.message,
        user_id=current_user.id,
        client_ctx=req.client_ctx or {},
    )
    return StreamingResponse(_event_source(stream), media_type="text/event-stream")


async def _receive_agent_payload(websocket: WebSocket) -> Optional[dict[str, Any]]:
    try:
        message = await websocket.receive_json()
        if not isinstance(message, dict):
            return None
        return message
    except (TypeError, ValueError, WebSocketDisconnect):
        return None


@router.websocket("/ws/chat")
async def agent_chat_websocket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token") or websocket.headers.get("Authorization")
    if token and token.lower().startswith("bearer "):
        token = token[7:]
    if not token:
        await websocket.close(code=4401)
        return

    try:
        payload = verify_token(token)
    except JWTError:
        await websocket.close(code=4401)
        return

    user_id = int(payload.get("sub"))

    db = SessionLocal()
    try:
        await websocket.accept()

        initial = await _receive_agent_payload(websocket)
        if not initial:
            await websocket.close(code=4400)
            return

        try:
            trip_id = int(initial.get("trip_id"))
            stage = str(initial.get("stage"))
            message = str(initial.get("message"))
        except (TypeError, ValueError):
            await websocket.close(code=4400)
            return

        client_ctx = initial.get("client_ctx") or {}

        save_message(
            db,
            trip_id=trip_id,
            user_id=user_id,
            stage=stage,
            role="user",
            message=message,
            message_meta={
                "client_ctx": client_ctx,
                "endpoint_version": "v2-websocket",
            },
        )

        session = StreamingAgentSession(db)
        async for event in session.run(
            trip_id=trip_id,
            stage=stage,
            message_text=message,
            user_id=user_id,
        ):
            await websocket.send_json(event.model_dump(mode="json"))

        await websocket.close(code=1000)
    finally:
        db.close()
