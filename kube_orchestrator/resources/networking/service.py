"""ServiceManager — all Service types with full spec coverage."""

from __future__ import annotations

import time
from typing import Any

from kubernetes.client import (
    CoreV1Api,
    V1Endpoints,
    V1Pod,
    V1Service,
)
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import ResourceNotFoundError, parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class ServiceManager(BaseResourceManager[V1Service]):
    """Manage Kubernetes Service resources (ClusterIP, NodePort, LoadBalancer, ExternalName)."""

    def _get_api(self) -> CoreV1Api:
        return self.client.core_v1

    def _kind(self) -> str:
        return "Service"

    def _api_version(self) -> str:
        return "v1"

    # ------------------------------------------------------------------
    # Full-spec factory
    # ------------------------------------------------------------------

    def create_service(
        self,
        name: str,
        namespace: str,
        selector: dict[str, Any] | None = None,
        ports: list[dict[str, Any]] | None = None,
        service_type: str = "ClusterIP",
        cluster_ip: str | None = None,
        cluster_ips: list[str] | None = None,
        external_ips: list[str] | None = None,
        external_name: str | None = None,
        external_traffic_policy: str | None = None,
        internal_traffic_policy: str | None = None,
        load_balancer_ip: str | None = None,
        load_balancer_source_ranges: list[str] | None = None,
        load_balancer_class: str | None = None,
        health_check_node_port: int | None = None,
        session_affinity: str | None = None,
        session_affinity_timeout: int | None = None,
        publish_not_ready: bool = False,
        ip_families: list[str] | None = None,
        ip_family_policy: str | None = None,
        allocate_lb_node_ports: bool | None = None,
        labels: dict[str, Any] | None = None,
        annotations: dict[str, Any] | None = None,
    ) -> V1Service:
        spec: dict[str, Any] = {"type": service_type}

        if selector is not None:
            spec["selector"] = selector
        if ports:
            spec["ports"] = self._build_ports(ports)
        if cluster_ip is not None:
            spec["clusterIP"] = cluster_ip
        if cluster_ips is not None:
            spec["clusterIPs"] = cluster_ips
        if external_ips is not None:
            spec["externalIPs"] = external_ips
        if external_name is not None:
            spec["externalName"] = external_name
        if external_traffic_policy is not None:
            spec["externalTrafficPolicy"] = external_traffic_policy
        if internal_traffic_policy is not None:
            spec["internalTrafficPolicy"] = internal_traffic_policy
        if load_balancer_ip is not None:
            spec["loadBalancerIP"] = load_balancer_ip
        if load_balancer_source_ranges is not None:
            spec["loadBalancerSourceRanges"] = load_balancer_source_ranges
        if load_balancer_class is not None:
            spec["loadBalancerClass"] = load_balancer_class
        if health_check_node_port is not None:
            spec["healthCheckNodePort"] = health_check_node_port
        if session_affinity is not None:
            spec["sessionAffinity"] = session_affinity
        if session_affinity_timeout is not None:
            spec["sessionAffinityConfig"] = {
                "clientIP": {"timeoutSeconds": session_affinity_timeout}
            }
        if publish_not_ready:
            spec["publishNotReadyAddresses"] = True
        if ip_families is not None:
            spec["ipFamilies"] = ip_families
        if ip_family_policy is not None:
            spec["ipFamilyPolicy"] = ip_family_policy
        if allocate_lb_node_ports is not None:
            spec["allocateLoadBalancerNodePorts"] = allocate_lb_node_ports

        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": build_metadata(
                name=name,
                namespace=namespace,
                labels=labels,
                annotations=annotations,
            ),
            "spec": spec,
        }
        return self.create(manifest, namespace)

    # ------------------------------------------------------------------
    # Convenience factories per service type
    # ------------------------------------------------------------------

    def create_clusterip(
        self,
        name: str,
        namespace: str,
        selector: dict[str, Any],
        ports: list[dict[str, Any]],
        cluster_ip: str | None = None,
        **opts: Any,
    ) -> V1Service:
        return self.create_service(
            name=name,
            namespace=namespace,
            selector=selector,
            ports=ports,
            service_type="ClusterIP",
            cluster_ip=cluster_ip,
            **opts,
        )

    def create_nodeport(
        self,
        name: str,
        namespace: str,
        selector: dict[str, Any],
        ports: list[dict[str, Any]],
        external_traffic_policy: str = "Cluster",
        **opts: Any,
    ) -> V1Service:
        return self.create_service(
            name=name,
            namespace=namespace,
            selector=selector,
            ports=ports,
            service_type="NodePort",
            external_traffic_policy=external_traffic_policy,
            **opts,
        )

    def create_loadbalancer(
        self,
        name: str,
        namespace: str,
        selector: dict[str, Any],
        ports: list[dict[str, Any]],
        load_balancer_ip: str | None = None,
        source_ranges: list[str] | None = None,
        **opts: Any,
    ) -> V1Service:
        return self.create_service(
            name=name,
            namespace=namespace,
            selector=selector,
            ports=ports,
            service_type="LoadBalancer",
            load_balancer_ip=load_balancer_ip,
            load_balancer_source_ranges=source_ranges,
            **opts,
        )

    def create_externalname(
        self,
        name: str,
        namespace: str,
        external_name: str,
        **opts: Any,
    ) -> V1Service:
        return self.create_service(
            name=name,
            namespace=namespace,
            service_type="ExternalName",
            external_name=external_name,
            **opts,
        )

    def create_headless(
        self,
        name: str,
        namespace: str,
        selector: dict[str, Any],
        ports: list[dict[str, Any]],
        **opts: Any,
    ) -> V1Service:
        """Headless service: clusterIP=None, used by StatefulSets."""
        return self.create_service(
            name=name,
            namespace=namespace,
            selector=selector,
            ports=ports,
            service_type="ClusterIP",
            cluster_ip="None",
            **opts,
        )

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def get_service(self, name: str, namespace: str) -> V1Service:
        return self.get(name, namespace)

    def list_services(
        self,
        namespace: str,
        label_selector: str | None = None,
        service_type: str | None = None,
    ) -> list[V1Service]:
        services = self.list(namespace, label_selector=label_selector)
        if service_type is not None:
            services = [
                s
                for s in services
                if getattr(getattr(s, "spec", None), "type", None) == service_type
            ]
        return services

    def update_service(
        self, name: str, namespace: str, manifest: dict[str, Any]
    ) -> V1Service:
        return self.update(name, manifest, namespace)

    def delete_service(self, name: str, namespace: str) -> None:
        self.delete(name, namespace)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_cluster_ip(self, name: str, namespace: str) -> str:
        svc = self.get_service(name, namespace)
        return (svc.spec and svc.spec.cluster_ip) or ""

    def get_external_ip(self, name: str, namespace: str) -> str | None:
        svc = self.get_service(name, namespace)
        ingresses = getattr(getattr(svc, "status", None), "load_balancer", None)
        if ingresses is None:
            return None
        ingress_list = getattr(ingresses, "ingress", None) or []
        if not ingress_list:
            return None
        first = ingress_list[0]
        return getattr(first, "ip", None) or getattr(first, "hostname", None)

    def wait_for_external_ip(
        self,
        name: str,
        namespace: str,
        timeout_seconds: int = 120,
    ) -> str:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            ip = self.get_external_ip(name, namespace)
            if ip:
                return ip
            time.sleep(5)
        raise TimeoutError(
            f"Service {namespace}/{name} did not receive an external IP within "
            f"{timeout_seconds}s"
        )

    def get_node_port(
        self,
        name: str,
        namespace: str,
        port: int,
    ) -> int | None:
        svc = self.get_service(name, namespace)
        for p in getattr(svc.spec, "ports", None) or []:
            if getattr(p, "port", None) == port:
                return getattr(p, "node_port", None)
        return None

    # ------------------------------------------------------------------
    # Endpoint and pod resolution
    # ------------------------------------------------------------------

    def get_endpoints(self, name: str, namespace: str) -> V1Endpoints:
        try:
            return self.client.core_v1.read_namespaced_endpoints(
                name=name, namespace=namespace
            )
        except ApiException as exc:
            if exc.status == 404:
                raise ResourceNotFoundError("Endpoints", name, namespace) from exc
            raise parse_api_exception(exc) from exc

    def get_target_pods(self, name: str, namespace: str) -> list[V1Pod]:
        svc = self.get_service(name, namespace)
        selector_dict: dict[str, Any] = getattr(svc.spec, "selector", None) or {}
        if not selector_dict:
            return []
        label_selector = ",".join(f"{k}={v}" for k, v in selector_dict.items())
        try:
            result = self.client.core_v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )
            return result.items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_port(self, name: str, namespace: str, port: dict[str, Any]) -> V1Service:
        svc = self.get_service(name, namespace)
        existing = [
            self._port_to_dict(p) for p in (getattr(svc.spec, "ports", None) or [])
        ]
        existing.append(port)
        return self.patch(
            name,
            {"spec": {"ports": existing}},
            namespace,
            patch_type="strategic",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ports(ports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for p in ports:
            entry: dict[str, Any] = {
                "port": p["port"],
                "protocol": p.get("protocol", "TCP"),
            }
            if "targetPort" in p:
                entry["targetPort"] = p["targetPort"]
            if "nodePort" in p:
                entry["nodePort"] = p["nodePort"]
            if "name" in p:
                entry["name"] = p["name"]
            if "appProtocol" in p:
                entry["appProtocol"] = p["appProtocol"]
            normalized.append(entry)
        return normalized

    @staticmethod
    def _port_to_dict(port_obj: Any) -> dict[str, Any]:
        result: dict[str, Any] = {
            "port": port_obj.port,
            "protocol": port_obj.protocol or "TCP",
        }
        if port_obj.target_port is not None:
            result["targetPort"] = port_obj.target_port
        if port_obj.node_port is not None:
            result["nodePort"] = port_obj.node_port
        if port_obj.name is not None:
            result["name"] = port_obj.name
        if port_obj.app_protocol is not None:
            result["appProtocol"] = port_obj.app_protocol
        return result
