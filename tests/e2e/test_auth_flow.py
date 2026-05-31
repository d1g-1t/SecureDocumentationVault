from __future__ import annotations

import pytest

pytestmark = pytest.mark.requires_db


@pytest.mark.asyncio
async def test_health_live(client):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_login_with_invalid_credentials(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_without_token_returns_401(client):
    import io

    resp = await client.post(
        "/api/v1/documents/",
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"title": "Test"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_request_id_header_present(client):
    resp = await client.get("/api/v1/health/live")
    assert "x-request-id" in resp.headers


@pytest.mark.asyncio
async def test_security_headers_present(client):
    resp = await client.get("/api/v1/health/live")
    headers = resp.headers
    assert "x-content-type-options" in headers
    assert "x-frame-options" in headers
    assert "content-security-policy" in headers
    assert "strict-transport-security" in headers
