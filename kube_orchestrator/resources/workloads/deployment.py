"""DeploymentManager — full lifecycle management for Kubernetes Deployments."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import ResourceNotFoundError, parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.workloads._builders.deployment_builder import (
    DeploymentBuilder,
)


class DeploymentManager(BaseResourceManager[client.V1Deployment]):
    """Full lifecycle manager for Kubernetes Deployments."""

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
        return "Deployment"

    def _api_version(self) -> str:
        return "apps/v1"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_deployment(
        self,
        builder: DeploymentBuilder | None = None,
        manifest: dict | None = None,
        namespace: str | None = None,
    ) -> client.V1Deployment:
        body = builder.build() if builder else manifest
        ns = namespace or self.default_namespace
        body.setdefault("metadata", {})["namespace"] = ns
        return self.create(body, ns)

    def get_deployment(
        self, name: str, namespace: str | None = None
    ) -> client.V1Deployment:
        return self.get(name, namespace)

    def list_deployments(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1Deployment]:
        return self.list(namespace, label_selector)

    def update_deployment(
        self,
        name: str,
        namespace: str | None = None,
        manifest: dict | None = None,
    ) -> client.V1Deployment:
        return self.update(name, manifest or {}, namespace)

    def patch_deployment(
        self,
        name: str,
        namespace: str | None = None,
        patch: dict | None = None,
        patch_type: str = "strategic",
    ) -> client.V1Deployment:
        return self.patch(name, patch or {}, namespace, patch_type)

    def delete_deployment(
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
            return self.client.apps_v1.patch_namespaced_deployment_scale(
                name=name, namespace=ns, body=body
            )
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
    ) -> client.V1Deployment:
        patch_body = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": container_name, "image": image}]
                    }
                }
            }
        }
        return self.patch_deployment(name, namespace, patch_body, "strategic")

    def set_env_var(
        self,
        name: str,
        namespace: str | None = None,
        container_name: str = "",
        env_name: str = "",
        value: str = "",
    ) -> client.V1Deployment:
        patch: dict[str, Any] = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container_name,
                                "env": [{"name": env_name, "value": value}],
                            }
                        ]
                    }
                }
            }
        }
        return self.patch_deployment(name, namespace, patch, "strategic")

    def set_resource_limits(
        self,
        name: str,
        namespace: str | None = None,
        container_name: str = "",
        cpu_limit: str | None = None,
        memory_limit: str | None = None,
    ) -> client.V1Deployment:
        limits: dict[str, str] = {}
        if cpu_limit:
            limits["cpu"] = cpu_limit
        if memory_limit:
            limits["memory"] = memory_limit
        patch: dict[str, Any] = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": container_name,
                                "resources": {"limits": limits},
                            }
                        ]
                    }
                }
            }
        }
        return self.patch_deployment(name, namespace, patch, "strategic")

    # ------------------------------------------------------------------
    # Rollout management
    # ------------------------------------------------------------------

    def get_rollout_status(
        self, name: str, namespace: str | None = None
    ) -> dict:
        dep = self.get_deployment(name, namespace)
        status = dep.status or client.V1DeploymentStatus()
        return {
            "replicas": status.replicas or 0,
            "ready_replicas": status.ready_replicas or 0,
            "available_replicas": status.available_replicas or 0,
            "updated_replicas": status.updated_replicas or 0,
            "unavailable_replicas": status.unavailable_replicas or 0,
            "observed_generation": status.observed_generation,
        }

    def wait_for_rollout(
        self,
        name: str,
        namespace: str | None = None,
        timeout_seconds: int = 300,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                dep = self.get_deployment(name, namespace)
                spec_replicas = (dep.spec.replicas or 1) if dep.spec else 1
                status = dep.status or client.V1DeploymentStatus()
                if (
                    status.updated_replicas == spec_replicas
                    and status.ready_replicas == spec_replicas
                    and status.available_replicas == spec_replicas
                ):
                    return True
            except ResourceNotFoundError:
                pass
            time.sleep(3)
        return False

    def pause_rollout(
        self, name: str, namespace: str | None = None
    ) -> client.V1Deployment:
        return self.patch_deployment(
            name, namespace, {"spec": {"paused": True}}, "merge"
        )

    def resume_rollout(
        self, name: str, namespace: str | None = None
    ) -> client.V1Deployment:
        return self.patch_deployment(
            name, namespace, {"spec": {"paused": False}}, "merge"
        )

    def restart_rollout(
        self, name: str, namespace: str | None = None
    ) -> client.V1Deployment:
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
        return self.patch_deployment(name, namespace, patch, "merge")

    # ------------------------------------------------------------------
    # Rollout history and rollback
    # ------------------------------------------------------------------

    def get_rollout_history(
        self, name: str, namespace: str | None = None
    ) -> list[dict]:
        ns = namespace or self.default_namespace
        try:
            result = self.client.apps_v1.list_namespaced_replica_set(namespace=ns)
            history: list[dict] = []
            for rs in result.items:
                if not rs.metadata or not rs.metadata.owner_references:
                    continue
                for ref in rs.metadata.owner_references:
                    if ref.kind == "Deployment" and ref.name == name:
                        revision = (rs.metadata.annotations or {}).get(
                            "deployment.kubernetes.io/revision"
                        )
                        history.append(
                            {
                                "revision": revision,
                                "name": rs.metadata.name,
                                "replicas": rs.status.replicas if rs.status else 0,
                                "ready": rs.status.ready_replicas if rs.status else 0,
                            }
                        )
            return sorted(history, key=lambda x: int(x["revision"] or 0))
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def rollback_to_revision(
        self,
        name: str,
        namespace: str | None = None,
        revision: int = 0,
    ) -> client.V1Deployment:
        ns = namespace or self.default_namespace
        try:
            result = self.client.apps_v1.list_namespaced_replica_set(namespace=ns)
            for rs in result.items:
                if not rs.metadata or not rs.metadata.owner_references:
                    continue
                for ref in rs.metadata.owner_references:
                    if ref.kind == "Deployment" and ref.name == name:
                        rev = (rs.metadata.annotations or {}).get(
                            "deployment.kubernetes.io/revision"
                        )
                        if str(rev) == str(revision) and rs.spec:
                            patch: dict[str, Any] = {
                                "spec": {"template": rs.spec.template.to_dict()}  # type: ignore[union-attr]
                            }
                            return self.patch_deployment(name, ns, patch, "strategic")
            raise ResourceNotFoundError("ReplicaSet", f"revision={revision}", ns)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Related resources
    # ------------------------------------------------------------------

    def get_pods(
        self, name: str, namespace: str | None = None
    ) -> list[client.V1Pod]:
        ns = namespace or self.default_namespace
        dep = self.get_deployment(name, ns)
        match_labels = (
            dep.spec.selector.match_labels if dep.spec and dep.spec.selector else {}
        )
        label_selector = ",".join(f"{k}={v}" for k, v in (match_labels or {}).items())
        try:
            result = self.client.core_v1.list_namespaced_pod(
                namespace=ns, label_selector=label_selector
            )
            return result.items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_replica_sets(
        self, name: str, namespace: str | None = None
    ) -> list[client.V1ReplicaSet]:
        ns = namespace or self.default_namespace
        try:
            result = self.client.apps_v1.list_namespaced_replica_set(namespace=ns)
            return [
                rs
                for rs in result.items
                if rs.metadata
                and any(
                    ref.kind == "Deployment" and ref.name == name
                    for ref in (rs.metadata.owner_references or [])
                )
            ]
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def is_available(self, name: str, namespace: str | None = None) -> bool:
        dep = self.get_deployment(name, namespace)
        if not dep.status or not dep.status.conditions:
            return False
        return any(
            c.type == "Available" and c.status == "True"
            for c in dep.status.conditions
        )

    def get_conditions(
        self, name: str, namespace: str | None = None
    ) -> list[dict]:
        dep = self.get_deployment(name, namespace)
        if not dep.status or not dep.status.conditions:
            return []
        return [
            {
                "type": c.type,
                "status": c.status,
                "reason": c.reason,
                "message": c.message,
            }
            for c in dep.status.conditions
        ]
