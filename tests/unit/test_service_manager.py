"""Unit tests for ServiceManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError, ResourceNotFoundError
from kube_orchestrator.resources.networking.service import ServiceManager


@pytest.fixture
def svc_manager(mock_kube_client: MagicMock) -> ServiceManager:
    return ServiceManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestServiceManager:
    def test_create_clusterip(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_service.return_value = MagicMock()
        svc_manager.create_clusterip(
            name="my-svc",
            namespace="default",
            selector={"app": "web"},
            ports=[{"port": 80, "targetPort": 8080}],
        )
        mock_core_v1.create_namespaced_service.assert_called_once()

    def test_create_nodeport(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_service.return_value = MagicMock()
        svc_manager.create_nodeport(
            name="my-np",
            namespace="default",
            selector={"app": "web"},
            ports=[{"port": 80, "targetPort": 8080, "nodePort": 30080}],
            external_traffic_policy="Cluster",
        )
        mock_core_v1.create_namespaced_service.assert_called_once()

    def test_create_loadbalancer(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_service.return_value = MagicMock()
        svc_manager.create_loadbalancer(
            name="my-lb",
            namespace="default",
            selector={"app": "web"},
            ports=[{"port": 443, "targetPort": 8443}],
        )
        mock_core_v1.create_namespaced_service.assert_called_once()

    def test_create_headless(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_service.return_value = MagicMock()
        svc_manager.create_headless(
            name="my-headless",
            namespace="default",
            selector={"app": "my-ss"},
            ports=[{"port": 9042}],
        )
        call_args = mock_core_v1.create_namespaced_service.call_args
        body = call_args[0][1] if call_args[0] else call_args[1].get("body")
        assert body["spec"]["clusterIP"] == "None"

    def test_delete_service(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc_manager.delete_service("my-svc", "default")
        mock_core_v1.delete_namespaced_service.assert_called_once()

    def test_create_externalname(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc_manager.create_externalname(
            "my-ext", "default", external_name="db.example.com"
        )
        call_kwargs = mock_core_v1.create_namespaced_service.call_args.kwargs
        assert call_kwargs["body"]["spec"]["externalName"] == "db.example.com"
        assert call_kwargs["body"]["spec"]["type"] == "ExternalName"

    def test_create_service_with_all_optional_fields(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc_manager.create_service(
            "full-svc",
            "default",
            selector={"app": "web"},
            ports=[{"port": 80, "name": "http", "appProtocol": "http"}],
            cluster_ip="10.0.0.5",
            cluster_ips=["10.0.0.5"],
            external_ips=["1.2.3.4"],
            external_traffic_policy="Local",
            internal_traffic_policy="Local",
            load_balancer_ip="5.6.7.8",
            load_balancer_source_ranges=["10.0.0.0/8"],
            load_balancer_class="internal",
            health_check_node_port=30000,
            session_affinity="ClientIP",
            session_affinity_timeout=100,
            publish_not_ready=True,
            ip_families=["IPv4"],
            ip_family_policy="SingleStack",
            allocate_lb_node_ports=False,
        )
        call_kwargs = mock_core_v1.create_namespaced_service.call_args.kwargs
        spec = call_kwargs["body"]["spec"]
        assert spec["clusterIP"] == "10.0.0.5"
        assert spec["clusterIPs"] == ["10.0.0.5"]
        assert spec["externalIPs"] == ["1.2.3.4"]
        assert spec["externalTrafficPolicy"] == "Local"
        assert spec["internalTrafficPolicy"] == "Local"
        assert spec["loadBalancerIP"] == "5.6.7.8"
        assert spec["loadBalancerSourceRanges"] == ["10.0.0.0/8"]
        assert spec["loadBalancerClass"] == "internal"
        assert spec["healthCheckNodePort"] == 30000
        assert spec["sessionAffinityConfig"]["clientIP"]["timeoutSeconds"] == 100
        assert spec["publishNotReadyAddresses"] is True
        assert spec["ipFamilies"] == ["IPv4"]
        assert spec["ipFamilyPolicy"] == "SingleStack"
        assert spec["allocateLoadBalancerNodePorts"] is False
        assert spec["ports"][0]["appProtocol"] == "http"

    def test_get_service(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_service.return_value = "svc-obj"
        assert svc_manager.get_service("my-svc", "default") == "svc-obj"

    def test_list_services_without_filter(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        s1 = MagicMock()
        s1.spec.type = "ClusterIP"
        mock_core_v1.list_namespaced_service.return_value.items = [s1]
        assert svc_manager.list_services("default") == [s1]

    def test_list_services_filtered_by_type(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        s1 = MagicMock()
        s1.spec.type = "ClusterIP"
        s2 = MagicMock()
        s2.spec.type = "NodePort"
        mock_core_v1.list_namespaced_service.return_value.items = [s1, s2]
        assert svc_manager.list_services("default", service_type="NodePort") == [s2]

    def test_update_service(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc_manager.update_service("my-svc", "default", {"spec": {}})
        mock_core_v1.replace_namespaced_service.assert_called_once()

    def test_get_cluster_ip(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.spec.cluster_ip = "10.0.0.1"
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_cluster_ip("my-svc", "default") == "10.0.0.1"

    def test_get_cluster_ip_returns_empty_without_spec(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.spec = None
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_cluster_ip("my-svc", "default") == ""

    def test_get_external_ip_from_ip_field(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        ingress = MagicMock(ip="1.2.3.4")
        ingress.hostname = None
        svc = MagicMock()
        svc.status.load_balancer.ingress = [ingress]
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_external_ip("my-svc", "default") == "1.2.3.4"

    def test_get_external_ip_falls_back_to_hostname(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        ingress = MagicMock(ip=None, hostname="lb.example.com")
        svc = MagicMock()
        svc.status.load_balancer.ingress = [ingress]
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_external_ip("my-svc", "default") == "lb.example.com"

    def test_get_external_ip_none_without_load_balancer(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.status.load_balancer = None
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_external_ip("my-svc", "default") is None

    def test_get_external_ip_none_with_empty_ingress_list(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.status.load_balancer.ingress = []
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_external_ip("my-svc", "default") is None

    def test_wait_for_external_ip_returns_when_available(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        ingress = MagicMock(ip="1.2.3.4")
        svc = MagicMock()
        svc.status.load_balancer.ingress = [ingress]
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.wait_for_external_ip("my-svc", "default") == "1.2.3.4"

    def test_wait_for_external_ip_times_out(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.status.load_balancer.ingress = []
        mock_core_v1.read_namespaced_service.return_value = svc
        with patch("kube_orchestrator.resources.networking.service.time.sleep"):
            with pytest.raises(TimeoutError):
                svc_manager.wait_for_external_ip(
                    "my-svc", "default", timeout_seconds=0.05
                )

    def test_get_node_port_found(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        port = MagicMock(port=80, node_port=30080)
        svc = MagicMock()
        svc.spec.ports = [port]
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_node_port("my-svc", "default", 80) == 30080

    def test_get_node_port_not_found(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.spec.ports = []
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_node_port("my-svc", "default", 80) is None

    def test_get_endpoints(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_endpoints.return_value = "ep-obj"
        assert svc_manager.get_endpoints("my-svc", "default") == "ep-obj"

    def test_get_endpoints_raises_not_found(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_endpoints.side_effect = ApiException(status=404)
        with pytest.raises(ResourceNotFoundError):
            svc_manager.get_endpoints("my-svc", "default")

    def test_get_endpoints_raises_parsed_exception(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_endpoints.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            svc_manager.get_endpoints("my-svc", "default")

    def test_get_target_pods(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.spec.selector = {"app": "web"}
        mock_core_v1.read_namespaced_service.return_value = svc
        mock_core_v1.list_namespaced_pod.return_value.items = ["pod-a"]

        result = svc_manager.get_target_pods("my-svc", "default")

        assert result == ["pod-a"]
        kwargs = mock_core_v1.list_namespaced_pod.call_args.kwargs
        assert kwargs["label_selector"] == "app=web"

    def test_get_target_pods_returns_empty_without_selector(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.spec.selector = None
        mock_core_v1.read_namespaced_service.return_value = svc
        assert svc_manager.get_target_pods("my-svc", "default") == []

    def test_get_target_pods_raises_parsed_exception(
        self, svc_manager: ServiceManager, mock_core_v1: MagicMock
    ) -> None:
        svc = MagicMock()
        svc.spec.selector = {"app": "web"}
        mock_core_v1.read_namespaced_service.return_value = svc
        mock_core_v1.list_namespaced_pod.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            svc_manager.get_target_pods("my-svc", "default")

    def test_add_port(self, svc_manager: ServiceManager, mock_core_v1: MagicMock) -> None:
        existing_port = MagicMock(port=80, protocol="TCP")
        existing_port.name = "http"
        existing_port.target_port = 8080
        existing_port.node_port = 30080
        existing_port.app_protocol = "http"
        svc = MagicMock()
        svc.spec.ports = [existing_port]
        mock_core_v1.read_namespaced_service.return_value = svc

        svc_manager.add_port("my-svc", "default", {"port": 443, "protocol": "TCP"})

        call_kwargs = mock_core_v1.patch_namespaced_service.call_args.kwargs
        ports = call_kwargs["body"]["spec"]["ports"]
        assert len(ports) == 2
        assert ports[0]["nodePort"] == 30080
        assert ports[0]["appProtocol"] == "http"
        assert ports[1] == {"port": 443, "protocol": "TCP"}

    def test_kind_and_api_version(self, svc_manager: ServiceManager) -> None:
        assert svc_manager._kind() == "Service"
        assert svc_manager._api_version() == "v1"
