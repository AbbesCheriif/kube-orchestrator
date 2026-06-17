"""RuntimeClassManager and LeaseManager — cluster-scoped resource managers."""

from __future__ import annotations

from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class RuntimeClassManager(BaseResourceManager[client.V1RuntimeClass]):
    """Manage Kubernetes RuntimeClass resources (cluster-scoped)."""

    def __init__(
        self,
        kube_client: "KubeClient | None" = None,
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, "", dry_run)

    def _get_api(self) -> client.NodeV1Api:
        return self.client.node_v1

    def _kind(self) -> str:
        return "RuntimeClass"

    def _api_version(self) -> str:
        return "node.k8s.io/v1"

    def create_runtime_class(
        self,
        name: str,
        handler: str,
        overhead: dict[str, Any] | None = None,
        scheduling: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
    ) -> client.V1RuntimeClass:
        manifest: dict[str, Any] = {
            "apiVersion": "node.k8s.io/v1",
            "kind": "RuntimeClass",
            "metadata": build_metadata(name, None, labels),
            "handler": handler,
        }
        if overhead:
            manifest["overhead"] = overhead
        if scheduling:
            manifest["scheduling"] = scheduling
        return self.create(manifest)

    def get_runtime_class(self, name: str) -> client.V1RuntimeClass:
        return self.get(name)

    def list_runtime_classes(
        self, label_selector: str | None = None
    ) -> list[client.V1RuntimeClass]:
        return self.list(label_selector=label_selector)

    def delete_runtime_class(self, name: str) -> None:
        self.delete(name)


class LeaseManager(BaseResourceManager[client.V1Lease]):
    """Manage Kubernetes Lease resources (coordination.k8s.io/v1)."""

    def __init__(
        self,
        kube_client: "KubeClient | None" = None,
        default_namespace: str = "kube-system",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.CoordinationV1Api:
        return self.client.coordination_v1

    def _kind(self) -> str:
        return "Lease"

    def _api_version(self) -> str:
        return "coordination.k8s.io/v1"

    def get_lease(self, name: str, namespace: str | None = None) -> client.V1Lease:
        return self.get(name, namespace or self.default_namespace)

    def list_leases(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1Lease]:
        return self.list(
            namespace or self.default_namespace,
            label_selector=label_selector,
        )

    def delete_lease(self, name: str, namespace: str | None = None) -> None:
        self.delete(name, namespace or self.default_namespace)

    def get_holder_identity(self, name: str, namespace: str | None = None) -> str | None:
        lease = self.get_lease(name, namespace)
        if lease.spec:
            return lease.spec.holder_identity
        return None

    def is_expired(self, name: str, namespace: str | None = None) -> bool:
        """Return True if the lease has no renew time (effectively expired/unset)."""
        lease = self.get_lease(name, namespace)
        return lease.spec is None or lease.spec.renew_time is None
