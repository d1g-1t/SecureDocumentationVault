from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from src.core.config import get_settings


class IntegrityChainService:

    def __init__(self) -> None:
        settings = get_settings()
        self._secret = settings.paseto_secret_key[:32].encode()

    def compute_hash(
        self,
        payload: dict[str, Any],
        prev_hash: str | None,
    ) -> str:
        msg_parts = [
            (prev_hash or "GENESIS").encode(),
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode(),
        ]
        msg = b"||".join(msg_parts)
        return hmac.new(self._secret, msg, hashlib.sha256).hexdigest()

    def verify_chain(
        self,
        events: list[dict[str, Any]],
    ) -> tuple[bool, int | None]:
        for idx, event in enumerate(events):
            expected = self.compute_hash(
                payload=event["payload"],
                prev_hash=event.get("prev_event_hash"),
            )
            if not hmac.compare_digest(expected, event["event_hash"]):
                return False, idx
        return True, None
