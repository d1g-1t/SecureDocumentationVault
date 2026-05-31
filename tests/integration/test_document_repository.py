from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(scope="module")
async def session_factory():
    from src.infrastructure.database.session import AsyncSessionFactory

    yield AsyncSessionFactory


@pytest.mark.asyncio
async def test_save_and_fetch_document(session_factory):
    from src.infrastructure.database.models import (
        TenantModel,
        ApiUserModel,
        DocumentModel,
    )
    from sqlalchemy import select

    tenant_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()

    async with session_factory.session() as session:
        tenant = TenantModel(id=tenant_id, name="Integration Test Tenant", slug="inttest")
        session.add(tenant)

        user = ApiUserModel(
            id=user_id,
            tenant_id=tenant_id,
            email=f"test-{user_id}@example.com",
            hashed_password="$2b$12$xxxxxxxx",
            role="ARCHIVIST",
            is_active=True,
        )
        session.add(user)

        doc = DocumentModel(
            id=doc_id,
            tenant_id=tenant_id,
            title="Integration Test Document",
            document_type="CONTRACT",
            status="ACTIVE",
            owner_user_id=user_id,
        )
        session.add(doc)
        await session.commit()

    async with session_factory.session() as session:
        fetched = await session.scalar(
            select(DocumentModel).where(DocumentModel.id == doc_id)
        )
        assert fetched is not None
        assert fetched.title == "Integration Test Document"
        assert fetched.status == "ACTIVE"

    async with session_factory.session() as session:
        d = await session.get(DocumentModel, doc_id)
        if d:
            await session.delete(d)
        u = await session.get(ApiUserModel, user_id)
        if u:
            await session.delete(u)
        t = await session.get(TenantModel, tenant_id)
        if t:
            await session.delete(t)
        await session.commit()
