"""Core package — client, config, context, middleware."""

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.config import KubeConfig
from kube_orchestrator.core.context import (
    ExecutionContext,
    use_context,
    use_dry_run,
    use_namespace,
)
from kube_orchestrator.core.middleware import (
    RateLimitHandler,
    RetryConfig,
    TimeoutManager,
    with_retry,
)

__all__ = [
    "ExecutionContext",
    "KubeClient",
    "KubeConfig",
    "RateLimitHandler",
    "RetryConfig",
    "TimeoutManager",
    "use_context",
    "use_dry_run",
    "use_namespace",
    "with_retry",
]
