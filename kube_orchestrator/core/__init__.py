"""Core package — client, config, context, middleware, logging, exceptions, settings."""

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.config import KubeConfig
from kube_orchestrator.core.context import ExecutionContext, use_context, use_dry_run, use_namespace
from kube_orchestrator.core.exceptions import KubeOrchestratorError, parse_api_exception
from kube_orchestrator.core.logging import RequestTracer, configure_logging, get_logger
from kube_orchestrator.core.middleware import RateLimitHandler, RetryConfig, TimeoutManager, with_retry
from kube_orchestrator.core.settings import Settings, settings

__all__ = [
    "KubeClient",
    "KubeConfig",
    "ExecutionContext",
    "use_namespace",
    "use_context",
    "use_dry_run",
    "RetryConfig",
    "with_retry",
    "TimeoutManager",
    "RateLimitHandler",
    "KubeOrchestratorError",
    "parse_api_exception",
    "configure_logging",
    "get_logger",
    "RequestTracer",
    "Settings",
    "settings",
]
