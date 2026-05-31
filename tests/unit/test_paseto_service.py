from __future__ import annotations

import time
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PASETO_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("REDIS_PASSWORD", "test")
    monkeypatch.setenv("MINIO_ROOT_USER", "test")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "test")
    from src.core.config import get_settings
    get_settings.cache_clear()


@pytest.fixture()
def paseto():
    from src.core.security import PasetoService
    return PasetoService()


class TestPasetoService:
    def test_create_and_decode_token(self, paseto) -> None:
        user_id = uuid4()
        tenant_id = uuid4()
        token = paseto.create_access_token(
            user_id=user_id, tenant_id=tenant_id, role="admin"
        )
        assert isinstance(token, str)
        assert token.startswith("v4.local.")

        claims = paseto.decode_token(token)
        assert claims["sub"] == str(user_id)
        assert claims["tenant_id"] == str(tenant_id)
        assert claims["role"] == "admin"

    def test_tampered_token_raises(self, paseto) -> None:
        token = paseto.create_access_token(
            user_id=uuid4(), tenant_id=uuid4(), role="viewer"
        )
        tampered = token[:-4] + "XXXX"
        with pytest.raises(ValueError, match="Invalid or expired token"):
            paseto.decode_token(tampered)

    def test_token_has_type_claim(self, paseto) -> None:
        token = paseto.create_access_token(
            user_id=uuid4(), tenant_id=uuid4(), role="viewer"
        )
        claims = paseto.decode_token(token)
        assert claims["type"] == "access"

    def test_refresh_token_has_correct_type(self, paseto) -> None:
        token = paseto.create_refresh_token(
            user_id=uuid4(), tenant_id=uuid4()
        )
        claims = paseto.decode_token(token)
        assert claims["type"] == "refresh"

    def test_hash_token_is_deterministic(self, paseto) -> None:
        from src.core.security import PasetoService as PS
        token = paseto.create_access_token(
            user_id=uuid4(), tenant_id=uuid4(), role="admin"
        )
        h1 = PS.hash_token(token)
        h2 = PS.hash_token(token)
        assert h1 == h2

    def test_different_tokens_different_hashes(self, paseto) -> None:
        from src.core.security import PasetoService as PS
        uid = uuid4()
        tid = uuid4()
        t1 = paseto.create_access_token(user_id=uid, tenant_id=tid, role="viewer")
        time.sleep(0.01)  # ensure different iat
        t2 = paseto.create_access_token(user_id=uid, tenant_id=tid, role="viewer")
        assert PS.hash_token(t1) != PS.hash_token(t2)
