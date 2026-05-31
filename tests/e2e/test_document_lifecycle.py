from __future__ import annotations

import pytest

pytestmark = pytest.mark.requires_db


@pytest.mark.asyncio
async def test_document_list_requires_auth(client):
    resp = await client.get("/api/v1/documents/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_document_not_found_returns_404(client):
    import uuid

    resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert resp.status_code in (401, 404)
    if resp.status_code == 404:
        body = resp.json()
        assert "type" in body
        assert "title" in body
        assert "status" in body


@pytest.mark.asyncio
async def test_share_link_with_unknown_token(client):
    resp = await client.post("/api/v1/shares/public/not-a-real-token/download")
    assert resp.status_code == 404
