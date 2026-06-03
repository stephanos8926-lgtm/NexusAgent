# Agent B: You are depending on TaskSchema and ResultSchema for all task-related communication.
from pydantic import BaseModel, Field
from typing import Optional

class TaskSchema(BaseModel):
    id: str
    description: str
    priority: int = 1

class ResultSchema(BaseModel):
    success: bool
    data: Optional[str] = None
    error: Optional[str] = None
