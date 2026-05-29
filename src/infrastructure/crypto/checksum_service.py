from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator


class ChecksumService:

    @staticmethod
    def compute(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    async def compute_stream(stream: AsyncIterator[bytes]) -> tuple[bytes, str]:
        h = hashlib.sha256()
        chunks: list[bytes] = []
        async for chunk in stream:
            h.update(chunk)
            chunks.append(chunk)
        return b"".join(chunks), h.hexdigest()

    @staticmethod
    def verify(data: bytes, expected_checksum: str) -> bool:
        actual = hashlib.sha256(data).hexdigest()
        return actual == expected_checksum
