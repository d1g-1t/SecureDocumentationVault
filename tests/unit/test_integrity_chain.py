from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PASETO_SECRET_KEY", "k" * 32)
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
    def test_genesis_hash_stable(self, chain) -> None:
        h1 = chain.compute_hash({"a": 1}, "GENESIS")
        h2 = chain.compute_hash({"a": 1}, "GENESIS")
        assert h1 == h2

    def test_different_prev_hash_different_result(self, chain) -> None:
        h1 = chain.compute_hash({"x": 1}, "GENESIS")
        h2 = chain.compute_hash({"x": 1}, "not_genesis")
        assert h1 != h2

    def test_different_payload_different_result(self, chain) -> None:
        h1 = chain.compute_hash({"x": 1}, "GENESIS")
        h2 = chain.compute_hash({"x": 2}, "GENESIS")
        assert h1 != h2

    def test_verify_valid_chain(self, chain) -> None:
        h0 = chain.compute_hash({"i": 0}, "GENESIS")
        h1 = chain.compute_hash({"i": 1}, h0)
        h2 = chain.compute_hash({"i": 2}, h1)

        chain_data = [
            {"payload": {"i": 0}, "prev_event_hash": "GENESIS", "event_hash": h0},
            {"payload": {"i": 1}, "prev_event_hash": h0, "event_hash": h1},
            {"payload": {"i": 2}, "prev_event_hash": h1, "event_hash": h2},
        ]
        is_valid, broken_idx = chain.verify_chain(chain_data)
        assert is_valid is True
        assert broken_idx is None

    def test_tampered_chain_fails(self, chain) -> None:
        h0 = chain.compute_hash({"i": 0}, "GENESIS")
        h1 = chain.compute_hash({"i": 1}, h0)

        chain_data = [
            {"payload": {"i": 0}, "prev_event_hash": "GENESIS", "event_hash": h0},
            {"payload": {"i": 1}, "prev_event_hash": h0, "event_hash": "tampered_hash"},
            {"payload": {"i": 2}, "prev_event_hash": h1, "event_hash": chain.compute_hash({"i": 2}, h1)},
        ]
        is_valid, broken_idx = chain.verify_chain(chain_data)
        assert is_valid is False
        assert broken_idx == 1

    def test_hash_is_hex_string(self, chain) -> None:
        h = chain.compute_hash({"test": True}, "GENESIS")
        assert isinstance(h, str)
        assert all(c in "0123456789abcdef" for c in h)
