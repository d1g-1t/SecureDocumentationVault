from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pyseto
from pyseto import Key, Token

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class PasetoService:

    def __init__(self) -> None:
        settings = get_settings()
        raw_key = settings.paseto_secret_key.encode()
        if len(raw_key) < 32:
            raise RuntimeError("PASETO_SECRET_KEY must be at least 32 bytes")
        self._key: Key = Key.new(version=4, purpose="local", key=raw_key[:32])

    def _sign(self, payload: dict[str, Any], ttl: timedelta) -> str:
        now = datetime.now(UTC)
        payload = {
            **payload,
            "iat": now.isoformat(),
            "exp": (now + ttl).isoformat(),
            "jti": secrets.token_urlsafe(16),
        }
        token: bytes = pyseto.encode(self._key, payload=json.dumps(payload))
        return token.decode()

    def create_access_token(self, user_id: UUID, tenant_id: UUID, role: str) -> str:
        settings = get_settings()
        return self._sign(
            payload={
                "sub": str(user_id),
                "tenant_id": str(tenant_id),
                "role": role,
                "type": "access",
            },
            ttl=timedelta(minutes=settings.access_token_ttl_minutes),
        )

    def create_refresh_token(self, user_id: UUID, tenant_id: UUID) -> str:
        settings = get_settings()
        return self._sign(
            payload={
                "sub": str(user_id),
                "tenant_id": str(tenant_id),
                "type": "refresh",
            },
            ttl=timedelta(days=settings.refresh_token_ttl_days),
        )

    def decode_token(self, token_str: str) -> dict[str, Any]:
        try:
            decoded: Token = pyseto.decode(self._key, token_str.encode(), deserializer=json)
            payload: dict[str, Any] = decoded.payload
            exp = datetime.fromisoformat(payload["exp"])
            if datetime.now(UTC) > exp:
                raise ValueError("Token has expired")
            return payload
        except Exception as exc:
            logger.warning("token_decode_failed", error=str(exc))
            raise ValueError("Invalid or expired token") from exc

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
