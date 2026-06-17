"""StatefulSetManager — full lifecycle management for Kubernetes StatefulSets."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import ResourceNotFoundError, parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.workloads._builders.statefulset_builder import (
    StatefulSetBuilder,
)


class StatefulSetManager(BaseResourceManager[client.V1StatefulSet]):
    """Full lifecycle manager for Kubernetes StatefulSets."""

    def __init__(
        self,
        kube_client: "KubeClient | None" = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.AppsV1Api:
        return self.client.apps_v1

    def _kind(self) -> str:
        return "StatefulSet"

    def _api_version(self) -> str:
        return "apps/v1"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_statefulset(
        self,
        builder: StatefulSetBuilder | None = None,
        manifest: dict | None = None,
        namespace: str | None = None,
    ) -> client.V1StatefulSet:
        body = builder.build() if builder else manifest
        return self.create(body, namespace)

    def get_statefulset(
        self, name: str, namespace: str | None = None
    ) -> client.V1StatefulSet:
        return self.get(name, namespace)

    def list_statefulsets(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1StatefulSet]:
        return self.list(namespace, label_selector)

    def update_statefulset(
        self,
        name: str,
        namespace: str | None = None,
        manifest: dict | None = None,
    ) -> client.V1StatefulSet:
        return self.update(name, manifest or {}, namespace)

    def delete_statefulset(
        self,
        name: str,
        namespace: str | None = None,
        propagation_policy: str = "Background",
    ) -> None:
        self.delete(name, namespace, propagation_policy=propagation_policy)

    # ------------------------------------------------------------------
    # Scale
    # ------------------------------------------------------------------

    def scale(
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
            return self.client.apps_v1.patch_namespaced_stateful_set_scale(
                name=name, namespace=ns, body=body
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def ordered_scale_up(
        self,
        name: str,
        namespace: str | None = None,
        replicas: int = 1,
        wait: bool = True,
    ) -> None:
        ns = namespace or self.default_namespace
        sts = self.get_statefulset(name, ns)
        current = (sts.spec.replicas or 0) if sts.spec else 0
        for target in range(current + 1, replicas + 1):
            self.scale(name, ns, target)
            if wait:
                self.wait_for_pod_ordinal(name, ns, target - 1, timeout_seconds=300)

    def ordered_scale_down(
        self,
        name: str,
        namespace: str | None = None,
        replicas: int = 0,
        wait: bool = True,
    ) -> None:
        ns = namespace or self.default_namespace
        sts = self.get_statefulset(name, ns)
        current = (sts.spec.replicas or 0) if sts.spec else 0
        for target in range(current - 1, replicas - 1, -1):
            self.scale(name, ns, target)
            if wait:
                deadline = time.monotonic() + 300
                while time.monotonic() < deadline:
                    try:
                        self.get_pod_by_ordinal(name, ns, target)
                        time.sleep(2)
                    except (ResourceNotFoundError, ApiException):
                        break

    # ------------------------------------------------------------------
    # Pod ordinal helpers
    # ------------------------------------------------------------------

    def get_pod_by_ordinal(
        self, name: str, namespace: str | None = None, ordinal: int = 0
    ) -> client.V1Pod:
        ns = namespace or self.default_namespace
        pod_name = f"{name}-{ordinal}"
        try:
            return self.client.core_v1.read_namespaced_pod(
                name=pod_name, namespace=ns
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def wait_for_pod_ordinal(
        self,
        name: str,
        namespace: str | None = None,
        ordinal: int = 0,
        timeout_seconds: int = 300,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                pod = self.get_pod_by_ordinal(name, namespace, ordinal)
                if pod.status and pod.status.phase == "Running":
                    conditions = pod.status.conditions or []
                    if any(c.type == "Ready" and c.status == "True" for c in conditions):
                        return True
            except (ResourceNotFoundError, ApiException):
                pass
            time.sleep(2)
        return False

    # ------------------------------------------------------------------
    # Update strategy helpers
    # ------------------------------------------------------------------

    def set_partition_update(
        self,
        name: str,
        namespace: str | None = None,
        partition: int = 0,
    ) -> client.V1StatefulSet:
        patch: dict[str, Any] = {
            "spec": {
                "updateStrategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {"partition": partition},
                }
            }
        }
        return self.patch(name, patch, namespace, "merge")

    # ------------------------------------------------------------------
    # Rollout status
    # ------------------------------------------------------------------

    def get_rollout_status(
        self, name: str, namespace: str | None = None
    ) -> dict:
        sts = self.get_statefulset(name, namespace)
        status = sts.status or client.V1StatefulSetStatus(replicas=0)
        spec_replicas = (sts.spec.replicas or 1) if sts.spec else 1
        return {
            "replicas": status.replicas or 0,
            "ready_replicas": status.ready_replicas or 0,
            "current_replicas": status.current_replicas or 0,
            "updated_replicas": status.updated_replicas or 0,
            "available_replicas": status.available_replicas or 0,
            "observed_generation": status.observed_generation,
            "current_revision": status.current_revision,
            "update_revision": status.update_revision,
            "collision_count": status.collision_count or 0,
            "fully_rolled_out": (status.updated_replicas or 0) == spec_replicas
            and (status.ready_replicas or 0) == spec_replicas,
        }

    # ------------------------------------------------------------------
    # PVC helpers
    # ------------------------------------------------------------------

    def get_persistent_volume_claims(
        self, name: str, namespace: str | None = None
    ) -> list[client.V1PersistentVolumeClaim]:
        ns = namespace or self.default_namespace
        try:
            result = self.client.core_v1.list_namespaced_persistent_volume_claim(
                namespace=ns, label_selector=f"app={name}"
            )
            return result.items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Container mutations
    # ------------------------------------------------------------------

    def update_image(
        self,
        name: str,
        namespace: str | None = None,
        container_name: str = "",
        image: str = "",
    ) -> client.V1StatefulSet:
        sts = self.get_statefulset(name, namespace)
        containers = (
            sts.spec.template.spec.containers
            if sts.spec and sts.spec.template and sts.spec.template.spec
            else []
        )
        for c in containers:
            if c.name == container_name:
                c.image = image
                break
        return self.update_statefulset(
            name, namespace, sts.to_dict() if hasattr(sts, "to_dict") else {}
        )

    def restart(
        self, name: str, namespace: str | None = None
    ) -> client.V1StatefulSet:
        now = datetime.now(timezone.utc).isoformat()
        patch: dict[str, Any] = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": now}
                    }
                }
            }
        }
        return self.patch(name, patch, namespace, "merge")
