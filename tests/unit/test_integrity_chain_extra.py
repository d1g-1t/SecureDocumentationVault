from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PASETO_SECRET_KEY", "z" * 32)
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("REDIS_PASSWORD", "test")
    monkeypatch.setenv("MINIO_ROOT_USER", "test")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "test")
    from src.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture()
def chain():
    from src.infrastructure.crypto.integrity_chain import IntegrityChainService

    return IntegrityChainService()


class TestIntegrityChain:
    def test_genesis_hash_is_deterministic(self, chain) -> None:
        h1 = chain.compute_hash({"a": 1}, None)
        h2 = chain.compute_hash({"a": 1}, None)
        assert h1 == h2

    def test_chain_extends_predictably(self, chain) -> None:
        h0 = chain.compute_hash({"event": "created"}, None)
        h1 = chain.compute_hash({"event": "updated"}, h0)
        h2 = chain.compute_hash({"event": "deleted"}, h1)
        assert len({h0, h1, h2}) == 3

    def test_verify_full_valid_chain(self, chain) -> None:
        events = []
        prev = None
        for i in range(5):
            payload = {"i": i}
            h = chain.compute_hash(payload, prev)
            events.append({"payload": payload, "prev_event_hash": prev, "event_hash": h})
            prev = h
        ok, broken = chain.verify_chain(events)
        assert ok is True
        assert broken is None

    def test_tampered_chain_detected(self, chain) -> None:
        events = []
        prev = None
        for i in range(3):
            payload = {"i": i}
            h = chain.compute_hash(payload, prev)
            events.append({"payload": payload, "prev_event_hash": prev, "event_hash": h})
            prev = h
        events[1]["payload"] = {"i": 999}
        ok, broken = chain.verify_chain(events)
        assert ok is False
        assert broken == 1

    def test_unicode_payload(self, chain) -> None:
        h1 = chain.compute_hash({"title": "Договор №42"}, None)
        h2 = chain.compute_hash({"title": "Договор №42"}, None)
        assert h1 == h2
