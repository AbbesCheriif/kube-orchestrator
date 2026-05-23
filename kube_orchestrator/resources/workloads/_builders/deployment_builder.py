"""Fluent builder for Kubernetes Deployment manifests."""

from __future__ import annotations

from typing import Any

from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder


class DeploymentBuilder:
    """Fluent interface for constructing Deployment manifests covering all spec fields."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> None:
        self._name = name
        self._namespace = namespace
        self._labels: dict[str, str] = labels or {}
        self._annotations: dict[str, str] = annotations or {}
        self._spec: dict[str, Any] = {}
        self._strategy: dict[str, Any] = {}
        self._selector: dict[str, Any] = {}
        self._pod_template: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Replica and selector helpers
    # ------------------------------------------------------------------

    def with_replicas(self, count: int) -> "DeploymentBuilder":
        self._spec["replicas"] = count
        return self

    def with_selector(
        self,
        match_labels: dict[str, str],
        match_expressions: list[dict] | None = None,
    ) -> "DeploymentBuilder":
        self._selector = {"matchLabels": match_labels}
        if match_expressions:
            self._selector["matchExpressions"] = match_expressions
        return self

    # ------------------------------------------------------------------
    # Strategy helpers
    # ------------------------------------------------------------------

    def with_rolling_update(
        self,
        max_surge: int | str = 1,
        max_unavailable: int | str = 0,
    ) -> "DeploymentBuilder":
        self._strategy = {
            "type": "RollingUpdate",
            "rollingUpdate": {
                "maxSurge": max_surge,
                "maxUnavailable": max_unavailable,
            },
        }
        return self

    def with_recreate_strategy(self) -> "DeploymentBuilder":
        self._strategy = {"type": "Recreate"}
        return self

    # ------------------------------------------------------------------
    # Rollout control helpers
    # ------------------------------------------------------------------

    def with_revision_history_limit(self, limit: int) -> "DeploymentBuilder":
        self._spec["revisionHistoryLimit"] = limit
        return self

    def with_progress_deadline(self, seconds: int) -> "DeploymentBuilder":
        self._spec["progressDeadlineSeconds"] = seconds
        return self

    def with_min_ready_seconds(self, seconds: int) -> "DeploymentBuilder":
        self._spec["minReadySeconds"] = seconds
        return self

    def with_paused(self, paused: bool) -> "DeploymentBuilder":
        self._spec["paused"] = paused
        return self

    # ------------------------------------------------------------------
    # Pod template helper
    # ------------------------------------------------------------------

    def with_pod_template(self, pod_builder: PodBuilder) -> "DeploymentBuilder":
        pod_manifest = pod_builder.build()
        self._pod_template = {
            "metadata": pod_manifest.get("metadata", {}),
            "spec": pod_manifest.get("spec", {}),
        }
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> dict:
        metadata: dict[str, Any] = {
            "name": self._name,
            "namespace": self._namespace,
        }
        if self._labels:
            metadata["labels"] = self._labels
        if self._annotations:
            metadata["annotations"] = self._annotations

        spec: dict[str, Any] = dict(self._spec)
        if self._selector:
            spec["selector"] = self._selector
        if self._strategy:
            spec["strategy"] = self._strategy
        if self._pod_template:
            spec["template"] = self._pod_template

        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": metadata,
            "spec": spec,
        }
