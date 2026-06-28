"""ReplicaSetManager — full lifecycle management for Kubernetes ReplicaSets."""

from __future__ import annotations

import time
from typing import Any

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import ResourceNotFoundError, parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager


class ReplicaSetManager(BaseResourceManager[client.V1ReplicaSet]):
    """Full lifecycle manager for Kubernetes ReplicaSets."""

    def __init__(
        self,
        kube_client: KubeClient | None = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.AppsV1Api:
        return self.client.apps_v1

    def _kind(self) -> str:
        return "ReplicaSet"

    def _resource_name(self) -> str:
        return "replica_set"

    def _api_version(self) -> str:
        return "apps/v1"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_replicaset(
        self,
        name: str,
        namespace: str | None = None,
        replicas: int = 1,
        selector: dict[str, Any] | None = None,
        pod_template: dict[str, Any] | None = None,
        min_ready_seconds: int | None = None,
        labels: dict[str, str] | None = None,
    ) -> client.V1ReplicaSet:
        ns = namespace or self.default_namespace
        metadata: dict[str, Any] = {"name": name, "namespace": ns}
        if labels:
            metadata["labels"] = labels

        spec: dict[str, Any] = {
            "replicas": replicas,
            "selector": selector or {},
            "template": pod_template or {},
        }
        if min_ready_seconds is not None:
            spec["minReadySeconds"] = min_ready_seconds

        manifest = {
            "apiVersion": "apps/v1",
            "kind": "ReplicaSet",
            "metadata": metadata,
            "spec": spec,
        }
        return self.create(manifest, ns)

    def get_replicaset(
        self, name: str, namespace: str | None = None
    ) -> client.V1ReplicaSet:
        return self.get(name, namespace)

    def list_replicasets(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1ReplicaSet]:
        return self.list(namespace, label_selector)

    def delete_replicaset(
        self,
        name: str,
        namespace: str | None = None,
        propagation_policy: str = "Background",
    ) -> None:
        self.delete(name, namespace, propagation_policy=propagation_policy)

    # ------------------------------------------------------------------
    # Scale
    # ------------------------------------------------------------------

    def scale_replicas(
        self,
        name: str,
        namespace: str | None = None,
        replicas: int = 1,
    ) -> client.V1Scale:
        ns = namespace or self.default_namespace
        body = client.V1Scale(
            metadata=client.V1ObjectMeta(name=name, namespace=ns),
            spec=client.V1ScaleSpec(replicas=replicas),
        )
        try:
            return self.client.apps_v1.patch_namespaced_replica_set_scale(
                name=name, namespace=ns, body=body
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Related resources
    # ------------------------------------------------------------------

    def get_pods(self, name: str, namespace: str | None = None) -> list[client.V1Pod]:
        ns = namespace or self.default_namespace
        rs = self.get_replicaset(name, ns)
        match_labels = (
            rs.spec.selector.match_labels if rs.spec and rs.spec.selector else {}
        )
        label_selector = ",".join(f"{k}={v}" for k, v in (match_labels or {}).items())
        try:
            result = self.client.core_v1.list_namespaced_pod(
                namespace=ns, label_selector=label_selector
            )
            return result.items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_owner_deployment(
        self, name: str, namespace: str | None = None
    ) -> client.V1Deployment | None:
        ns = namespace or self.default_namespace
        rs = self.get_replicaset(name, ns)
        if not rs.metadata or not rs.metadata.owner_references:
            return None
        for ref in rs.metadata.owner_references:
            if ref.kind == "Deployment":
                try:
                    return self.client.apps_v1.read_namespaced_deployment(
                        name=ref.name, namespace=ns
                    )
                except ApiException:
                    return None
        return None

    # ------------------------------------------------------------------
    # Orphan helpers
    # ------------------------------------------------------------------

    def is_orphan(self, name: str, namespace: str | None = None) -> bool:
        rs = self.get_replicaset(name, namespace)
        if not rs.metadata:
            return True
        refs = rs.metadata.owner_references or []
        return not any(ref.kind == "Deployment" for ref in refs)

    def list_orphan_replicasets(
        self, namespace: str | None = None
    ) -> list[client.V1ReplicaSet]:
        all_rs = self.list_replicasets(namespace)
        return [
            rs
            for rs in all_rs
            if not rs.metadata
            or not any(
                ref.kind == "Deployment" for ref in (rs.metadata.owner_references or [])
            )
        ]

    def delete_orphans(self, namespace: str | None = None) -> list[str]:
        orphans = self.list_orphan_replicasets(namespace)
        deleted: list[str] = []
        for rs in orphans:
            rs_name = rs.metadata.name if rs.metadata else None
            if rs_name:
                self.delete_replicaset(rs_name, namespace)
                deleted.append(rs_name)
        return deleted

    # ------------------------------------------------------------------
    # Validation and status helpers
    # ------------------------------------------------------------------

    def validate_selector(
        self, selector: dict[str, str], pod_labels: dict[str, str]
    ) -> bool:
        return all(pod_labels.get(k) == v for k, v in selector.items())

    def get_ready_replicas(self, name: str, namespace: str | None = None) -> int:
        rs = self.get_replicaset(name, namespace)
        return (rs.status.ready_replicas or 0) if rs.status else 0

    def wait_for_replicas(
        self,
        name: str,
        namespace: str | None = None,
        count: int = 1,
        timeout_seconds: int = 120,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                if self.get_ready_replicas(name, namespace) >= count:
                    return True
            except ResourceNotFoundError:
                pass
            time.sleep(2)
        return False
