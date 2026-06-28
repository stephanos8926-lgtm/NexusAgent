"""Database manager — async engine + session factory.

Resolves the DB URL from ``settings.server.db_path`` at creation time.
The singleton instance is created at the package level in ``__init__.py``
so that all consumers (``TaskRepository``, ``SessionRepository``) share
one engine.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nexusagent.infrastructure.config import settings

from .base import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async SQLAlchemy engine + session factory."""

    def __init__(self, db_url: str | None = None) -> None:
        """Initialize the async engine and session factory.

        Auto-prefixes plain paths with ``sqlite+aiosqlite://`` and ensures
        the parent directory exists for file-based SQLite databases.

        Args:
            db_url: Database URL. If None, resolved from
                ``settings.server.db_path``.
        """
        url = db_url or settings.server.db_path
        if not url.startswith("sqlite+aiosqlite://"):
            if url.startswith("sqlite://"):
                url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
            elif not url.startswith("://"):
                url = f"sqlite+aiosqlite:///{url}"
        self.db_url = url
        # Ensure parent directory exists for file-based SQLite DBs
        if "sqlite" in url:
            from pathlib import Path as _Path

            db_file = url.split("///")[-1] if "///" in url else ""
            if db_file and not db_file.startswith(":memory:"):
                _Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(self.db_url, echo=False, future=True)
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    def reinit(self, db_url: str | None = None) -> None:
        """Reinitialize with a new DB URL (used by tests).

        FIX: Previously only updated ``self.db_url`` without recreating the
        engine/session, so tests silently used the old engine. Now both the
        engine and session factory are recreated.
        """
        url = db_url or settings.server.db_path
        if not url.startswith("sqlite+aiosqlite://"):
            if url.startswith("sqlite://"):
                url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
            elif not url.startswith("://"):
                url = f"sqlite+aiosqlite:///{url}"
        self.db_url = url
        if "sqlite" in url:
            from pathlib import Path as _Path

            db_file = url.split("///")[-1] if "///" in url else ""
            if db_file and not db_file.startswith(":memory:"):
                _Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        # FIX: Recreate engine and session factory with the new URL
        self.engine = create_async_engine(self.db_url, echo=False, future=True)
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self) -> None:
        """Create all ORM tables (idempotent — safe to call at startup)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await self._run_migrations(conn)
        logger.info(f"Database initialized at {self.db_url}")

    async def _run_migrations(self, conn) -> None:
        """Run incremental schema migrations.

        Each migration is a named SQL block that runs only once,
        tracked in a ``_migrations`` table.
        """
        # Ensure the migrations tracking table exists
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS _migrations ("
                "  name TEXT PRIMARY KEY,"
                "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
                ")"
            )
        )

        # Migration: add memory_dir column to sessions table
        row = await conn.execute(text("SELECT name FROM _migrations WHERE name = 'add_memory_dir'"))
        if row.scalar_one_or_none() is None:
            # Check if the column already exists (in case of pre-existing DB)
            pragma = await conn.execute(text("PRAGMA table_info(sessions)"))
            columns = [r[1] for r in pragma.fetchall()]
            if "memory_dir" not in columns:
                await conn.execute(text("ALTER TABLE sessions ADD COLUMN memory_dir TEXT"))
            await conn.execute(text("INSERT INTO _migrations (name) VALUES ('add_memory_dir')"))

        # Migration: add index on working_dir for find_sessions_by_working_dir
        row = await conn.execute(
            text("SELECT name FROM _migrations WHERE name = 'add_working_dir_index'")
        )
        if row.scalar_one_or_none() is None:
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_sessions_working_dir ON sessions (working_dir)")
            )
            await conn.execute(
                text("INSERT INTO _migrations (name) VALUES ('add_working_dir_index')")
            )

    async def close(self) -> None:
        """Dispose the engine (call on shutdown)."""
        await self.engine.dispose()

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        """Yield a transactional session, committing on success or rolling back on error.

        The session is always closed when the context exits.
        """
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def execute(self, query: str, params: dict | None = None) -> object:
        """Execute a raw SQL query and return the result.

        Args:
            query: The SQL statement to execute.
            params: Optional dict of named parameters.

        Returns:
            The SQLAlchemy ``Result`` object.
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            return result
