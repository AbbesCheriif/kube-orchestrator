"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import structlog
from structlog.types import BoundLogger


def configure_logging(level: str = "INFO", format: str = "json") -> None:
    """Configure structlog processors, renderer, and stdlib root logger."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=log_level)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    renderer: Any
    if format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> BoundLogger:
    """Return a structlog BoundLogger bound to *name*."""
    return structlog.get_logger(name)


class RequestTracer:
    """Generates and binds a unique trace ID for per-request log correlation."""

    def __init__(self) -> None:
        self.trace_id: str = str(uuid.uuid4())

    def bind_trace(self, logger: BoundLogger) -> BoundLogger:
        """Return a new logger with *trace_id* bound."""
        return logger.bind(trace_id=self.trace_id)
