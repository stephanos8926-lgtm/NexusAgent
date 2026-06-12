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

    def __init__(self, db_manager: "DatabaseManager") -> None:
        self.db_manager = db_manager

    async def create_session(
        self, working_dir: str = ".", memory_id: str | None = None
    ) -> str:
        session_id = str(uuid.uuid4())
        async with self.db_manager.get_session() as session:
            sess = SessionModel(
                id=session_id,
                working_dir=working_dir,
                memory_id=memory_id,
            )
            session.add(sess)
        return session_id

    async def get_session(self, session_id: str) -> dict | None:
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
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }

    async def update_status(self, session_id: str, status: str) -> None:
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

    async def list_sessions(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List sessions with optional status filter and pagination."""
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
        """Fork a session: copy messages to a new session ID. Returns new session ID or None."""
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
