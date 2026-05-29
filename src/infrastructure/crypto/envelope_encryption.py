from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class EnvelopeEncryptionService:

    def __init__(self) -> None:
        settings = get_settings()
        raw = settings.paseto_secret_key[:32].encode()
        self._kek = Fernet(base64.urlsafe_b64encode(raw))

    def generate_dek(self) -> tuple[bytes, str]:
        dek = Fernet.generate_key()
        encrypted_dek = self._kek.encrypt(dek)
        return dek, encrypted_dek.decode()

    def unwrap_dek(self, encrypted_dek_token: str) -> bytes:
        try:
            return self._kek.decrypt(encrypted_dek_token.encode())
        except InvalidToken as exc:
            logger.error("dek_unwrap_failed")
            raise ValueError("Failed to unwrap DEK — possible key rotation issue") from exc

    def encrypt_bytes(self, plain: bytes, dek: bytes) -> bytes:
        f = Fernet(dek)
        return f.encrypt(plain)

    def decrypt_bytes(self, cipher: bytes, dek: bytes) -> bytes:
        try:
            f = Fernet(dek)
            return f.decrypt(cipher)
        except InvalidToken as exc:
            raise ValueError("Decryption failed — content may be corrupt or key is wrong") from exc
