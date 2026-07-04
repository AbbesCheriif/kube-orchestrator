"""Unit tests for EndpointsManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.networking.endpoints import EndpointsManager


@pytest.fixture
def ep_manager(mock_kube_client: MagicMock) -> EndpointsManager:
    return EndpointsManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestCreateEndpoints:
    def test_creates_with_full_subset(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        ep_manager.create_endpoints(
            "web",
            "default",
            subsets=[
                {
                    "addresses": [
                        {"ip": "10.0.0.1", "hostname": "web-1", "nodeName": "n1"}
                    ],
                    "notReadyAddresses": [{"ip": "10.0.0.2"}],
                    "ports": [
                        {
                            "port": 80,
                            "name": "http",
                            "protocol": "TCP",
                            "appProtocol": "http",
                        }
                    ],
                }
            ],
        )
        call_kwargs = mock_core_v1.create_namespaced_endpoints.call_args.kwargs
        subset = call_kwargs["body"]["subsets"][0]
        assert subset["addresses"][0]["hostname"] == "web-1"
        assert subset["notReadyAddresses"][0]["ip"] == "10.0.0.2"
        assert subset["ports"][0]["appProtocol"] == "http"

    def test_creates_with_minimal_subset(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        ep_manager.create_endpoints("web", "default", subsets=[{}])
        call_kwargs = mock_core_v1.create_namespaced_endpoints.call_args.kwargs
        assert call_kwargs["body"]["subsets"] == [{}]


@pytest.mark.unit
class TestGetListDelete:
    def test_get_endpoints(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_endpoints.return_value = "ep-obj"
        assert ep_manager.get_endpoints("web", "default") == "ep-obj"

    def test_list_endpoints(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_endpoints.return_value.items = ["a"]
        assert ep_manager.list_endpoints("default") == ["a"]

    def test_delete_endpoints(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        ep_manager.delete_endpoints("web", "default")
        mock_core_v1.delete_namespaced_endpoints.assert_called_once()


@pytest.mark.unit
class TestUpdateEndpoints:
    def test_preserves_resource_version(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        current = MagicMock()
        current.metadata.resource_version = "42"
        mock_core_v1.read_namespaced_endpoints.return_value = current

        ep_manager.update_endpoints("web", "default", subsets=[{}])

        call_kwargs = mock_core_v1.replace_namespaced_endpoints.call_args.kwargs
        assert call_kwargs["body"]["metadata"]["resourceVersion"] == "42"


@pytest.mark.unit
class TestAddAddress:
    def test_appends_to_existing_subset(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        addr = MagicMock()
        addr.ip = "10.0.0.1"
        addr.hostname = None
        addr.node_name = None
        subset = MagicMock()
        subset.addresses = [addr]
        subset.not_ready_addresses = None
        port = MagicMock(port=80, protocol="TCP", app_protocol=None)
        port.name = "http"
        subset.ports = [port]
        current = MagicMock()
        current.subsets = [subset]
        mock_core_v1.read_namespaced_endpoints.return_value = current

        ep_manager.add_address("web", "default", "10.0.0.2", 80)

        call_kwargs = mock_core_v1.replace_namespaced_endpoints.call_args.kwargs
        addresses = call_kwargs["body"]["subsets"][0]["addresses"]
        assert {"ip": "10.0.0.2"} in addresses

    def test_creates_new_subset_when_none_exist(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        current = MagicMock()
        current.subsets = []
        mock_core_v1.read_namespaced_endpoints.return_value = current

        ep_manager.add_address(
            "web",
            "default",
            "10.0.0.1",
            80,
            hostname="web-1",
            node_name="n1",
            target_ref={"kind": "Pod", "name": "web-1"},
        )

        call_kwargs = mock_core_v1.replace_namespaced_endpoints.call_args.kwargs
        subset = call_kwargs["body"]["subsets"][0]
        assert subset["addresses"][0]["hostname"] == "web-1"
        assert subset["addresses"][0]["targetRef"]["kind"] == "Pod"
        assert subset["ports"][0]["port"] == 80

    def test_appends_new_port_to_existing_subset(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        addr = MagicMock()
        addr.ip = "10.0.0.1"
        addr.hostname = None
        addr.node_name = None
        existing_port = MagicMock()
        existing_port.name = None
        existing_port.port = 80
        existing_port.protocol = "TCP"
        existing_port.app_protocol = None
        subset = MagicMock()
        subset.addresses = [addr]
        subset.not_ready_addresses = None
        subset.ports = [existing_port]
        current = MagicMock()
        current.subsets = [subset]
        mock_core_v1.read_namespaced_endpoints.return_value = current

        ep_manager.add_address("web", "default", "10.0.0.1", 443)

        call_kwargs = mock_core_v1.replace_namespaced_endpoints.call_args.kwargs
        ports = call_kwargs["body"]["subsets"][0]["ports"]
        assert {"port": 443, "protocol": "TCP"} in ports
        assert len(ports) == 2

    def test_does_not_duplicate_existing_port(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        subset = MagicMock()
        subset.addresses = []
        subset.not_ready_addresses = None
        port = MagicMock()
        port.name = None
        port.port = 80
        port.protocol = "TCP"
        port.app_protocol = None
        subset.ports = [port]
        current = MagicMock()
        current.subsets = [subset]
        mock_core_v1.read_namespaced_endpoints.return_value = current

        ep_manager.add_address("web", "default", "10.0.0.1", 80)

        call_kwargs = mock_core_v1.replace_namespaced_endpoints.call_args.kwargs
        assert len(call_kwargs["body"]["subsets"][0]["ports"]) == 1


@pytest.mark.unit
class TestRemoveAddress:
    def test_removes_matching_ip_from_addresses_and_not_ready(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        keep_addr = MagicMock()
        keep_addr.ip = "10.0.0.2"
        keep_addr.hostname = None
        keep_addr.node_name = None
        remove_addr = MagicMock()
        remove_addr.ip = "10.0.0.1"
        remove_addr.hostname = None
        remove_addr.node_name = None
        subset = MagicMock()
        subset.addresses = [keep_addr, remove_addr]
        subset.not_ready_addresses = [remove_addr]
        subset.ports = []
        current = MagicMock()
        current.subsets = [subset]
        mock_core_v1.read_namespaced_endpoints.return_value = current

        ep_manager.remove_address("web", "default", "10.0.0.1")

        call_kwargs = mock_core_v1.replace_namespaced_endpoints.call_args.kwargs
        remaining = call_kwargs["body"]["subsets"][0]["addresses"]
        assert remaining == [{"ip": "10.0.0.2"}]
        assert call_kwargs["body"]["subsets"][0]["notReadyAddresses"] == []


@pytest.mark.unit
class TestQueryHelpers:
    def test_get_ready_addresses(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        addr = MagicMock(ip="10.0.0.1")
        subset = MagicMock(addresses=[addr])
        ep = MagicMock(subsets=[subset])
        mock_core_v1.read_namespaced_endpoints.return_value = ep

        assert ep_manager.get_ready_addresses("web", "default") == ["10.0.0.1"]

    def test_get_ready_addresses_empty_without_subsets(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        ep = MagicMock(subsets=None)
        mock_core_v1.read_namespaced_endpoints.return_value = ep
        assert ep_manager.get_ready_addresses("web", "default") == []

    def test_get_not_ready_addresses(
        self, ep_manager: EndpointsManager, mock_core_v1: MagicMock
    ) -> None:
        addr = MagicMock(ip="10.0.0.9")
        subset = MagicMock(not_ready_addresses=[addr])
        ep = MagicMock(subsets=[subset])
        mock_core_v1.read_namespaced_endpoints.return_value = ep

        assert ep_manager.get_not_ready_addresses("web", "default") == ["10.0.0.9"]


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, ep_manager: EndpointsManager) -> None:
        assert ep_manager._kind() == "Endpoints"
        assert ep_manager._api_version() == "v1"
