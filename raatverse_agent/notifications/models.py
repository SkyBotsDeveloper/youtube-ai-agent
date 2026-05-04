from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class NotificationMessage(BaseModel):
    event: str
    title: str
    body: str
    data: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationResult(BaseModel):
    provider: str
    sent: bool
    message: str
    status_code: int | None = None
