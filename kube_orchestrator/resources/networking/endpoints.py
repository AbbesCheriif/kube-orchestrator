"""EndpointsManager — full Endpoints spec coverage."""

from __future__ import annotations

from typing import Any

from kubernetes.client import (
    CoreV1Api,
    V1Endpoints,
)

from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class EndpointsManager(BaseResourceManager[V1Endpoints]):
    """Manage Kubernetes Endpoints resources with full spec coverage.

    Covers all fields from ``kubectl explain endpoints``:
      subsets[].addresses        — ip, hostname, nodeName, targetRef
      subsets[].notReadyAddresses
      subsets[].ports            — appProtocol, name, port, protocol
    """

    def _get_api(self) -> CoreV1Api:
        return self.client.core_v1

    def _kind(self) -> str:
        return "Endpoints"

    def _api_version(self) -> str:
        return "v1"

    # ------------------------------------------------------------------
    # Full-spec factory
    # ------------------------------------------------------------------

    def create_endpoints(
        self,
        name: str,
        namespace: str,
        subsets: list[dict],
        labels: dict | None = None,
    ) -> V1Endpoints:
        """Create an Endpoints object.

        Each subset dict may contain:
          - addresses: list of {ip, hostname, nodeName, targetRef}
          - notReadyAddresses: list of same
          - ports: list of {name, port, protocol, appProtocol}
        """
        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": build_metadata(name=name, namespace=namespace, labels=labels),
            "subsets": [self._build_subset(s) for s in subsets],
        }
        return self.create(manifest, namespace)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def get_endpoints(self, name: str, namespace: str) -> V1Endpoints:
        return self.get(name, namespace)

    def list_endpoints(self, namespace: str) -> list[V1Endpoints]:
        return self.list(namespace)

    def update_endpoints(
        self,
        name: str,
        namespace: str,
        subsets: list[dict],
    ) -> V1Endpoints:
        """Replace the subsets of an existing Endpoints object."""
        current = self.get_endpoints(name, namespace)
        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": {
                "name": name,
                "namespace": namespace,
                "resourceVersion": getattr(
                    getattr(current, "metadata", None), "resource_version", None
                ),
            },
            "subsets": [self._build_subset(s) for s in subsets],
        }
        return self.update(name, manifest, namespace)

    def delete_endpoints(self, name: str, namespace: str) -> None:
        self.delete(name, namespace)

    # ------------------------------------------------------------------
    # Address management
    # ------------------------------------------------------------------

    def add_address(
        self,
        name: str,
        namespace: str,
        ip: str,
        port: int,
        protocol: str = "TCP",
        hostname: str | None = None,
        node_name: str | None = None,
        target_ref: dict | None = None,
    ) -> V1Endpoints:
        """Add a ready address + port to the first subset (or create one)."""
        current = self.get_endpoints(name, namespace)
        raw_subsets: list[dict[str, Any]] = self._object_to_subsets(current)

        address: dict[str, Any] = {"ip": ip}
        if hostname:
            address["hostname"] = hostname
        if node_name:
            address["nodeName"] = node_name
        if target_ref:
            address["targetRef"] = target_ref

        port_entry: dict[str, Any] = {"port": port, "protocol": protocol}

        if raw_subsets:
            subset = raw_subsets[0]
            subset.setdefault("addresses", [])
            subset["addresses"].append(address)
            subset.setdefault("ports", [])
            if not any(p.get("port") == port for p in subset["ports"]):
                subset["ports"].append(port_entry)
        else:
            raw_subsets.append({"addresses": [address], "ports": [port_entry]})

        return self.update_endpoints(name, namespace, raw_subsets)

    def remove_address(
        self,
        name: str,
        namespace: str,
        ip: str,
    ) -> V1Endpoints:
        """Remove the address with the given IP from all subsets."""
        current = self.get_endpoints(name, namespace)
        raw_subsets = self._object_to_subsets(current)

        for subset in raw_subsets:
            subset["addresses"] = [
                a for a in subset.get("addresses", []) if a.get("ip") != ip
            ]
            subset["notReadyAddresses"] = [
                a for a in subset.get("notReadyAddresses", []) if a.get("ip") != ip
            ]

        return self.update_endpoints(name, namespace, raw_subsets)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_ready_addresses(self, name: str, namespace: str) -> list[str]:
        """Return the list of ready IP addresses across all subsets."""
        ep = self.get_endpoints(name, namespace)
        ips: list[str] = []
        for subset in getattr(ep, "subsets", []) or []:
            for addr in getattr(subset, "addresses", []) or []:
                ip = getattr(addr, "ip", None)
                if ip:
                    ips.append(ip)
        return ips

    def get_not_ready_addresses(self, name: str, namespace: str) -> list[str]:
        """Return the list of not-ready IP addresses across all subsets."""
        ep = self.get_endpoints(name, namespace)
        ips: list[str] = []
        for subset in getattr(ep, "subsets", []) or []:
            for addr in getattr(subset, "not_ready_addresses", []) or []:
                ip = getattr(addr, "ip", None)
                if ip:
                    ips.append(ip)
        return ips

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_address(addr: dict) -> dict[str, Any]:
        entry: dict[str, Any] = {"ip": addr["ip"]}
        if "hostname" in addr:
            entry["hostname"] = addr["hostname"]
        if "nodeName" in addr:
            entry["nodeName"] = addr["nodeName"]
        if "targetRef" in addr:
            entry["targetRef"] = addr["targetRef"]
        return entry

    @staticmethod
    def _build_port(p: dict) -> dict[str, Any]:
        entry: dict[str, Any] = {"port": p["port"]}
        if "name" in p:
            entry["name"] = p["name"]
        if "protocol" in p:
            entry["protocol"] = p["protocol"]
        if "appProtocol" in p:
            entry["appProtocol"] = p["appProtocol"]
        return entry

    def _build_subset(self, subset: dict) -> dict[str, Any]:
        entry: dict[str, Any] = {}
        if "addresses" in subset:
            entry["addresses"] = [self._build_address(a) for a in subset["addresses"]]
        if "notReadyAddresses" in subset:
            entry["notReadyAddresses"] = [
                self._build_address(a) for a in subset["notReadyAddresses"]
            ]
        if "ports" in subset:
            entry["ports"] = [self._build_port(p) for p in subset["ports"]]
        return entry

    @staticmethod
    def _object_to_subsets(ep: V1Endpoints) -> list[dict[str, Any]]:
        """Convert a V1Endpoints object back to a list of raw subset dicts."""
        result: list[dict[str, Any]] = []
        for subset in getattr(ep, "subsets", []) or []:
            raw: dict[str, Any] = {}

            addresses = getattr(subset, "addresses", None)
            if addresses:
                raw["addresses"] = [
                    {
                        k: v
                        for k, v in {
                            "ip": getattr(a, "ip", None),
                            "hostname": getattr(a, "hostname", None),
                            "nodeName": getattr(a, "node_name", None),
                        }.items()
                        if v is not None
                    }
                    for a in addresses
                ]

            not_ready = getattr(subset, "not_ready_addresses", None)
            if not_ready:
                raw["notReadyAddresses"] = [
                    {
                        k: v
                        for k, v in {
                            "ip": getattr(a, "ip", None),
                            "hostname": getattr(a, "hostname", None),
                            "nodeName": getattr(a, "node_name", None),
                        }.items()
                        if v is not None
                    }
                    for a in not_ready
                ]

            ports = getattr(subset, "ports", None)
            if ports:
                raw["ports"] = [
                    {
                        k: v
                        for k, v in {
                            "name": getattr(p, "name", None),
                            "port": getattr(p, "port", None),
                            "protocol": getattr(p, "protocol", None),
                            "appProtocol": getattr(p, "app_protocol", None),
                        }.items()
                        if v is not None
                    }
                    for p in ports
                ]

            result.append(raw)
        return result
