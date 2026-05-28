from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from src.application.dto import CurrentUserDTO, LoginRequest, TokenResponse
from src.core.logging import get_logger
from src.core.security import PasetoService
from src.infrastructure.database.models import ApiUserModel
from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.security.password_hasher import PasswordHasher

logger = get_logger(__name__)


class AuthService:

    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        paseto: PasetoService,
    ) -> None:
        self._sf = session_factory
        self._paseto = paseto
        self._hasher = PasswordHasher()

    async def login(self, request: LoginRequest) -> TokenResponse:
        async with self._sf.session() as session:
            result = await session.execute(
                select(ApiUserModel).where(ApiUserModel.email == request.email)
            )
            user = result.scalars().first()

        if not user or not self._hasher.verify(request.password, user.hashed_password):
            logger.warning("login_failed", email=request.email)
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is disabled")

        access = self._paseto.create_access_token(user.id, user.tenant_id, user.role)
        refresh = self._paseto.create_refresh_token(user.id, user.tenant_id)

        logger.info("user_login", user_id=str(user.id), tenant_id=str(user.tenant_id))

        from src.core.config import get_settings
        cfg = get_settings()
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
            expires_in=cfg.access_token_ttl_minutes * 60,
        )

    async def get_current_user(self, token: str) -> CurrentUserDTO:
        payload = self._paseto.decode_token(token)

        if payload.get("type") != "access":
            raise ValueError("Not an access token")

        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])

        async with self._sf.session() as session:
            result = await session.execute(
                select(ApiUserModel).where(
                    ApiUserModel.id == user_id,
                    ApiUserModel.is_active == True,
                )
            )
            user = result.scalars().first()

        if not user:
            raise ValueError("User not found or deactivated")

        return CurrentUserDTO(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            role=user.role,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        payload = self._paseto.decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])

        async with self._sf.session() as session:
            result = await session.execute(
                select(ApiUserModel).where(
                    ApiUserModel.id == user_id,
                    ApiUserModel.is_active == True,
                )
            )
            user = result.scalars().first()

        if not user:
            raise ValueError("User not found or deactivated")

        access = self._paseto.create_access_token(user.id, user.tenant_id, user.role)
        refresh = self._paseto.create_refresh_token(user.id, user.tenant_id)

        logger.info("token_refreshed", user_id=str(user.id))

        from src.core.config import get_settings
        cfg = get_settings()
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
            expires_in=cfg.access_token_ttl_minutes * 60,
        )
