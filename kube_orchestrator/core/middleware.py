"""Retry middleware, timeout manager, and rate-limit handler for API calls."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from kubernetes.client.exceptions import ApiException


@dataclass
class RetryConfig:
    """Configuration for the retry decorator."""

    max_attempts: int = 3
    wait_fixed: float = 1.0
    wait_exponential_multiplier: float = 1.0
    wait_exponential_max: float = 10.0
    retry_on_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (ApiException,)
    )


def with_retry(func: Callable[..., Any], config: RetryConfig | None = None) -> Callable[..., Any]:
    """Wrap *func* so it is retried according to *config* on transient errors."""
    cfg = config or RetryConfig()

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, cfg.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except cfg.retry_on_exceptions as exc:
                # Do not retry on 4xx client errors (except 429)
                if isinstance(exc, ApiException) and exc.status not in (429, 500, 502, 503, 504):
                    raise
                last_exc = exc
                if attempt == cfg.max_attempts:
                    break
                delay = min(
                    cfg.wait_fixed + cfg.wait_exponential_multiplier * (2 ** (attempt - 1)),
                    cfg.wait_exponential_max,
                )
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]

    return wrapper


class TimeoutManager:
    """Holds default timeout values and provides a context manager to override them."""

    def __init__(
        self,
        default_timeout: int = 30,
        watch_timeout: int = 300,
    ) -> None:
        self.default_timeout = default_timeout
        self.watch_timeout = watch_timeout
        self._override: int | None = None

    @contextmanager
    def apply_timeout(self, seconds: int) -> Iterator[None]:
        """Temporarily set the active timeout to *seconds* within the block."""
        previous = self._override
        self._override = seconds
        try:
            yield
        finally:
            self._override = previous

    @property
    def active_timeout(self) -> int:
        """Return the currently effective timeout (override or default)."""
        return self._override if self._override is not None else self.default_timeout


class RateLimitHandler:
    """Handles HTTP 429 Too Many Requests responses from the API server."""

    def __init__(self, max_retries: int = 5) -> None:
        self.max_retries = max_retries

    def handle_429(self, response: ApiException) -> None:
        """Extract Retry-After header (or fall back to 5 s) and sleep."""
        retry_after = 5
        if response.headers:
            try:
                retry_after = int(response.headers.get("Retry-After", 5))
            except (ValueError, TypeError):
                pass
        time.sleep(retry_after)
