"""Execution context helpers — namespace switcher, context switcher, dry-run mode."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class ExecutionContext:
    """Holds runtime parameters that influence how API calls are made."""

    namespace: str = "default"
    context: str | None = None
    dry_run: bool = False
    timeout: int = 30


# Process-wide active context (module-level singleton)
_active: ExecutionContext = ExecutionContext()


def get_active_context() -> ExecutionContext:
    """Return the currently active ExecutionContext."""
    return _active


@contextmanager
def use_namespace(ns: str) -> Iterator[ExecutionContext]:
    """Temporarily override the active namespace within the block."""
    global _active
    previous = _active.namespace
    _active.namespace = ns
    try:
        yield _active
    finally:
        _active.namespace = previous


@contextmanager
def use_context(ctx: str) -> Iterator[ExecutionContext]:
    """Temporarily switch the Kubernetes context within the block."""
    global _active
    from kube_orchestrator.core.client import (
        KubeClient,  # avoid circular at module level
    )

    previous_ctx = _active.context
    _active.context = ctx

    kube_client = KubeClient.get_instance()
    _ = kube_client._api_client.configuration  # touch to ensure initialised

    # Re-load config for the requested context
    from kube_orchestrator.core.config import KubeConfig

    cfg = KubeConfig()
    cfg.load_from_file()
    cfg.switch_context(ctx)

    # Temporarily swap the api_client configuration
    original_cfg = kube_client._api_client.configuration
    kube_client._api_client.configuration = cfg.configuration
    try:
        yield _active
    finally:
        kube_client._api_client.configuration = original_cfg
        _active.context = previous_ctx


@contextmanager
def use_dry_run() -> Iterator[ExecutionContext]:
    """Enable dry-run mode for all API calls within the block."""
    global _active
    previous = _active.dry_run
    _active.dry_run = True
    try:
        yield _active
    finally:
        _active.dry_run = previous
