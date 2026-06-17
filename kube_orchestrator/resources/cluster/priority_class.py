"""PriorityClassManager — cluster-scoped PriorityClass resource manager."""

from __future__ import annotations

from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class PriorityClassManager(BaseResourceManager[client.V1PriorityClass]):
    """Manage Kubernetes PriorityClass resources (cluster-scoped)."""

    def __init__(
        self,
        kube_client: "KubeClient | None" = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.SchedulingV1Api:
        return self.client.scheduling_v1

    def _kind(self) -> str:
        return "PriorityClass"

    def _api_version(self) -> str:
        return "scheduling.k8s.io/v1"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_priority_class(
        self,
        name: str,
        value: int,
        global_default: bool = False,
        description: str | None = None,
        preemption_policy: str = "PreemptLowerPriority",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> client.V1PriorityClass:
        metadata = build_metadata(
            name=name,
            namespace=None,
            labels=labels,
            annotations=annotations,
        )
        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": metadata,
            "value": value,
            "globalDefault": global_default,
            "preemptionPolicy": preemption_policy,
        }
        if description is not None:
            manifest["description"] = description

        try:
            return self.client.scheduling_v1.create_priority_class(
                body=manifest,
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_priority_class(self, name: str) -> client.V1PriorityClass:
        try:
            return self.client.scheduling_v1.read_priority_class(name=name)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def list_priority_classes(
        self,
        label_selector: str | None = None,
    ) -> list[client.V1PriorityClass]:
        try:
            result = self.client.scheduling_v1.list_priority_class(
                label_selector=label_selector
            )
            return result.items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def delete_priority_class(self, name: str) -> None:
        try:
            self.client.scheduling_v1.delete_priority_class(
                name=name,
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Global default helpers
    # ------------------------------------------------------------------

    def set_global_default(self, name: str) -> client.V1PriorityClass:
        """Set this PriorityClass as the cluster global default."""
        try:
            return self.client.scheduling_v1.patch_priority_class(
                name=name,
                body={"globalDefault": True},
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def unset_global_default(self, name: str) -> client.V1PriorityClass:
        try:
            return self.client.scheduling_v1.patch_priority_class(
                name=name,
                body={"globalDefault": False},
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_global_default(self) -> client.V1PriorityClass | None:
        for pc in self.list_priority_classes():
            if pc.global_default:
                return pc
        return None

    # ------------------------------------------------------------------
    # Pod spec helper
    # ------------------------------------------------------------------

    def assign_to_pod_spec(
        self, pod_spec: dict, priority_class_name: str
    ) -> dict:
        """Inject priorityClassName into a pod spec dict."""
        pod_spec["priorityClassName"] = priority_class_name
        return pod_spec

    # ------------------------------------------------------------------
    # Workload lookup
    # ------------------------------------------------------------------

    def get_workloads_using(
        self, name: str, namespace: str | None = None
    ) -> list[dict]:
        """Return all pods in namespace that use this PriorityClass."""
        ns = namespace or self.default_namespace
        try:
            result = self.client.core_v1.list_namespaced_pod(namespace=ns)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

        matching: list[dict] = []
        for pod in result.items:
            if (
                pod.spec
                and pod.spec.priority_class_name == name
            ):
                matching.append({
                    "kind": "Pod",
                    "name": pod.metadata.name if pod.metadata else "",
                    "namespace": pod.metadata.namespace if pod.metadata else ns,
                })
        return matching
