"""Execution DTOs: runs and tasks (docs/contracts.md section 2)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from ramus_api.shared.presentation.schemas import ApiResponse, ErrorSummary

RunPurpose = Literal["work", "summary"]
RunStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]
TaskStatus = Literal["pending", "running", "ready", "failed", "cancelled"]


class Run(ApiResponse):
    id: UUID
    conversation_id: UUID
    task_id: UUID | None
    purpose: RunPurpose
    status: RunStatus
    requested_by: UUID
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: ErrorSummary | None


class Task(ApiResponse):
    id: UUID
    source_conversation_id: UUID
    child_conversation_id: UUID
    title: str
    goal: str
    status: TaskStatus
    requested_by: UUID
    result_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: ErrorSummary | None


class TaskList(ApiResponse):
    items: list[Task]
