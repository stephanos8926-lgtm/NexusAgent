# src/nexusagent/models.py
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskSchema(BaseModel):
    id: str
    description: str
    priority: int = Field(default=1, ge=1, le=5)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryScope(StrEnum):
    SHARED = "shared"
    ISOLATED = "isolated"
    SCOPED = "scoped"


class TaskContract(BaseModel):
    task_id: str
    title: str
    working_dir: str = Field(default=".")
    allowed_tools: list[str] | None = None
    denied_tools: list[str] = Field(default_factory=list)
    max_turns: int = Field(default=20, ge=1, le=100)
    max_wall_time: float = Field(default=1800.0, ge=10.0)
    max_tokens: int | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    memory_scope: MemoryScope = MemoryScope.ISOLATED
    parent_memory_id: str | None = None
    human_in_the_loop: bool = False
    on_failure: str = "escalate"
    expected_outputs: list[str] = Field(default_factory=list)
    description: str = ""
    priority: int = Field(default=1, ge=1, le=5)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResultSchema(BaseModel):
    task_id: str
    success: bool
    data: Any | None = None
    error: str | None = None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration: float | None = None  # In seconds


# --- Agent Event Types (streaming protocol) ---


class AgentEvent(BaseModel):
    type: str


class ThinkingEvent(AgentEvent):
    type: str = "thinking"
    content: str = ""


class ToolCallEvent(AgentEvent):
    type: str = "tool_call"
    tool: str
    args: dict[str, Any]
    call_id: str = ""


class ToolResultEvent(AgentEvent):
    type: str = "tool_result"
    call_id: str
    output: str = ""
    success: bool = True


class ApprovalRequestEvent(AgentEvent):
    type: str = "approval_request"
    tool: str
    args: dict[str, Any]
    call_id: str = ""
    reason: str = ""


class ResponseEvent(AgentEvent):
    type: str = "response"
    content: str = ""


class ErrorEvent(AgentEvent):
    type: str = "error"
    message: str = ""
