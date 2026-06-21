"""DaemonSetManager — full lifecycle management for Kubernetes DaemonSets."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import ResourceNotFoundError, parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager


class DaemonSetManager(BaseResourceManager[client.V1DaemonSet]):
    """Full lifecycle manager for Kubernetes DaemonSets."""

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
        return "DaemonSet"

    def _api_version(self) -> str:
        return "apps/v1"

    def _resource_name(self) -> str:
        return "daemon_set"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_daemonset(
        self,
        name: str,
        namespace: str | None = None,
        selector: dict | None = None,
        pod_template: dict | None = None,
        update_strategy: dict | None = None,
        min_ready_seconds: int | None = None,
        revision_history_limit: int | None = None,
        labels: dict[str, str] | None = None,
    ) -> client.V1DaemonSet:
        ns = namespace or self.default_namespace
        metadata: dict[str, Any] = {"name": name, "namespace": ns}
        if labels:
            metadata["labels"] = labels

        spec: dict[str, Any] = {
            "selector": selector or {},
            "template": pod_template or {},
        }
        if update_strategy is not None:
            spec["updateStrategy"] = update_strategy
        if min_ready_seconds is not None:
            spec["minReadySeconds"] = min_ready_seconds
        if revision_history_limit is not None:
            spec["revisionHistoryLimit"] = revision_history_limit

        manifest: dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "DaemonSet",
            "metadata": metadata,
            "spec": spec,
        }
        return self.create(manifest, ns)

    def get_daemonset(
        self, name: str, namespace: str | None = None
    ) -> client.V1DaemonSet:
        return self.get(name, namespace)

    def list_daemonsets(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1DaemonSet]:
        return self.list(namespace, label_selector)

    def update_daemonset(
        self,
        name: str,
        namespace: str | None = None,
        manifest: dict | None = None,
    ) -> client.V1DaemonSet:
        return self.update(name, manifest or {}, namespace)

    def delete_daemonset(
        self,
        name: str,
        namespace: str | None = None,
        propagation_policy: str = "Background",
    ) -> None:
        self.delete(name, namespace, propagation_policy=propagation_policy)

    # ------------------------------------------------------------------
    # Update strategy helpers
    # ------------------------------------------------------------------

    def set_rolling_update_strategy(
        self,
        name: str,
        namespace: str | None = None,
        max_unavailable: int | str = 1,
        max_surge: int | str | None = None,
    ) -> client.V1DaemonSet:
        rolling: dict[str, Any] = {"maxUnavailable": max_unavailable}
        if max_surge is not None:
            rolling["maxSurge"] = max_surge
        patch: dict[str, Any] = {
            "spec": {
                "updateStrategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": rolling,
                }
            }
        }
        return self.patch(name, patch, namespace, "merge")

    def set_on_delete_strategy(
        self, name: str, namespace: str | None = None
    ) -> client.V1DaemonSet:
        patch: dict[str, Any] = {
            "spec": {"updateStrategy": {"type": "OnDelete"}}
        }
        return self.patch(name, patch, namespace, "merge")

    # ------------------------------------------------------------------
    # Container mutations
    # ------------------------------------------------------------------

    def update_image(
        self,
        name: str,
        namespace: str | None = None,
        container_name: str = "",
        image: str = "",
    ) -> client.V1DaemonSet:
        ds = self.get_daemonset(name, namespace)
        containers = (
            ds.spec.template.spec.containers
            if ds.spec and ds.spec.template and ds.spec.template.spec
            else []
        )
        for c in containers:
            if c.name == container_name:
                c.image = image
                break
        return self.update_daemonset(
            name, namespace, ds.to_dict() if hasattr(ds, "to_dict") else {}
        )

    # ------------------------------------------------------------------
    # Scheduling helpers
    # ------------------------------------------------------------------

    def set_node_selector(
        self,
        name: str,
        namespace: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> client.V1DaemonSet:
        patch: dict[str, Any] = {
            "spec": {
                "template": {
                    "spec": {"nodeSelector": labels or {}}
                }
            }
        }
        return self.patch(name, patch, namespace, "merge")

    def add_toleration(
        self,
        name: str,
        namespace: str | None = None,
        key: str = "",
        operator: str = "Equal",
        value: str | None = None,
        effect: str | None = None,
        toleration_seconds: int | None = None,
    ) -> client.V1DaemonSet:
        ds = self.get_daemonset(name, namespace)
        tol: dict[str, Any] = {"key": key, "operator": operator}
        if value is not None:
            tol["value"] = value
        if effect is not None:
            tol["effect"] = effect
        if toleration_seconds is not None:
            tol["tolerationSeconds"] = toleration_seconds

        existing: list[dict] = []
        if (
            ds.spec
            and ds.spec.template
            and ds.spec.template.spec
            and ds.spec.template.spec.tolerations
        ):
            existing = [
                t.to_dict() if hasattr(t, "to_dict") else t
                for t in ds.spec.template.spec.tolerations
            ]
        existing.append(tol)

        patch: dict[str, Any] = {
            "spec": {"template": {"spec": {"tolerations": existing}}}
        }
        return self.patch(name, patch, namespace, "merge")

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_desired_scheduled(
        self, name: str, namespace: str | None = None
    ) -> int:
        ds = self.get_daemonset(name, namespace)
        return (ds.status.desired_number_scheduled or 0) if ds.status else 0

    def get_number_ready(
        self, name: str, namespace: str | None = None
    ) -> int:
        ds = self.get_daemonset(name, namespace)
        return (ds.status.number_ready or 0) if ds.status else 0

    def get_pods_per_node(
        self, name: str, namespace: str | None = None
    ) -> dict[str, client.V1Pod]:
        ns = namespace or self.default_namespace
        ds = self.get_daemonset(name, ns)
        match_labels = (
            ds.spec.selector.match_labels if ds.spec and ds.spec.selector else {}
        )
        label_selector = ",".join(
            f"{k}={v}" for k, v in (match_labels or {}).items()
        )
        try:
            result = self.client.core_v1.list_namespaced_pod(
                namespace=ns, label_selector=label_selector
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

        mapping: dict[str, client.V1Pod] = {}
        for pod in result.items:
            node = (pod.spec.node_name or "") if pod.spec else ""
            if node:
                mapping[node] = pod
        return mapping

    def get_rollout_status(
        self, name: str, namespace: str | None = None
    ) -> dict:
        ds = self.get_daemonset(name, namespace)
        status = ds.status
        desired = (status.desired_number_scheduled or 0) if status else 0
        return {
            "desired_number_scheduled": desired,
            "current_number_scheduled": (status.current_number_scheduled or 0) if status else 0,
            "number_ready": (status.number_ready or 0) if status else 0,
            "number_available": (status.number_available or 0) if status else 0,
            "number_unavailable": (status.number_unavailable or 0) if status else 0,
            "updated_number_scheduled": (status.updated_number_scheduled or 0) if status else 0,
            "number_misscheduled": (status.number_mis_scheduled or 0) if status else 0,
            "observed_generation": (status.observed_generation or 0) if status else 0,
            "fully_rolled_out": (
                desired > 0
                and (status.number_ready or 0) == desired
                and (status.updated_number_scheduled or 0) == desired
            ) if status else False,
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
                rollout = self.get_rollout_status(name, namespace)
                if rollout["fully_rolled_out"]:
                    return True
            except ResourceNotFoundError:
                pass
            time.sleep(5)
        return False

    # ------------------------------------------------------------------
    # Restart
    # ------------------------------------------------------------------

    def restart(
        self, name: str, namespace: str | None = None
    ) -> client.V1DaemonSet:
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
