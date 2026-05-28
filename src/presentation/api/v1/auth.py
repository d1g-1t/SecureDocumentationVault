"""Auth router — login, token refresh, current user."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

from src.application.dto import CurrentUserDTO, LoginRequest, TokenResponse
from src.application.use_cases.auth_service import AuthService
from src.presentation.deps import CurrentUser, get_paseto, get_session_factory

router = APIRouter(prefix="/auth", tags=["auth"])


class RefreshRequest(BaseModel):
    refresh_token: str


def _get_auth_service(
    sf: Annotated[object, Depends(get_session_factory)],
    paseto: Annotated[object, Depends(get_paseto)],
) -> AuthService:
    return AuthService(sf, paseto)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive PASETO tokens",
)
async def login(
    request: LoginRequest,
    auth: Annotated[AuthService, Depends(_get_auth_service)],
) -> TokenResponse:
    """Exchange credentials for PASETO v4 access + refresh tokens."""
    try:
        return await auth.login(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token using a refresh token",
)
async def refresh_token(
    request: RefreshRequest,
    auth: Annotated[AuthService, Depends(_get_auth_service)],
) -> TokenResponse:
    """Exchange a valid refresh token for new access + refresh tokens."""
    try:
        return await auth.refresh_tokens(request.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get(
    "/me",
    response_model=CurrentUserDTO,
    summary="Get current authenticated user",
)
async def get_me(current_user: CurrentUser) -> CurrentUserDTO:
    return current_user
