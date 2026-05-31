from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PASETO_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("REDIS_PASSWORD", "test")
    monkeypatch.setenv("MINIO_ROOT_USER", "test")
    monkeypatch.setenv("MINIO_ROOT_PASSWORD", "test")
    from src.core.config import get_settings
    get_settings.cache_clear()


@pytest.fixture()
def enc():
    from src.infrastructure.crypto.envelope_encryption import EnvelopeEncryptionService
    return EnvelopeEncryptionService()


class TestEnvelopeEncryption:
    def test_round_trip(self, enc) -> None:
        plaintext = b"Sensitive legal document content \xd1\x82\xd0\xb5\xd1\x81\xd1\x82"
        dek, enc_key_id = enc.generate_dek()
        ciphertext = enc.encrypt_bytes(plaintext, dek)
        assert ciphertext != plaintext
        recovered_dek = enc.unwrap_dek(enc_key_id)
        recovered = enc.decrypt_bytes(ciphertext, recovered_dek)
        assert recovered == plaintext

    def test_different_dek_each_call(self, enc) -> None:
        _, key1 = enc.generate_dek()
        _, key2 = enc.generate_dek()
        assert key1 != key2

    def test_ciphertext_differs_each_call(self, enc) -> None:
        data = b"same plaintext"
        dek, _ = enc.generate_dek()
        ct1 = enc.encrypt_bytes(data, dek)
        ct2 = enc.encrypt_bytes(data, dek)
        assert ct1 != ct2

    def test_tampered_ciphertext_fails(self, enc) -> None:
        data = b"original"
        dek, _ = enc.generate_dek()
        ciphertext = enc.encrypt_bytes(data, dek)
        tampered = ciphertext[:-4] + b"\x00\x00\x00\x00"
        with pytest.raises(Exception):
            enc.decrypt_bytes(tampered, dek)

    def test_empty_bytes(self, enc) -> None:
        data = b""
        dek, _ = enc.generate_dek()
        ct = enc.encrypt_bytes(data, dek)
        recovered = enc.decrypt_bytes(ct, dek)
        assert recovered == b""

    def test_large_payload(self, enc) -> None:
        data = b"A" * 10_000_000
        dek, _ = enc.generate_dek()
        ct = enc.encrypt_bytes(data, dek)
        assert enc.decrypt_bytes(ct, dek) == data

    def test_unwrap_invalid_token_raises(self, enc) -> None:
        with pytest.raises(ValueError, match="Failed to unwrap DEK"):
            enc.unwrap_dek("not-a-valid-encrypted-dek-token")
