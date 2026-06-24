"""KubeConfig — kubeconfig loader with multi-context support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from kubernetes import client, config
from kubernetes.config.incluster_config import load_incluster_config
from kubernetes.config.kube_config import (
    KUBE_CONFIG_DEFAULT_LOCATION,
    list_kube_config_contexts,
    load_kube_config,
    load_kube_config_from_dict,
)

_DEFAULT_KUBECONFIG = os.environ.get("KUBECONFIG", KUBE_CONFIG_DEFAULT_LOCATION)


class KubeConfig:
    """Manages kubeconfig loading and context switching."""

    def __init__(self) -> None:
        self._config_file: str | None = None
        self._active_context: str | None = None
        self._configuration: client.Configuration = client.Configuration()

    def load_from_file(self, path: str | None = None) -> None:
        """Load kubeconfig from a file path (defaults to ~/.kube/config)."""
        config_path = path or _DEFAULT_KUBECONFIG
        load_kube_config(
            config_file=config_path,
            client_configuration=self._configuration,
        )
        self._config_file = config_path
        _, active = list_kube_config_contexts(config_file=config_path)
        self._active_context = active["name"] if active else None

    def load_from_incluster(self) -> None:
        """Load config from /var/run/secrets/kubernetes.io (in-cluster)."""
        load_incluster_config(client_configuration=self._configuration)
        self._config_file = None
        self._active_context = "in-cluster"

    def load_default(self) -> None:
        """Auto-detect: try in-cluster first, fall back to kubeconfig file."""
        try:
            self.load_from_incluster()
        except config.ConfigException:
            self.load_from_file()

    def get_current_context(self) -> str:
        """Return the name of the currently active context."""
        if self._active_context is None:
            raise RuntimeError("No kubeconfig loaded. Call load_* first.")
        return self._active_context

    def list_contexts(self) -> list[str]:
        """Return all context names available in the loaded kubeconfig."""
        if self._config_file is None:
            return [self._active_context] if self._active_context else []
        contexts, _ = list_kube_config_contexts(config_file=self._config_file)
        return [ctx["name"] for ctx in contexts]

    def switch_context(self, name: str) -> None:
        """Switch to a named context and reload the client configuration."""
        config_path = self._config_file or _DEFAULT_KUBECONFIG
        load_kube_config(
            config_file=config_path,
            context=name,
            client_configuration=self._configuration,
        )
        self._active_context = name

    def get_namespace_for_context(self, context: str) -> str:
        """Return the default namespace declared for *context* in kubeconfig."""
        config_path = self._config_file or _DEFAULT_KUBECONFIG
        contexts, _ = list_kube_config_contexts(config_file=config_path)
        for ctx in contexts:
            if ctx["name"] == context:
                ctx_details: dict[str, Any] = ctx.get("context", {})
                namespace: str = ctx_details.get("namespace", "default")
                return namespace
        return "default"

    def merge_kubeconfigs(self, paths: list[str]) -> None:
        """Merge multiple kubeconfig files and load the combined result."""
        merged: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [],
            "contexts": [],
            "users": [],
            "preferences": {},
        }
        for p in paths:
            raw = Path(p).read_text(encoding="utf-8")
            import yaml  # lazy import — optional dependency in test envs

            partial: dict[str, Any] = yaml.safe_load(raw)
            for key in ("clusters", "contexts", "users"):
                merged[key].extend(partial.get(key) or [])
            if not merged.get("current-context") and partial.get("current-context"):
                merged["current-context"] = partial["current-context"]

        load_kube_config_from_dict(
            config_dict=merged,
            client_configuration=self._configuration,
        )
        self._config_file = None
        _, active = list_kube_config_contexts.__wrapped__(merged)
        self._active_context = active["name"] if active else None

    @property
    def configuration(self) -> client.Configuration:
        """The underlying kubernetes client Configuration object."""
        return self._configuration
