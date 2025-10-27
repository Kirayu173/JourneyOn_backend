from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.errors import register_exception_handlers
from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.agent import router as agent_router
from app.api.routes.trips import router as trips_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.itinerary_items import router as itinerary_router
from app.api.routes.kb_entries import router as kb_router
from app.api.routes.kb_vector import router as kb_vector_router
from app.api.routes.reports import router as reports_router
from app.api.routes.user_tags import router as user_tags_router
from app.api.routes.system import router as system_router
from app.api.routes.audit_logs import router as audit_router
from app.api.routes.memories import router as memories_router
from app.db.session import init_db


# 定义生命周期以替代已弃用的on_event启动
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await init_db()
    except Exception:
        logging.getLogger(__name__).warning("数据库初始化跳过（错误）", exc_info=True)
    yield

setup_logging(level=settings.LOG_LEVEL)

app = FastAPI(
    title="JourneyOn Backend",
    version="0.1.0",
    description="JourneyOn的FastAPI骨架，与设计文档对齐",
    lifespan=lifespan,
)

# 开发环境的CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# 请求ID中间件用于追踪
from app.middleware.request_id import RequestIdMiddleware
app.add_middleware(RequestIdMiddleware)

# 路由器
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(trips_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(itinerary_router, prefix="/api")
app.include_router(kb_router, prefix="/api")
app.include_router(kb_vector_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(user_tags_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(memories_router, prefix="/api")


# 已移除已弃用的on_event；生命周期处理启动

@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"message": "JourneyOn后端正在运行"}
