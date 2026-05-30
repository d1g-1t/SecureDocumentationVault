from __future__ import annotations

from fastapi import APIRouter, Response, status
from fastapi.responses import ORJSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.application.dto import HealthResponse
from src.core.config import get_settings
from src.presentation.deps import get_redis, get_session_factory

router = APIRouter(prefix="/health", tags=["health"])
_VERSION = "0.1.0"


@router.get(
    "/live",
    response_model=HealthResponse,
    summary="Liveness probe — is the process alive?",
)
async def liveness() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=get_settings().otel_service_name,
        version=_VERSION,
        checks={},
    )


@router.get(
    "/ready",
    summary="Readiness probe — are all dependencies healthy?",
)
async def readiness() -> ORJSONResponse:
    checks: dict[str, str] = {}
    healthy = True

    try:
        sf = get_session_factory()
        async with sf.session() as session:
            await session.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"
        healthy = False

    try:
        redis = get_redis()
        if await redis.ping():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "ping_failed"
            healthy = False
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False

    http_status = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return ORJSONResponse(
        status_code=http_status,
        content={
            "status": "ok" if healthy else "degraded",
            "service": get_settings().otel_service_name,
            "version": _VERSION,
            "checks": checks,
        },
    )


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    include_in_schema=False,
)
async def metrics() -> Response:
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
