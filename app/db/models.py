from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship
import enum


Base = declarative_base()


class TripStageEnum(str, enum.Enum):
    pre = "pre"
    on = "on"
    post = "post"


class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True)
    username: str = Column(String(64), unique=True, nullable=False)
    email: str = Column(String(255), unique=True, index=True, nullable=False)
    password_hash: Optional[str] = Column(Text)
    display_name: Optional[str] = Column(String(128))
    meta: dict = Column(JSON, default={})
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trips = relationship("Trip", back_populates="user")


class Trip(Base):
    __tablename__ = "trips"

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Optional[str] = Column(String(255))
    origin: Optional[str] = Column(String(255))
    origin_lat: Optional[float] = Column(Float)
    origin_lng: Optional[float] = Column(Float)
    destination: Optional[str] = Column(String(255))
    destination_lat: Optional[float] = Column(Float)
    destination_lng: Optional[float] = Column(Float)
    start_date: Optional[date] = Column(Date)
    duration_days: Optional[int] = Column(Integer)
    budget: Optional[float] = Column(Numeric(10, 2))
    currency: str = Column(String(8), default="CNY")
    current_stage: TripStageEnum = Column(Enum(TripStageEnum, name="trip_stage_enum"), default=TripStageEnum.pre)
    status: str = Column(String(32), default="active")
    preferences: Optional[dict] = Column(JSON, nullable=True)
    agent_context: Optional[dict] = Column(JSON, nullable=True)
    meta: dict = Column(JSON, default={})
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="trips")
    stages = relationship("TripStage", back_populates="trip", cascade="all, delete-orphan")
    itinerary_items = relationship("ItineraryItem", back_populates="trip", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="trip", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="trip", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="trip", cascade="all, delete-orphan")


class TripStage(Base):
    __tablename__ = "trip_stages"

    id: int = Column(Integer, primary_key=True)
    trip_id: int = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    stage_name: str = Column(String(8), nullable=False)
    status: str = Column(String(16), default="pending")
    assigned_agent: Optional[str] = Column(String(128))
    confirmed_at: Optional[datetime] = Column(DateTime(timezone=True))
    meta: dict = Column(JSON, default={})
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trip = relationship("Trip", back_populates="stages")

    __table_args__ = (UniqueConstraint("trip_id", "stage_name", name="uq_trip_stage"),)


class ItineraryItem(Base):
    __tablename__ = "itinerary_items"

    id: int = Column(Integer, primary_key=True)
    trip_id: int = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    day: int = Column(Integer, nullable=False)
    start_time: Optional[str] = Column(String(32))
    end_time: Optional[str] = Column(String(32))
    kind: Optional[str] = Column(String(32))
    title: Optional[str] = Column(String(255))
    location: Optional[str] = Column(String(255))
    lat: Optional[float] = Column(Float)
    lng: Optional[float] = Column(Float)
    details: Optional[str] = Column(Text)

    trip = relationship("Trip", back_populates="itinerary_items")


class Task(Base):
    __tablename__ = "tasks"

    id: int = Column(Integer, primary_key=True)
    trip_id: int = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    stage: str = Column(String(8), nullable=False)
    title: str = Column(String(255), nullable=False)
    description: Optional[str] = Column(Text)
    status: str = Column(String(32), default="pending")
    priority: int = Column(Integer, default=1)
    assigned_to: Optional[str] = Column(String(64))
    due_date: Optional[date] = Column(Date)
    meta: dict = Column(JSON, default={})

    trip = relationship("Trip", back_populates="tasks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: int = Column(Integer, primary_key=True)
    trip_id: int = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    stage: str = Column(String(8), nullable=False)
    role: str = Column(String(16), nullable=False)
    message: str = Column(Text, nullable=False)
    message_meta: dict = Column(JSON, default={})
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trip = relationship("Trip", back_populates="conversations")


class KBEntry(Base):
    __tablename__ = "kb_entries"

    id: int = Column(Integer, primary_key=True)
    trip_id: Optional[int] = Column(Integer, ForeignKey("trips.id", ondelete="SET NULL"))
    source: Optional[str] = Column(String(64))
    title: Optional[str] = Column(String(255))
    content: Optional[str] = Column(Text)
    meta: dict = Column("metadata", JSON, default={})
    embedding_id: Optional[str] = Column(String(64))
    # Store embedding as JSON list of floats to keep compatibility across SQLite/Postgres
    embedding: Optional[list] = Column(JSON, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class UserTag(Base):
    __tablename__ = "user_tags"

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tag: str = Column(String(64), nullable=False)
    weight: Optional[float] = Column(Float)
    source_trip_id: Optional[int] = Column(Integer, ForeignKey("trips.id", ondelete="SET NULL"))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: int = Column(Integer, primary_key=True)
    user_id: Optional[int] = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    trip_id: Optional[int] = Column(Integer, ForeignKey("trips.id", ondelete="SET NULL"))
    action: str = Column(String(64), nullable=False)
    detail: Optional[str] = Column(Text)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Report(Base):
    __tablename__ = "reports"

    id: int = Column(Integer, primary_key=True)
    trip_id: int = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    filename: Optional[str] = Column(String(255))
    format: Optional[str] = Column(String(32))
    content_type: Optional[str] = Column(String(128))
    file_size: Optional[int] = Column(BigInteger)
    storage_key: str = Column(String(512), nullable=False)
    meta: dict = Column(JSON, default={})
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trip = relationship("Trip", back_populates="reports")
