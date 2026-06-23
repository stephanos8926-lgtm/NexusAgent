"""Session repository — CRUD operations on the ``sessions`` and ``messages`` tables."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select, text, update

from .models import MessageModel, SessionModel

if TYPE_CHECKING:
    from .manager import DatabaseManager


class SessionRepository:
    """CRUD operations on sessions and messages."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the repository with a database manager instance.

        Args:
            db_manager: The ``DatabaseManager`` providing session factories.
        """
        self.db_manager = db_manager

    async def create_session(
        self,
        working_dir: str = ".",
        memory_id: str | None = None,
        memory_dir: str | None = None,
    ) -> str:
        """Create a new session record and return its UUID.

        Args:
            working_dir: The project working directory for the session.
            memory_id: Optional identifier for the hybrid memory store.
            memory_dir: Optional path to the session's memory directory.

        Returns:
            The newly generated session UUID.
        """
        session_id = str(uuid.uuid4())
        async with self.db_manager.get_session() as session:
            sess = SessionModel(
                id=session_id,
                working_dir=working_dir,
                memory_id=memory_id,
                memory_dir=memory_dir,
            )
            session.add(sess)
        return session_id

    async def get_session(self, session_id: str) -> dict | None:
        """Retrieve a session record by its UUID.

        Args:
            session_id: The session UUID to look up.

        Returns:
            A dict of session fields, or None if not found.
        """
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            s = result.scalar_one_or_none()
            if not s:
                return None
            return {
                "id": s.id,
                "working_dir": s.working_dir,
                "memory_id": s.memory_id,
                "memory_dir": s.memory_dir,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }

    async def update_status(self, session_id: str, status: str) -> None:
        """Update the status field of a session.

        Args:
            session_id: The session UUID to update.
            status: The new status string (e.g. ``"active"``, ``"idle"``, ``"closed"``).
        """
        async with self.db_manager.get_session() as session:
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(status=status)
            )
            await session.execute(stmt)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: str | None = None,
        tool_args: dict | None = None,
    ) -> str:
        """Append a message to a session's conversation history.

        Args:
            session_id: The session UUID the message belongs to.
            role: Message role (``"user"``, ``"assistant"``, ``"system"``).
            content: The message text content.
            tool_name: Optional tool name if this is a tool call message.
            tool_args: Optional tool arguments dict.

        Returns:
            The newly generated message UUID.
        """
        msg_id = str(uuid.uuid4())
        async with self.db_manager.get_session() as session:
            msg = MessageModel(
                id=msg_id,
                session_id=session_id,
                role=role,
                content=content,
                tool_name=tool_name,
                tool_args=tool_args,
            )
            session.add(msg)
        return msg_id

    async def get_messages(
        self, session_id: str, limit: int = 100
    ) -> list[dict]:
        """Retrieve messages for a session, ordered oldest-first.

        Args:
            session_id: The session UUID to fetch messages for.
            limit: Maximum number of messages to return.

        Returns:
            A list of message dicts.
        """
        async with self.db_manager.get_session() as session:
            query = (
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at.asc())
                .limit(limit)
            )
            result = await session.execute(query)
            messages = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "session_id": m.session_id,
                    "role": m.role,
                    "content": m.content,
                    "tool_name": m.tool_name,
                    "tool_args": m.tool_args,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ]

    async def find_sessions_by_working_dir(
        self,
        working_dir: str,
        exclude: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find previous sessions for the same workspace, ordered by created_at desc.

        Args:
            working_dir: The working directory to filter by.
            exclude: Optional session UUID to exclude from results.
            limit: Maximum number of sessions to return.

        Returns:
            A list of session dicts matching the working directory.
        """
        limit = max(1, min(limit, 200))
        async with self.db_manager.get_session() as session:
            query = (
                select(SessionModel)
                .where(SessionModel.working_dir == working_dir)
                .order_by(SessionModel.created_at.desc())
                .limit(limit)
            )
            if exclude:
                query = query.where(SessionModel.id != exclude)
            result = await session.execute(query)
            sessions = result.scalars().all()
            return [
                {
                    "id": s.id,
                    "working_dir": s.working_dir,
                    "memory_id": s.memory_id,
                    "memory_dir": s.memory_dir,
                    "status": s.status,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in sessions
            ]

    async def list_sessions(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List sessions with optional status filter and pagination."""
        # Clamp limit to prevent resource exhaustion (max 200 per page)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        async with self.db_manager.get_session() as session:
            query = select(SessionModel).order_by(SessionModel.updated_at.desc())
            if status:
                query = query.where(SessionModel.status == status)
            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            sessions = result.scalars().all()
            return [
                {
                    "id": s.id,
                    "working_dir": s.working_dir,
                    "memory_id": s.memory_id,
                    "memory_dir": s.memory_dir,
                    "status": s.status,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in sessions
            ]

    async def rename_session(self, session_id: str, new_id: str) -> bool:
        """Rename a session. Returns True if renamed, False if not found or new_id taken."""
        async with self.db_manager.get_session() as session:
            existing = await session.execute(
                select(SessionModel).where(SessionModel.id == new_id)
            )
            if existing.scalar_one_or_none():
                return False
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(id=new_id)
            )
            result = await session.execute(stmt)
            return result.rowcount > 0

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages. Returns True if deleted."""
        async with self.db_manager.get_session() as session:
            await session.execute(
                text("DELETE FROM messages WHERE session_id = :sid"),
                {"sid": session_id},
            )
            result = await session.execute(
                text("DELETE FROM sessions WHERE id = :sid"),
                {"sid": session_id},
            )
            return result.rowcount > 0

    async def fork_session(
        self, source_id: str, new_working_dir: str | None = None
    ) -> str | None:
        """Fork a session: copy messages to a new session ID.

        All operations (create new session record, copy messages) happen
        within a single database transaction via ``get_session()``, so
        the fork is atomic — it either fully succeeds or fully rolls back.

        Returns:
            The new session UUID, or ``None`` if the source session was not found.
        """
        async with self.db_manager.get_session() as session:
            src = await session.execute(
                select(SessionModel).where(SessionModel.id == source_id)
            )
            src_sess = src.scalar_one_or_none()
            if not src_sess:
                return None

            new_id = str(uuid.uuid4())
            new_sess = SessionModel(
                id=new_id,
                working_dir=new_working_dir or src_sess.working_dir,
                memory_id=src_sess.memory_id,
                memory_dir=src_sess.memory_dir,
                status="active",
            )
            session.add(new_sess)

            msgs = await session.execute(
                select(MessageModel)
                .where(MessageModel.session_id == source_id)
                .order_by(MessageModel.created_at.asc())
            )
            for msg in msgs.scalars().all():
                new_msg = MessageModel(
                    id=str(uuid.uuid4()),
                    session_id=new_id,
                    role=msg.role,
                    content=msg.content,
                    tool_name=msg.tool_name,
                    tool_args=msg.tool_args,
                )
                session.add(new_msg)

            return new_id
