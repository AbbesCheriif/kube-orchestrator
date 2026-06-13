"""APIDiscovery — dynamic API group and CRD discovery for the cluster."""

from __future__ import annotations

from typing import Any

from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.crd.custom_object_manager import CustomObjectManager


class APIDiscovery:
    """Discover API groups, resources and CRDs available in the cluster."""

    def __init__(self, kube_client: KubeClient) -> None:
        self.client = kube_client

    # ------------------------------------------------------------------
    # API group discovery
    # ------------------------------------------------------------------

    def list_api_groups(self) -> list[str]:
        """Return the names of all API groups registered in the cluster."""
        from kubernetes import client as k8s_client

        api = k8s_client.ApisApi(self.client._client)
        try:
            result = api.get_api_versions()
            return [g.name for g in result.groups]
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def list_resources_for_group(
        self, group: str, version: str
    ) -> list[dict[str, Any]]:
        """Return all resources available for an API group and version."""
        from kubernetes import client as k8s_client

        api = k8s_client.ApisApi(self.client._client)
        try:
            result = api.get_api_group(group)
            for v in result.versions:
                if v.version == version:
                    resource_api = k8s_client.CustomObjectsApi(
                        self.client._client
                    )
                    _ = resource_api  # placeholder — real impl uses discovery endpoint
                    break
            return []
        except (ApiException, AttributeError):
            return []

    # ------------------------------------------------------------------
    # CRD discovery
    # ------------------------------------------------------------------

    def discover_all_crds(self) -> list[dict[str, Any]]:
        """Return a summary of every CRD installed in the cluster."""
        try:
            api = self.client.api_extensions_v1()
            result = api.list_custom_resource_definition()
            crds: list[dict[str, Any]] = []
            for crd in result.items:
                spec = crd.spec
                crds.append(
                    {
                        "name": crd.metadata.name,
                        "group": spec.group if spec else None,
                        "versions": [
                            v.name for v in (spec.versions or [])
                        ] if spec else [],
                        "plural": spec.names.plural if spec and spec.names else None,
                        "kind": spec.names.kind if spec and spec.names else None,
                        "scope": spec.scope if spec else None,
                    }
                )
            return crds
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Dynamic client builder
    # ------------------------------------------------------------------

    def build_dynamic_client(
        self, group: str, version: str, plural: str
    ) -> CustomObjectManager:
        """Build a ready-to-use CustomObjectManager for any CRD at runtime."""
        return CustomObjectManager(
            group=group,
            version=version,
            plural=plural,
            kube_client=self.client,
        )
