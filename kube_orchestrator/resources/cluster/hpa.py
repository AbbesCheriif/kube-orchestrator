"""HPAManager — full lifecycle management for Kubernetes HorizontalPodAutoscaler v2."""

from __future__ import annotations

from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class HPAManager(BaseResourceManager[client.V2HorizontalPodAutoscaler]):
    """Manage Kubernetes HorizontalPodAutoscaler (autoscaling/v2) resources."""

    def __init__(
        self,
        kube_client: "KubeClient | None" = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.AutoscalingV2Api:
        return self.client.autoscaling_v2

    def _kind(self) -> str:
        return "HorizontalPodAutoscaler"

    def _api_version(self) -> str:
        return "autoscaling/v2"

    def _resource_name(self) -> str:
        return "horizontal_pod_autoscaler"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_hpa(
        self,
        name: str,
        namespace: str | None = None,
        scale_target_ref: dict[str, str] | None = None,
        min_replicas: int | None = None,
        max_replicas: int = 10,
        metrics: list[dict[str, Any]] | None = None,
        behavior: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
    ) -> client.V2HorizontalPodAutoscaler:
        ns = namespace or self.default_namespace
        manifest: dict[str, Any] = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": build_metadata(name, ns, labels),
            "spec": {
                "scaleTargetRef": scale_target_ref or {},
                "maxReplicas": max_replicas,
            },
        }
        spec = manifest["spec"]
        if min_replicas is not None:
            spec["minReplicas"] = min_replicas
        if metrics:
            spec["metrics"] = metrics
        if behavior:
            spec["behavior"] = behavior
        return self.create(manifest, ns)

    def create_cpu_hpa(
        self,
        name: str,
        namespace: str | None = None,
        target_kind: str = "Deployment",
        target_name: str = "",
        min_replicas: int = 1,
        max_replicas: int = 10,
        target_cpu_utilization: int = 80,
    ) -> client.V2HorizontalPodAutoscaler:
        metrics = [
            {
                "type": "Resource",
                "resource": {
                    "name": "cpu",
                    "target": {
                        "type": "Utilization",
                        "averageUtilization": target_cpu_utilization,
                    },
                },
            }
        ]
        return self.create_hpa(
            name=name,
            namespace=namespace,
            scale_target_ref={
                "apiVersion": "apps/v1",
                "kind": target_kind,
                "name": target_name,
            },
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            metrics=metrics,
        )

    def create_memory_hpa(
        self,
        name: str,
        namespace: str | None = None,
        target_kind: str = "Deployment",
        target_name: str = "",
        min_replicas: int = 1,
        max_replicas: int = 10,
        target_memory_average_value: str = "512Mi",
    ) -> client.V2HorizontalPodAutoscaler:
        metrics = [
            {
                "type": "Resource",
                "resource": {
                    "name": "memory",
                    "target": {
                        "type": "AverageValue",
                        "averageValue": target_memory_average_value,
                    },
                },
            }
        ]
        return self.create_hpa(
            name=name,
            namespace=namespace,
            scale_target_ref={
                "apiVersion": "apps/v1",
                "kind": target_kind,
                "name": target_name,
            },
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            metrics=metrics,
        )

    def get_hpa(
        self, name: str, namespace: str | None = None
    ) -> client.V2HorizontalPodAutoscaler:
        return self.get(name, namespace or self.default_namespace)

    def list_hpas(
        self, namespace: str | None = None
    ) -> list[client.V2HorizontalPodAutoscaler]:
        return self.list(namespace or self.default_namespace)

    def update_hpa(
        self,
        name: str,
        namespace: str | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> client.V2HorizontalPodAutoscaler:
        return self.update(name, manifest or {}, namespace or self.default_namespace)

    def delete_hpa(self, name: str, namespace: str | None = None) -> None:
        self.delete(name, namespace or self.default_namespace)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_current_replicas(
        self, name: str, namespace: str | None = None
    ) -> int | None:
        hpa = self.get_hpa(name, namespace)
        return hpa.status.current_replicas if hpa.status else None

    def get_conditions(
        self, name: str, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        hpa = self.get_hpa(name, namespace)
        if not hpa.status or not hpa.status.conditions:
            return []
        return [
            {
                "type": c.type,
                "status": c.status,
                "reason": c.reason,
                "message": c.message,
            }
            for c in hpa.status.conditions
        ]

    # ------------------------------------------------------------------
    # Patch helpers
    # ------------------------------------------------------------------

    def add_metric(
        self,
        name: str,
        namespace: str | None = None,
        metric: dict[str, Any] | None = None,
    ) -> client.V2HorizontalPodAutoscaler:
        hpa = self.get_hpa(name, namespace)
        current_metrics: list[Any] = list(hpa.spec.metrics or [])
        current_metrics.append(metric or {})
        patch: dict[str, Any] = {"spec": {"metrics": current_metrics}}
        return self.patch(name, patch, namespace or self.default_namespace)

    def set_behavior(
        self,
        name: str,
        namespace: str | None = None,
        behavior: dict[str, Any] | None = None,
    ) -> client.V2HorizontalPodAutoscaler:
        patch: dict[str, Any] = {"spec": {"behavior": behavior or {}}}
        return self.patch(name, patch, namespace or self.default_namespace)
