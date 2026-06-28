from __future__ import annotations

from typing import Any

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.logging import get_logger


class MetricsClient:
    def __init__(self, client: KubeClient | None = None) -> None:
        self._client = client or KubeClient.get_instance()
        self._logger = get_logger(__name__)

    def get_pod_metrics(self, name: str, namespace: str) -> dict[str, Any]:
        try:
            result = self._client.custom_objects.get_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods",
                name=name,
            )
            return self._parse_pod_metrics(result)
        except Exception as exc:
            self._logger.warning("get_pod_metrics_failed", pod=name, error=str(exc))
            return {}

    def get_node_metrics(self, name: str) -> dict[str, Any]:
        try:
            result = self._client.custom_objects.get_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes",
                name=name,
            )
            return self._parse_node_metrics(result)
        except Exception as exc:
            self._logger.warning("get_node_metrics_failed", node=name, error=str(exc))
            return {}

    def list_pod_metrics(
        self, namespace: str, label_selector: str | None = None
    ) -> list[Any]:
        try:
            kwargs: dict[str, Any] = {
                "group": "metrics.k8s.io",
                "version": "v1beta1",
                "namespace": namespace,
                "plural": "pods",
            }
            if label_selector:
                kwargs["label_selector"] = label_selector
            result = self._client.custom_objects.list_namespaced_custom_object(**kwargs)
            return [self._parse_pod_metrics(item) for item in result.get("items", [])]
        except Exception as exc:
            self._logger.warning(
                "list_pod_metrics_failed", namespace=namespace, error=str(exc)
            )
            return []

    def list_node_metrics(self) -> list[Any]:
        try:
            result = self._client.custom_objects.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes",
            )
            return [self._parse_node_metrics(item) for item in result.get("items", [])]
        except Exception as exc:
            self._logger.warning("list_node_metrics_failed", error=str(exc))
            return []

    def get_top_pods(self, namespace: str, top: int = 5) -> list[Any]:
        metrics = self.list_pod_metrics(namespace)
        sorted_metrics = sorted(
            metrics, key=lambda m: m.get("cpu_cores", 0), reverse=True
        )
        return sorted_metrics[:top]

    def get_top_nodes(self, top: int = 5) -> list[Any]:
        metrics = self.list_node_metrics()
        sorted_metrics = sorted(
            metrics, key=lambda m: m.get("cpu_cores", 0), reverse=True
        )
        return sorted_metrics[:top]

    def _parse_pod_metrics(self, raw: dict[str, Any]) -> dict[str, Any]:
        containers = raw.get("containers", [])
        total_cpu: float = 0
        total_memory = 0
        for container in containers:
            usage = container.get("usage", {})
            total_cpu += self._parse_cpu(usage.get("cpu", "0"))
            total_memory += self._parse_memory(usage.get("memory", "0"))
        return {
            "name": raw.get("metadata", {}).get("name", ""),
            "namespace": raw.get("metadata", {}).get("namespace", ""),
            "cpu_cores": total_cpu,
            "memory_bytes": total_memory,
            "containers": len(containers),
        }

    def _parse_node_metrics(self, raw: dict[str, Any]) -> dict[str, Any]:
        usage = raw.get("usage", {})
        return {
            "name": raw.get("metadata", {}).get("name", ""),
            "cpu_cores": self._parse_cpu(usage.get("cpu", "0")),
            "memory_bytes": self._parse_memory(usage.get("memory", "0")),
        }

    @staticmethod
    def _parse_cpu(value: str) -> float:
        value = value.strip()
        if value.endswith("n"):
            return int(value[:-1]) / 1_000_000_000
        if value.endswith("m"):
            return int(value[:-1]) / 1000
        try:
            return float(value)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_memory(value: str) -> int:
        value = value.strip()
        units = {
            "Ki": 1024,
            "Mi": 1024**2,
            "Gi": 1024**3,
            "Ti": 1024**4,
            "k": 1000,
            "M": 1000**2,
            "G": 1000**3,
        }
        for suffix, multiplier in units.items():
            if value.endswith(suffix):
                return int(value[: -len(suffix)]) * multiplier
        try:
            return int(value)
        except ValueError:
            return 0
