from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 300


class RedisClient:

    def __init__(self) -> None:
        cfg = get_settings()
        self._redis: aioredis.Redis = aioredis.from_url(
            cfg.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )

    async def ping(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: int = _CACHE_TTL_SECONDS,
    ) -> None:
        await self._redis.setex(key, ttl, json.dumps(value, default=str))

    async def get_json(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def invalidate_pattern(self, pattern: str) -> int:
        keys = await self._redis.keys(pattern)
        if keys:
            return await self._redis.delete(*keys)
        return 0

    async def blocklist_token(self, jti: str, ttl: int) -> None:
        await self._redis.setex(f"blocklist:{jti}", ttl, "1")

    async def is_token_blocked(self, jti: str) -> bool:
        return bool(await self._redis.exists(f"blocklist:{jti}"))

    async def close(self) -> None:
        await self._redis.aclose()
