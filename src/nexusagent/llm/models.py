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
    CANCELLED = "cancelled"


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
    # P5: Sub-agent improvements
    # Per-agent model/provider override. If None, inherits from settings.
    # provider must match a key recognised by llm.py (e.g. "gemini", "openrouter").
    model: str | None = None
    provider: str | None = None
    max_depth: int = Field(default=3, ge=1, le=10)  # Max sub-agent nesting depth
    summary_only: bool = False  # If True, return only a summary (not full output)


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


# ── Image Input Models ─────────────────────────────────────────────────────


class ImageAttachment(BaseModel):
    """Represents an image attached to a user message.

    Supports both local file paths and remote URLs.
    The image is base64-encoded before being sent to the LLM.
    """

    path: str  # Local file path or URL
    mime_type: str = "image/png"  # MIME type (image/png, image/jpeg, image/webp, image/gif)
    base64_data: str = ""  # Base64-encoded image data (populated by encode_image)

    def encode(self) -> str:
        """Encode the image to base64.

        For local files: reads the file and encodes it.
        For URLs: returns the URL directly (LLMs that support URLs can fetch them).

        Returns:
            Base64 data URI string or URL.
        """
        import base64
        from pathlib import Path

        # If it's a URL, return as-is
        if self.path.startswith(("http://", "https://")):
            return self.path

        # Local file — read and encode
        file_path = Path(self.path).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        # Auto-detect MIME type from extension
        ext = file_path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }
        self.mime_type = mime_map.get(ext, "image/png")

        with open(file_path, "rb") as f:
            self.base64_data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{self.mime_type};base64,{self.base64_data}"


def encode_image_to_content(path: str) -> dict:
    """Encode an image to a LangChain-compatible content block.

    Args:
        path: Local file path or URL to the image.

    Returns:
        A dict with 'type': 'image_url' and the image data,
        compatible with LangChain's multimodal message format.
    """
    attachment = ImageAttachment(path=path)
    encoded = attachment.encode()

    return {"type": "image_url", "image_url": {"url": encoded}}
