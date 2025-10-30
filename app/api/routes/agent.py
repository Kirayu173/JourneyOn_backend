from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.agents.streaming import StreamingAgentSession
from app.api.deps import get_current_user
from app.core.security import verify_token
from app.db.models import User
from app.db.session import SessionLocal, get_db
from app.schemas.agent_schemas import AgentEvent
from app.schemas.common import Envelope
from app.services.conversation_service import save_message

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    trip_id: int
    stage: str
    message: str
    client_ctx: Dict[str, Any] | None = None
    cards: bool | None = None


@router.post("/chat", response_model=Envelope[Dict[str, Any]])
async def agent_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Envelope[Dict[str, Any]]:
    """与AI代理进行同步聊天。"""
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

    def _build_cards(stage: str, text: str) -> list[dict[str, Any]]:
        stage_norm = (stage or "").strip().lower()
        if stage_norm == "pre":
            return [
                {
                    "type": "planning",
                    "title": "行程规划草案",
                    "items": [
                        {"kind": "text", "text": text},
                    ],
                }
            ]
        if stage_norm == "on":
            return [
                {
                    "type": "daily_schedule",
                    "title": "当日行程与提醒",
                    "items": [
                        {"kind": "text", "text": text},
                    ],
                }
            ]
        # post or others
        return [
            {
                "type": "summary",
                "title": "旅行回顾",
                "items": [
                    {"kind": "text", "text": text},
                ],
            }
        ]

    cards_enabled = bool(req.cards)
    cards: list[dict[str, Any]] | None = None
    if cards_enabled:
        msg_text = str(reply.get("reply", "")) if isinstance(reply, dict) else ""
        cards = _build_cards(req.stage, msg_text)

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
            **({"cards": cards, "cards_enabled": True} if cards_enabled else {}),
        },
    )


async def _event_source(stream: AsyncGenerator[AgentEvent, None]) -> AsyncGenerator[bytes, None]:
    """将代理事件转换为服务器发送事件格式。"""
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
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """与AI代理进行流式聊天。"""
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


async def _receive_agent_payload(websocket: WebSocket) -> Optional[Dict[str, Any]]:
    """从WebSocket接收代理有效载荷。"""
    try:
        message = await websocket.receive_json()
        if not isinstance(message, dict):
            return None
        return message
    except (TypeError, ValueError, WebSocketDisconnect):
        return None


@router.websocket("/ws/chat")
async def agent_chat_websocket(websocket: WebSocket) -> None:
    """通过WebSocket与AI代理进行实时聊天。"""
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

    user_sub = payload.get("sub")
    try:
        user_id = int(user_sub) if user_sub is not None else None
    except (TypeError, ValueError):
        user_id = None
    if user_id is None:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        await websocket.accept()

        initial = await _receive_agent_payload(websocket)
        if not initial:
            await websocket.close(code=4400)
            return

        trip_id_raw = initial.get("trip_id")
        stage_raw = initial.get("stage")
        message_raw = initial.get("message")
        if not isinstance(trip_id_raw, (int, str)):
            await websocket.close(code=4400)
            return
        try:
            trip_id = int(trip_id_raw)
        except ValueError:
            await websocket.close(code=4400)
            return
        if stage_raw is None or message_raw is None:
            await websocket.close(code=4400)
            return
        stage = str(stage_raw)
        message = str(message_raw)

        client_ctx_raw = initial.get("client_ctx")
        client_ctx = client_ctx_raw if isinstance(client_ctx_raw, dict) else {}

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
            client_ctx=client_ctx,
        ):
            await websocket.send_json(event.model_dump(mode="json"))

        await websocket.close(code=1000)
    finally:
        db.close()
