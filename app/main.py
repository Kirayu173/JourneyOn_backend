from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

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
from app.api.routes.user_tags import router as user_tags_router
from app.api.routes.system import router as system_router
from app.db.session import init_db


# Define lifespan to replace deprecated on_event startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception:
        logging.getLogger(__name__).warning("DB init skipped (error)", exc_info=True)
    yield

setup_logging(level=settings.LOG_LEVEL)

app = FastAPI(
    title="JourneyOn Backend",
    version="0.1.0",
    description="FastAPI skeleton for JourneyOn, aligned with design docs",
    lifespan=lifespan,
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Request ID middleware for tracing
from app.middleware.request_id import RequestIdMiddleware
app.add_middleware(RequestIdMiddleware)

# Routers
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(trips_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(itinerary_router, prefix="/api")
app.include_router(kb_router, prefix="/api")
app.include_router(kb_vector_router, prefix="/api")
app.include_router(user_tags_router, prefix="/api")
app.include_router(system_router, prefix="/api")


# Removed deprecated on_event; lifespan handles startup

@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"message": "JourneyOn backend is running"}
