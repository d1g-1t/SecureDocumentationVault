from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from src.core.config import get_settings

_MASKED_KEYS = frozenset(
    {
        "password",
        "hashed_password",
        "token",
        "access_token",
        "refresh_token",
        "paseto_secret_key",
        "encryption_key",
        "dek",
        "kek",
        "secret",
    }
)


def _mask_sensitive_fields(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    settings = get_settings()
    if not settings.enable_log_masking:
        return event_dict
    for key in list(event_dict.keys()):
        if key.lower() in _MASKED_KEYS:
            event_dict[key] = "***MASKED***"
    return event_dict


def _add_app_context(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    settings = get_settings()
    event_dict.setdefault("service", settings.otel_service_name)
    event_dict.setdefault("env", settings.app_env)
    return event_dict


def configure_logging() -> None:
    settings = get_settings()

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_app_context,
        _mask_sensitive_fields,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_env in ("dev", "test"):
        renderer: Any = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if settings.app_debug else logging.INFO)

    for noisy in ("uvicorn.access", "sqlalchemy.engine", "celery"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
