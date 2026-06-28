"""Fluent builder for Kubernetes StatefulSet manifests."""

from __future__ import annotations

from typing import Any

from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder


class StatefulSetBuilder:
    """Fluent interface for constructing StatefulSet manifests covering all spec fields."""

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
        self._selector: dict[str, Any] = {}
        self._update_strategy: dict[str, Any] = {}
        self._pod_template: dict[str, Any] = {}
        self._volume_claim_templates: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Replica and service helpers
    # ------------------------------------------------------------------

    def with_replicas(self, count: int) -> StatefulSetBuilder:
        self._spec["replicas"] = count
        return self

    def with_service_name(self, name: str) -> StatefulSetBuilder:
        self._spec["serviceName"] = name
        return self

    def with_selector(
        self,
        match_labels: dict[str, str],
        match_expressions: list[dict[str, Any]] | None = None,
    ) -> StatefulSetBuilder:
        self._selector = {"matchLabels": match_labels}
        if match_expressions:
            self._selector["matchExpressions"] = match_expressions
        return self

    # ------------------------------------------------------------------
    # Pod management policy
    # ------------------------------------------------------------------

    def with_pod_management_policy(self, policy: str) -> StatefulSetBuilder:
        self._spec["podManagementPolicy"] = policy
        return self

    # ------------------------------------------------------------------
    # Update strategy helpers
    # ------------------------------------------------------------------

    def with_rolling_update(
        self,
        max_unavailable: int | str | None = None,
        partition: int = 0,
    ) -> StatefulSetBuilder:
        rolling: dict[str, Any] = {"partition": partition}
        if max_unavailable is not None:
            rolling["maxUnavailable"] = max_unavailable
        self._update_strategy = {
            "type": "RollingUpdate",
            "rollingUpdate": rolling,
        }
        return self

    def with_on_delete_strategy(self) -> StatefulSetBuilder:
        self._update_strategy = {"type": "OnDelete"}
        return self

    # ------------------------------------------------------------------
    # Rollout control helpers
    # ------------------------------------------------------------------

    def with_revision_history_limit(self, limit: int) -> StatefulSetBuilder:
        self._spec["revisionHistoryLimit"] = limit
        return self

    def with_min_ready_seconds(self, seconds: int) -> StatefulSetBuilder:
        self._spec["minReadySeconds"] = seconds
        return self

    def with_ordinals(self, start: int) -> StatefulSetBuilder:
        self._spec["ordinals"] = {"start": start}
        return self

    def with_pvc_retention_policy(
        self,
        when_deleted: str = "Retain",
        when_scaled: str = "Retain",
    ) -> StatefulSetBuilder:
        self._spec["persistentVolumeClaimRetentionPolicy"] = {
            "whenDeleted": when_deleted,
            "whenScaled": when_scaled,
        }
        return self

    # ------------------------------------------------------------------
    # Volume claim templates
    # ------------------------------------------------------------------

    def add_volume_claim_template(
        self,
        name: str,
        storage: str,
        access_modes: list[str],
        storage_class_name: str | None = None,
        volume_mode: str | None = None,
        selector: dict[str, Any] | None = None,
    ) -> StatefulSetBuilder:
        pvc_spec: dict[str, Any] = {
            "accessModes": access_modes,
            "resources": {"requests": {"storage": storage}},
        }
        if storage_class_name is not None:
            pvc_spec["storageClassName"] = storage_class_name
        if volume_mode is not None:
            pvc_spec["volumeMode"] = volume_mode
        if selector is not None:
            pvc_spec["selector"] = selector

        self._volume_claim_templates.append(
            {
                "metadata": {"name": name},
                "spec": pvc_spec,
            }
        )
        return self

    # ------------------------------------------------------------------
    # Pod template helper
    # ------------------------------------------------------------------

    def with_pod_template(self, pod_builder: PodBuilder) -> StatefulSetBuilder:
        pod_manifest = pod_builder.build()
        self._pod_template = {
            "metadata": pod_manifest.get("metadata", {}),
            "spec": pod_manifest.get("spec", {}),
        }
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> dict[str, Any]:
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
        if self._update_strategy:
            spec["updateStrategy"] = self._update_strategy
        if self._pod_template:
            spec["template"] = self._pod_template
        if self._volume_claim_templates:
            spec["volumeClaimTemplates"] = self._volume_claim_templates

        return {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": metadata,
            "spec": spec,
        }
