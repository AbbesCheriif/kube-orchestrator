"""KubeClient — singleton API client exposing all Kubernetes API groups."""

from __future__ import annotations

from typing import ClassVar

from kubernetes import client

from kube_orchestrator.core.config import KubeConfig


class KubeClient:
    """Singleton wrapper around the kubernetes-client, one instance per process."""

    _instance: ClassVar[KubeClient | None] = None

    def __init__(self, kube_config: KubeConfig | None = None) -> None:
        cfg = kube_config or KubeConfig()
        if not getattr(cfg, "_active_context", None):
            cfg.load_default()
        api_client = client.ApiClient(configuration=cfg.configuration)
        self._api_client = api_client

    # ------------------------------------------------------------------
    # Singleton lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> "KubeClient":
        """Return (and lazily create) the process-wide singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Destroy the singleton — useful in tests to force re-initialisation."""
        if cls._instance is not None:
            cls._instance._api_client.rest_client.pool_manager.clear()
        cls._instance = None

    # ------------------------------------------------------------------
    # API group properties
    # ------------------------------------------------------------------

    @property
    def core_v1(self) -> client.CoreV1Api:
        return client.CoreV1Api(api_client=self._api_client)

    @property
    def apps_v1(self) -> client.AppsV1Api:
        return client.AppsV1Api(api_client=self._api_client)

    @property
    def networking_v1(self) -> client.NetworkingV1Api:
        return client.NetworkingV1Api(api_client=self._api_client)

    @property
    def rbac_v1(self) -> client.RbacAuthorizationV1Api:
        return client.RbacAuthorizationV1Api(api_client=self._api_client)

    @property
    def autoscaling_v2(self) -> client.AutoscalingV2Api:
        return client.AutoscalingV2Api(api_client=self._api_client)

    @property
    def batch_v1(self) -> client.BatchV1Api:
        return client.BatchV1Api(api_client=self._api_client)

    @property
    def storage_v1(self) -> client.StorageV1Api:
        return client.StorageV1Api(api_client=self._api_client)

    @property
    def scheduling_v1(self) -> client.SchedulingV1Api:
        return client.SchedulingV1Api(api_client=self._api_client)

    @property
    def policy_v1(self) -> client.PolicyV1Api:
        return client.PolicyV1Api(api_client=self._api_client)

    @property
    def custom_objects(self) -> client.CustomObjectsApi:
        return client.CustomObjectsApi(api_client=self._api_client)

    @property
    def api_extensions_v1(self) -> client.ApiextensionsV1Api:
        return client.ApiextensionsV1Api(api_client=self._api_client)

    @property
    def coordination_v1(self) -> client.CoordinationV1Api:
        return client.CoordinationV1Api(api_client=self._api_client)

    @property
    def events_v1(self) -> client.EventsV1Api:
        return client.EventsV1Api(api_client=self._api_client)
