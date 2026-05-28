from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.core.config import get_settings
from src.core.logging import configure_logging
from src.core.telemetry import setup_telemetry
from src.presentation.api.v1 import auth, audit, documents, health, legal_holds, retention, shares, signatures
from src.presentation.exception_handlers import register_exception_handlers
from src.presentation.middleware.request_id import RequestIDMiddleware
from src.presentation.middleware.security_headers import SecurityHeadersMiddleware

logger = structlog.get_logger(__name__)

cfg = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger.info("securedocvault_starting", env=cfg.app_env, port=cfg.app_port)

    try:
        from src.presentation.deps import get_storage
        get_storage()
    except Exception as exc:
        logger.warning("minio_init_failed", error=str(exc))

    yield

    logger.info("securedocvault_stopping")
    from src.presentation.deps import get_session_factory
    await get_session_factory().close()


app = FastAPI(
    title="SecureDocVault Enterprise Archive",
    description=(
        "Legal-grade secure document vault for Russian legal entities. "
        "Envelope encryption, KEP/NEP verification, "
        "immutable audit trail with hash chain, WORM retention, legal holds, "
        "and controlled document sharing."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(signatures.router, prefix=API_PREFIX)
app.include_router(shares.router, prefix=API_PREFIX)
app.include_router(retention.router, prefix=API_PREFIX)
app.include_router(legal_holds.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)
app.include_router(health.router, prefix=API_PREFIX)

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    env_var_name="ENABLE_METRICS",
    excluded_handlers=["/api/v1/health/metrics"],
).instrument(app)

setup_telemetry(app)
