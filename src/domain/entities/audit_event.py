from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from src.domain.value_objects import EventType


@dataclass
class AuditEvent:

    id: UUID
    tenant_id: UUID
    actor_user_id: UUID | None
    resource_type: str
    resource_id: UUID
    event_type: EventType
    ip_address: str | None
    user_agent: str | None
    trace_id: str | None
    payload: dict[str, object]
    prev_event_hash: str | None
    event_hash: str
    created_at: datetime
