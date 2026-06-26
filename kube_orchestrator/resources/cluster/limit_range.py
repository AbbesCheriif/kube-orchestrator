"""LimitRangeManager — namespaced LimitRange resource manager."""

from __future__ import annotations

from typing import Any

from kubernetes.client import CoreV1Api, V1LimitRange

from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class LimitRangeManager(BaseResourceManager[V1LimitRange]):
    """Manage Kubernetes LimitRange resources."""

    def _get_api(self) -> CoreV1Api:
        return self.client.core_v1

    def _kind(self) -> str:
        return "LimitRange"

    def _resource_name(self) -> str:
        return "limit_range"

    def _api_version(self) -> str:
        return "v1"

    def create_limit_range(
        self,
        name: str,
        namespace: str,
        limits: list[dict[str, Any]],
        labels: dict[str, Any] | None = None,
    ) -> V1LimitRange:
        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": build_metadata(name=name, namespace=namespace, labels=labels),
            "spec": {"limits": limits},
        }
        return self.create(manifest, namespace)

    def _build_limit_item(
        self,
        limit_type: str,
        max_vals: dict[str, Any],
        min_vals: dict[str, Any],
        default: dict[str, Any] | None = None,
        default_request: dict[str, Any] | None = None,
        max_limit_request_ratio: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item: dict[str, Any] = {"type": limit_type}
        if max_vals:
            item["max"] = max_vals
        if min_vals:
            item["min"] = min_vals
        if default:
            item["default"] = default
        if default_request:
            item["defaultRequest"] = default_request
        if max_limit_request_ratio:
            item["maxLimitRequestRatio"] = max_limit_request_ratio
        return item

    def add_container_limits(
        self,
        name: str,
        namespace: str,
        max_cpu: str | None = None,
        max_memory: str | None = None,
        min_cpu: str | None = None,
        min_memory: str | None = None,
        default_cpu_limit: str | None = None,
        default_memory_limit: str | None = None,
        default_cpu_request: str | None = None,
        default_memory_request: str | None = None,
        max_limit_request_ratio_cpu: str | None = None,
    ) -> V1LimitRange:
        lr = self.get_limit_range(name, namespace)
        limits = list(lr.spec.limits or []) if lr.spec else []
        max_vals = {k: v for k, v in [("cpu", max_cpu), ("memory", max_memory)] if v}
        min_vals = {k: v for k, v in [("cpu", min_cpu), ("memory", min_memory)] if v}
        default = {
            k: v
            for k, v in [("cpu", default_cpu_limit), ("memory", default_memory_limit)]
            if v
        }
        default_req = {
            k: v
            for k, v in [
                ("cpu", default_cpu_request),
                ("memory", default_memory_request),
            ]
            if v
        }
        ratio = (
            {"cpu": max_limit_request_ratio_cpu} if max_limit_request_ratio_cpu else {}
        )
        limits.append(
            self._build_limit_item(
                "Container",
                max_vals,
                min_vals,
                default or None,
                default_req or None,
                ratio or None,
            )  # type: ignore[arg-type]  # dict accepted at runtime
        )
        return self.patch(name, {"spec": {"limits": limits}}, namespace)

    def add_pod_limits(
        self,
        name: str,
        namespace: str,
        max_cpu: str | None = None,
        max_memory: str | None = None,
        min_cpu: str | None = None,
        min_memory: str | None = None,
    ) -> V1LimitRange:
        lr = self.get_limit_range(name, namespace)
        limits = list(lr.spec.limits or []) if lr.spec else []
        max_vals = {k: v for k, v in [("cpu", max_cpu), ("memory", max_memory)] if v}
        min_vals = {k: v for k, v in [("cpu", min_cpu), ("memory", min_memory)] if v}
        limits.append(self._build_limit_item("Pod", max_vals, min_vals))  # type: ignore[arg-type]  # dict accepted at runtime
        return self.patch(name, {"spec": {"limits": limits}}, namespace)

    def add_pvc_limits(
        self,
        name: str,
        namespace: str,
        max_storage: str | None = None,
        min_storage: str | None = None,
    ) -> V1LimitRange:
        lr = self.get_limit_range(name, namespace)
        limits = list(lr.spec.limits or []) if lr.spec else []
        max_vals = {"storage": max_storage} if max_storage else {}
        min_vals = {"storage": min_storage} if min_storage else {}
        item = self._build_limit_item("PersistentVolumeClaim", max_vals, min_vals)
        limits.append(item)  # type: ignore[arg-type]  # dict accepted at runtime
        return self.patch(name, {"spec": {"limits": limits}}, namespace)

    def get_limit_range(self, name: str, namespace: str) -> V1LimitRange:
        return self.get(name, namespace)

    def list_limit_ranges(self, namespace: str) -> list[V1LimitRange]:
        return self.list(namespace=namespace)

    def delete_limit_range(self, name: str, namespace: str) -> None:
        self.delete(name, namespace)
