"""ResourceQuotaManager — namespaced ResourceQuota resource manager."""

from __future__ import annotations

from typing import Any

from kubernetes.client import CoreV1Api, V1ResourceQuota
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class ResourceQuotaManager(BaseResourceManager[V1ResourceQuota]):
    """Manage Kubernetes ResourceQuota resources."""

    def _get_api(self) -> CoreV1Api:
        return self.client.core_v1

    def _kind(self) -> str:
        return "ResourceQuota"

    def _api_version(self) -> str:
        return "v1"

    def create_quota(
        self,
        name: str,
        namespace: str,
        hard: dict,
        scopes: list[str] | None = None,
        scope_selector: dict | None = None,
        labels: dict | None = None,
    ) -> V1ResourceQuota:
        spec: dict[str, Any] = {"hard": hard}
        if scopes:
            spec["scopes"] = scopes
        if scope_selector:
            spec["scopeSelector"] = scope_selector
        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": build_metadata(name=name, namespace=namespace, labels=labels),
            "spec": spec,
        }
        return self.create(manifest, namespace)

    def update_quota(
        self,
        name: str,
        namespace: str,
        hard: dict,
    ) -> V1ResourceQuota:
        quota = self.get_quota(name, namespace)
        quota.spec.hard = hard
        return self.update(name, quota.to_dict(), namespace)

    def get_quota(self, name: str, namespace: str) -> V1ResourceQuota:
        return self.get(name, namespace)

    def list_quotas(self, namespace: str) -> list[V1ResourceQuota]:
        return self.list(namespace=namespace)

    def delete_quota(self, name: str, namespace: str) -> None:
        self.delete(name, namespace)

    def get_used(self, name: str, namespace: str) -> dict:
        """Return the currently-used resource quantities."""
        quota = self.get_quota(name, namespace)
        if quota.status and quota.status.used:
            return dict(quota.status.used)
        return {}

    def get_remaining(self, name: str, namespace: str) -> dict:
        """Return remaining capacity (hard − used) for each resource."""
        quota = self.get_quota(name, namespace)
        if not quota.status:
            return {}
        hard = dict(quota.status.hard or {})
        used = dict(quota.status.used or {})
        remaining: dict[str, str] = {}
        for resource, hard_val in hard.items():
            used_val = used.get(resource, "0")
            remaining[resource] = f"{hard_val} (used: {used_val})"
        return remaining

    def is_limit_reached(self, namespace: str, resource: str) -> bool:
        """Return True if any quota in the namespace has exhausted the given resource."""
        api = self._get_api()
        try:
            quotas = api.list_namespaced_resource_quota(namespace=namespace)
            for quota in quotas.items:
                if not quota.status:
                    continue
                hard = dict(quota.status.hard or {})
                used = dict(quota.status.used or {})
                if resource in hard and resource in used:
                    if used[resource] >= hard[resource]:
                        return True
            return False
        except ApiException as exc:
            raise parse_api_exception(exc) from exc
