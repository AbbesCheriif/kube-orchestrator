"""EndpointSliceManager — EndpointSlice read/query operations."""

from __future__ import annotations

from typing import Any

from kubernetes.client import DiscoveryV1Api

from kube_orchestrator.resources.base import BaseResourceManager


class EndpointSliceManager(BaseResourceManager[Any]):
    """Read and query Kubernetes EndpointSlice resources.

    Covers all fields from ``kubectl explain endpointslice``:
      addressType          — IPv4 | IPv6 | FQDN
      endpoints[].addresses
      endpoints[].conditions — ready, serving, terminating
      endpoints[].hints
      endpoints[].hostname
      endpoints[].nodeName
      endpoints[].targetRef
      endpoints[].zone
      ports[]              — appProtocol, name, port, protocol
    """

    def _get_api(self) -> DiscoveryV1Api:
        return self.client.discovery_v1

    def _kind(self) -> str:
        return "EndpointSlice"

    def _api_version(self) -> str:
        return "discovery.k8s.io/v1"

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    def list_slices_for_service(
        self,
        service_name: str,
        namespace: str,
    ) -> list[Any]:
        """Return all EndpointSlices owned by the given Service."""
        label_selector = f"kubernetes.io/service-name={service_name}"
        return self.list(namespace, label_selector=label_selector)

    def get_all_ready_endpoints(
        self,
        service_name: str,
        namespace: str,
    ) -> list[str]:
        """Return all ready IP addresses across every slice for a Service."""
        slices = self.list_slices_for_service(service_name, namespace)
        ips: list[str] = []
        for slc in slices:
            for ep in getattr(slc, "endpoints", []) or []:
                conditions = getattr(ep, "conditions", None)
                ready = getattr(conditions, "ready", None)
                if ready is False:
                    continue
                for addr in getattr(ep, "addresses", []) or []:
                    ips.append(addr)
        return ips

    def get_endpoints_by_node(
        self,
        service_name: str,
        namespace: str,
    ) -> dict[str, list[str]]:
        """Return a mapping of nodeName → list of ready IP addresses."""
        slices = self.list_slices_for_service(service_name, namespace)
        result: dict[str, list[str]] = {}
        for slc in slices:
            for ep in getattr(slc, "endpoints", []) or []:
                conditions = getattr(ep, "conditions", None)
                if getattr(conditions, "ready", None) is False:
                    continue
                node = getattr(ep, "node_name", None) or "__unknown__"
                result.setdefault(node, [])
                result[node].extend(getattr(ep, "addresses", []) or [])
        return result

    def get_endpoints_by_zone(
        self,
        service_name: str,
        namespace: str,
    ) -> dict[str, list[str]]:
        """Return a mapping of zone → list of ready IP addresses."""
        slices = self.list_slices_for_service(service_name, namespace)
        result: dict[str, list[str]] = {}
        for slc in slices:
            for ep in getattr(slc, "endpoints", []) or []:
                conditions = getattr(ep, "conditions", None)
                if getattr(conditions, "ready", None) is False:
                    continue
                zone = getattr(ep, "zone", None) or "__unknown__"
                result.setdefault(zone, [])
                result[zone].extend(getattr(ep, "addresses", []) or [])
        return result
