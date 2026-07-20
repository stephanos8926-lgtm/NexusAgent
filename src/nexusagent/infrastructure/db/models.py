"""ORM model definitions for NexusAgent.

All models inherit from ``Base`` (imported from .base).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String

from .base import Base


class TaskModel(Base):
    """ORM model for the ``tasks`` table."""

    __tablename__ = "tasks"
    id = Column(String, primary_key=True)
    description = Column(String, nullable=False)
    priority = Column(Integer, default=1)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    metadata_json = Column(JSON, default=dict)


class ResultModel(Base):
    """ORM model for the ``results`` table."""

    __tablename__ = "results"
    task_id = Column(String, primary_key=True)
    success = Column(Integer, default=0)
    data = Column(String, nullable=True)
    error = Column(String, nullable=True)
    completed_at = Column(DateTime, default=lambda: datetime.now(UTC))
    duration = Column(Float, nullable=True)


class SessionModel(Base):
    """ORM model for the ``sessions`` table."""

    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    working_dir = Column(String, nullable=False, default=".")
    memory_id = Column(String, nullable=True)
    memory_dir = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class MessageModel(Base):
    """ORM model for the ``messages`` table."""

    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    tool_name = Column(String, nullable=True)
    tool_args = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class EventModel(Base):
    """ORM model for the ``events`` table."""

    __tablename__ = "events"
    id = Column(String, primary_key=True)
    timestamp = Column(String, nullable=False)
    source = Column(String, nullable=False)
    type = Column(String, nullable=False)
    payload_json = Column(JSON, default=dict)
