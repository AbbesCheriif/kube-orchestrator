"""NamespaceScope — context manager for scoped multi-resource operations."""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING

from kube_orchestrator.core.client import KubeClient

if TYPE_CHECKING:
    from kube_orchestrator.resources.workloads.pod import PodManager
    from kube_orchestrator.resources.workloads.deployment import DeploymentManager
    from kube_orchestrator.resources.workloads.statefulset import StatefulSetManager
    from kube_orchestrator.resources.workloads.daemonset import DaemonSetManager
    from kube_orchestrator.resources.workloads.job import JobManager
    from kube_orchestrator.resources.workloads.cronjob import CronJobManager


class NamespaceScope:
    """Provide scoped access to all resource managers within a single namespace.

    Usage::

        with NamespaceScope("production", client) as ns:
            pods = ns.pods().list_pods()
            deploys = ns.deployments().list_deployments()
    """

    def __init__(self, namespace: str, client: KubeClient) -> None:
        self._namespace = namespace
        self._client = client

    # ------------------------------------------------------------------
    # Workloads
    # ------------------------------------------------------------------

    def pods(self) -> "PodManager":
        from kube_orchestrator.resources.workloads.pod import PodManager

        return PodManager(client=self._client, default_namespace=self._namespace)

    def deployments(self) -> "DeploymentManager":
        from kube_orchestrator.resources.workloads.deployment import DeploymentManager

        return DeploymentManager(client=self._client, default_namespace=self._namespace)

    def statefulsets(self) -> "StatefulSetManager":
        from kube_orchestrator.resources.workloads.statefulset import StatefulSetManager

        return StatefulSetManager(client=self._client, default_namespace=self._namespace)

    def daemonsets(self) -> "DaemonSetManager":
        from kube_orchestrator.resources.workloads.daemonset import DaemonSetManager

        return DaemonSetManager(client=self._client, default_namespace=self._namespace)

    def jobs(self) -> "JobManager":
        from kube_orchestrator.resources.workloads.job import JobManager

        return JobManager(client=self._client, default_namespace=self._namespace)

    def cronjobs(self) -> "CronJobManager":
        from kube_orchestrator.resources.workloads.cronjob import CronJobManager

        return CronJobManager(client=self._client, default_namespace=self._namespace)

    # ------------------------------------------------------------------
    # Networking (lazy imports — implemented in future days)
    # ------------------------------------------------------------------

    def services(self) -> object:
        from kube_orchestrator.resources.networking.service import ServiceManager  # type: ignore[import]

        return ServiceManager(client=self._client, default_namespace=self._namespace)

    # ------------------------------------------------------------------
    # Storage / Config (lazy imports — implemented in future days)
    # ------------------------------------------------------------------

    def configmaps(self) -> object:
        from kube_orchestrator.resources.storage.configmap import ConfigMapManager  # type: ignore[import]

        return ConfigMapManager(client=self._client, default_namespace=self._namespace)

    def secrets(self) -> object:
        from kube_orchestrator.resources.storage.secret import SecretManager  # type: ignore[import]

        return SecretManager(client=self._client, default_namespace=self._namespace)

    def pvcs(self) -> object:
        from kube_orchestrator.resources.storage.pvc import PVCManager  # type: ignore[import]

        return PVCManager(client=self._client, default_namespace=self._namespace)

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "NamespaceScope":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass
