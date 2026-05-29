from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import selectinload

from src.domain.entities.document import Document, DocumentVersion
from src.domain.entities.storage_object import StorageObject
from src.domain.repositories import IDocumentRepository
from src.domain.value_objects import DocumentStatus, StorageClass
from src.infrastructure.database.models import (
    DocumentModel,
    DocumentVersionModel,
    StorageObjectModel,
)
from src.infrastructure.database.session import AsyncSessionFactory


class DocumentRepository(IDocumentRepository):
    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._sf = session_factory

    @staticmethod
    def _to_entity(m: DocumentModel) -> Document:
        return Document(
            id=m.id,
            tenant_id=m.tenant_id,
            title=m.title,
            document_type=m.document_type,
            status=DocumentStatus(m.status),
            owner_user_id=m.owner_user_id,
            current_version_id=m.current_version_id,
            retention_policy_id=m.retention_policy_id,
            legal_hold_active=m.legal_hold_active,
            tags=list(m.tags or []),
            metadata=dict(m.metadata_ or {}),
            created_at=m.created_at,
            updated_at=m.updated_at,
            versions=[DocumentRepository._version_to_entity(v) for v in (m.versions or [])],
        )

    @staticmethod
    def _version_to_entity(v: DocumentVersionModel) -> DocumentVersion:
        return DocumentVersion(
            id=v.id,
            document_id=v.document_id,
            version_number=v.version_number,
            file_name=v.file_name,
            mime_type=v.mime_type,
            size_bytes=v.size_bytes,
            sha256_checksum=v.sha256_checksum,
            storage_object_id=v.storage_object_id,
            encryption_key_id=v.encryption_key_id,
            uploaded_by=v.uploaded_by,
            created_at=v.created_at,
        )

    async def get_by_id(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(DocumentModel)
                .where(DocumentModel.id == document_id, DocumentModel.tenant_id == tenant_id)
                .options(selectinload(DocumentModel.versions))
            )
            model = result.scalars().first()
            return self._to_entity(model) if model else None

    async def get_by_id_global(self, document_id: uuid.UUID) -> Document | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(DocumentModel)
                .where(DocumentModel.id == document_id)
                .options(selectinload(DocumentModel.versions))
            )
            model = result.scalars().first()
            return self._to_entity(model) if model else None

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        status: DocumentStatus | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        async with self._sf.session() as session:
            q = (
                select(DocumentModel)
                .where(DocumentModel.tenant_id == tenant_id)
                .options(selectinload(DocumentModel.versions))
                .order_by(DocumentModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if status:
                q = q.where(DocumentModel.status == status.value)
            if tags:
                q = q.where(DocumentModel.tags.contains(tags))
            result = await session.execute(q)
            return [self._to_entity(m) for m in result.scalars().all()]

    async def create(self, document: Document) -> Document:
        async with self._sf.session() as session:
            model = DocumentModel(
                id=document.id,
                tenant_id=document.tenant_id,
                title=document.title,
                document_type=document.document_type,
                status=document.status.value,
                owner_user_id=document.owner_user_id,
                current_version_id=document.current_version_id,
                retention_policy_id=document.retention_policy_id,
                legal_hold_active=document.legal_hold_active,
                tags=document.tags,
                metadata_=document.metadata,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return self._to_entity(model)

    async def update(self, document: Document) -> Document:
        async with self._sf.session() as session:
            await session.execute(
                sa_update(DocumentModel)
                .where(DocumentModel.id == document.id)
                .values(
                    title=document.title,
                    status=document.status.value,
                    current_version_id=document.current_version_id,
                    retention_policy_id=document.retention_policy_id,
                    legal_hold_active=document.legal_hold_active,
                    tags=document.tags,
                    metadata_=document.metadata,
                    updated_at=datetime.now(UTC),
                )
            )
            result = await session.execute(
                select(DocumentModel)
                .where(DocumentModel.id == document.id)
                .options(selectinload(DocumentModel.versions))
            )
            model = result.scalars().one()
            return self._to_entity(model)

    async def list_versions(self, document_id: uuid.UUID) -> list[DocumentVersion]:
        async with self._sf.session() as session:
            result = await session.execute(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.document_id == document_id)
                .order_by(DocumentVersionModel.version_number)
            )
            return [self._version_to_entity(v) for v in result.scalars().all()]

    async def get_version_by_id(self, version_id: uuid.UUID) -> DocumentVersion | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(DocumentVersionModel).where(DocumentVersionModel.id == version_id)
            )
            v = result.scalars().first()
            return self._version_to_entity(v) if v else None

    async def create_version(self, version: DocumentVersion) -> DocumentVersion:
        async with self._sf.session() as session:
            model = DocumentVersionModel(
                id=version.id,
                document_id=version.document_id,
                version_number=version.version_number,
                file_name=version.file_name,
                mime_type=version.mime_type,
                size_bytes=version.size_bytes,
                sha256_checksum=version.sha256_checksum,
                storage_object_id=version.storage_object_id,
                encryption_key_id=version.encryption_key_id,
                uploaded_by=version.uploaded_by,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return self._version_to_entity(model)

    async def create_storage_object(self, obj: StorageObject) -> StorageObject:
        async with self._sf.session() as session:
            model = StorageObjectModel(
                id=obj.id,
                tenant_id=obj.tenant_id,
                object_key=obj.object_key,
                bucket_name=obj.bucket_name,
                storage_class=obj.storage_class.value,
                encrypted=obj.encrypted,
                object_size=obj.object_size,
                object_checksum=obj.object_checksum,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return StorageObject(
                id=model.id,
                tenant_id=model.tenant_id,
                object_key=model.object_key,
                bucket_name=model.bucket_name,
                storage_class=StorageClass(model.storage_class),
                encrypted=model.encrypted,
                object_size=model.object_size,
                object_checksum=model.object_checksum,
                created_at=model.created_at,
            )

    async def link_version_storage(
        self, version_id: uuid.UUID, storage_object_id: uuid.UUID
    ) -> None:
        async with self._sf.session() as session:
            await session.execute(
                sa_update(DocumentVersionModel)
                .where(DocumentVersionModel.id == version_id)
                .values(storage_object_id=storage_object_id)
            )
