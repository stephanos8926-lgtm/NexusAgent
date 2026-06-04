# src/nexusagent/models.py
from typing import Optional, Any, Dict
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskSchema(BaseModel):
    id: str
    description: str
    priority: int = Field(default=1, ge=1, le=5)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ResultSchema(BaseModel):
    task_id: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    duration: Optional[float] = None # In seconds
