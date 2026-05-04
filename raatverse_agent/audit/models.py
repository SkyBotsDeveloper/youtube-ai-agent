from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AuditLog(BaseModel):
    id: int | None = None
    actor: str = "system"
    action: str
    entity_type: str
    entity_id: int | None = None
    before_status: str | None = None
    after_status: str | None = None
    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogCreate(BaseModel):
    actor: str = "system"
    action: str
    entity_type: str
    entity_id: int | None = None
    before_status: str | None = None
    after_status: str | None = None
    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict = Field(default_factory=dict)


class ApprovalEvent(BaseModel):
    id: int | None = None
    entity_type: str
    entity_id: int
    action: str
    comment: str | None = None
    actor: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
