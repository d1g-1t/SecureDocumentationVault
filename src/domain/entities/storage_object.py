from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.value_objects import StorageClass


@dataclass
class StorageObject:

    id: UUID
    tenant_id: UUID
    object_key: str
    bucket_name: str
    storage_class: StorageClass
    encrypted: bool
    object_size: int
    object_checksum: str
    created_at: datetime
