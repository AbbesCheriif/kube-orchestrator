from __future__ import annotations

from abc import ABC, abstractmethod

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.logging import get_logger


class ScalingStrategy(ABC):
    @abstractmethod
    def should_scale_up(self, metrics: dict) -> bool: ...

    @abstractmethod
    def should_scale_down(self, metrics: dict) -> bool: ...

    @abstractmethod
    def get_desired_replicas(self, current: int, metrics: dict) -> int: ...


class CPUScalingStrategy(ScalingStrategy):
    def __init__(self, target_cpu_utilization: int = 70) -> None:
        self.target_cpu_utilization = target_cpu_utilization

    def should_scale_up(self, metrics: dict) -> bool:
        return metrics.get("cpu_utilization", 0) > self.target_cpu_utilization

    def should_scale_down(self, metrics: dict) -> bool:
        return metrics.get("cpu_utilization", 0) < self.target_cpu_utilization * 0.5

    def get_desired_replicas(self, current: int, metrics: dict) -> int:
        utilization = metrics.get("cpu_utilization", self.target_cpu_utilization)
        if utilization == 0:
            return max(1, current - 1)
        ratio = utilization / self.target_cpu_utilization
        desired = int(current * ratio)
        return max(1, desired)


class MemoryScalingStrategy(ScalingStrategy):
    def __init__(self, target_memory_average: str = "512Mi") -> None:
        self.target_memory_average = target_memory_average
        self._target_bytes = self._parse_memory(target_memory_average)

    def should_scale_up(self, metrics: dict) -> bool:
        avg_bytes = metrics.get("memory_bytes", 0)
        return avg_bytes > self._target_bytes * 0.9

    def should_scale_down(self, metrics: dict) -> bool:
        avg_bytes = metrics.get("memory_bytes", 0)
        return avg_bytes < self._target_bytes * 0.4

    def get_desired_replicas(self, current: int, metrics: dict) -> int:
        avg_bytes = metrics.get("memory_bytes", self._target_bytes)
        if avg_bytes == 0:
            return max(1, current - 1)
        ratio = avg_bytes / self._target_bytes
        return max(1, int(current * ratio))

    @staticmethod
    def _parse_memory(value: str) -> int:
        value = value.strip()
        units = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4}
        for suffix, multiplier in units.items():
            if value.endswith(suffix):
                return int(value[: -len(suffix)]) * multiplier
        return int(value)


class CustomMetricStrategy(ScalingStrategy):
    def __init__(self, metric_name: str, target_value: float) -> None:
        self.metric_name = metric_name
        self.target_value = target_value

    def should_scale_up(self, metrics: dict) -> bool:
        return metrics.get(self.metric_name, 0) > self.target_value

    def should_scale_down(self, metrics: dict) -> bool:
        return metrics.get(self.metric_name, 0) < self.target_value * 0.5

    def get_desired_replicas(self, current: int, metrics: dict) -> int:
        value = metrics.get(self.metric_name, self.target_value)
        if value == 0:
            return max(1, current - 1)
        ratio = value / self.target_value
        return max(1, int(current * ratio))


class ScalingEngine:
    def __init__(self, client: KubeClient | None = None) -> None:
        self._client = client or KubeClient.get_instance()
        self._logger = get_logger(__name__)

    def scale_with_strategy(
        self,
        target_name: str,
        namespace: str,
        kind: str,
        strategy: ScalingStrategy,
        metrics: dict | None = None,
    ) -> None:
        metrics = metrics or {}
        try:
            current = self._get_replicas(target_name, namespace, kind)
            desired = strategy.get_desired_replicas(current, metrics)
            if desired != current:
                self._logger.info(
                    "scaling",
                    target=target_name,
                    kind=kind,
                    from_replicas=current,
                    to_replicas=desired,
                )
                self.set_replicas(target_name, namespace, kind, desired)
        except Exception as exc:
            self._logger.error(
                "scaling_failed",
                target=target_name,
                kind=kind,
                error=str(exc),
            )
            raise

    def set_replicas(
        self, target_name: str, namespace: str, kind: str, replicas: int
    ) -> None:
        patch = {"spec": {"replicas": replicas}}
        kind_lower = kind.lower()
        if kind_lower == "deployment":
            self._client.apps_v1.patch_namespaced_deployment(
                target_name, namespace, patch
            )
        elif kind_lower == "statefulset":
            self._client.apps_v1.patch_namespaced_stateful_set(
                target_name, namespace, patch
            )
        elif kind_lower == "replicaset":
            self._client.apps_v1.patch_namespaced_replica_set(
                target_name, namespace, patch
            )
        else:
            raise ValueError(f"Unsupported kind for scaling: {kind}")
        self._logger.info(
            "replicas_set",
            target=target_name,
            kind=kind,
            namespace=namespace,
            replicas=replicas,
        )

    def _get_replicas(self, target_name: str, namespace: str, kind: str) -> int:
        kind_lower = kind.lower()
        if kind_lower == "deployment":
            obj = self._client.apps_v1.read_namespaced_deployment(
                target_name, namespace
            )
        elif kind_lower == "statefulset":
            obj = self._client.apps_v1.read_namespaced_stateful_set(
                target_name, namespace
            )
        elif kind_lower == "replicaset":
            obj = self._client.apps_v1.read_namespaced_replica_set(
                target_name, namespace
            )
        else:
            raise ValueError(f"Unsupported kind: {kind}")
        return obj.spec.replicas or 1
