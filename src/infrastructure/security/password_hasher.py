from __future__ import annotations

import bcrypt


class PasswordHasher:

    _ROUNDS = 12

    @staticmethod
    def hash(plain: str) -> str:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(PasswordHasher._ROUNDS)).decode()

    @staticmethod
    def verify(plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
