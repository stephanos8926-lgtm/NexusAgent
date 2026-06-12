"""SQLAlchemy declarative base — single canonical location for all ORM models."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Canonical declarative base for all NexusAgent ORM models."""
