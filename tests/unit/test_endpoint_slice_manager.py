"""Unit tests for EndpointSliceManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.networking.endpoint_slice import EndpointSliceManager


@pytest.fixture
def es_manager(mock_kube_client: MagicMock) -> EndpointSliceManager:
    return EndpointSliceManager(kube_client=mock_kube_client)


def _endpoint(
    addresses: list[str], ready: bool | None = True, node: str | None = None, zone: str | None = None
) -> MagicMock:
    ep = MagicMock()
    ep.addresses = addresses
    ep.conditions.ready = ready
    ep.node_name = node
    ep.zone = zone
    return ep


@pytest.mark.unit
class TestListSlicesForService:
    def test_uses_service_name_label_selector(
        self, es_manager: EndpointSliceManager, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.discovery_v1.list_namespaced_endpoint_slice.return_value.items = []
        es_manager.list_slices_for_service("web", "default")
        kwargs = (
            mock_kube_client.discovery_v1.list_namespaced_endpoint_slice.call_args.kwargs
        )
        assert kwargs["label_selector"] == "kubernetes.io/service-name=web"


@pytest.mark.unit
class TestGetAllReadyEndpoints:
    def test_collects_ready_addresses_only(
        self, es_manager: EndpointSliceManager, mock_kube_client: MagicMock
    ) -> None:
        slc = MagicMock()
        slc.endpoints = [
            _endpoint(["10.0.0.1"], ready=True),
            _endpoint(["10.0.0.2"], ready=False),
        ]
        mock_kube_client.discovery_v1.list_namespaced_endpoint_slice.return_value.items = [
            slc
        ]

        result = es_manager.get_all_ready_endpoints("web", "default")

        assert result == ["10.0.0.1"]

    def test_treats_missing_condition_as_ready(
        self, es_manager: EndpointSliceManager, mock_kube_client: MagicMock
    ) -> None:
        slc = MagicMock()
        slc.endpoints = [_endpoint(["10.0.0.1"], ready=None)]
        mock_kube_client.discovery_v1.list_namespaced_endpoint_slice.return_value.items = [
            slc
        ]

        assert es_manager.get_all_ready_endpoints("web", "default") == ["10.0.0.1"]


@pytest.mark.unit
class TestGetEndpointsByNode:
    def test_groups_by_node_name(
        self, es_manager: EndpointSliceManager, mock_kube_client: MagicMock
    ) -> None:
        slc = MagicMock()
        slc.endpoints = [
            _endpoint(["10.0.0.1"], node="node-a"),
            _endpoint(["10.0.0.2"], node="node-a"),
            _endpoint(["10.0.0.3"], node="node-b"),
            _endpoint(["10.0.0.4"], ready=False, node="node-c"),
        ]
        mock_kube_client.discovery_v1.list_namespaced_endpoint_slice.return_value.items = [
            slc
        ]

        result = es_manager.get_endpoints_by_node("web", "default")

        assert result == {
            "node-a": ["10.0.0.1", "10.0.0.2"],
            "node-b": ["10.0.0.3"],
        }

    def test_uses_unknown_placeholder_without_node_name(
        self, es_manager: EndpointSliceManager, mock_kube_client: MagicMock
    ) -> None:
        slc = MagicMock()
        slc.endpoints = [_endpoint(["10.0.0.1"], node=None)]
        mock_kube_client.discovery_v1.list_namespaced_endpoint_slice.return_value.items = [
            slc
        ]

        result = es_manager.get_endpoints_by_node("web", "default")
        assert result == {"__unknown__": ["10.0.0.1"]}


@pytest.mark.unit
class TestGetEndpointsByZone:
    def test_groups_by_zone(
        self, es_manager: EndpointSliceManager, mock_kube_client: MagicMock
    ) -> None:
        slc = MagicMock()
        slc.endpoints = [
            _endpoint(["10.0.0.1"], zone="us-east-1a"),
            _endpoint(["10.0.0.2"], ready=False, zone="us-east-1b"),
        ]
        mock_kube_client.discovery_v1.list_namespaced_endpoint_slice.return_value.items = [
            slc
        ]

        result = es_manager.get_endpoints_by_zone("web", "default")
        assert result == {"us-east-1a": ["10.0.0.1"]}

    def test_uses_unknown_placeholder_without_zone(
        self, es_manager: EndpointSliceManager, mock_kube_client: MagicMock
    ) -> None:
        slc = MagicMock()
        slc.endpoints = [_endpoint(["10.0.0.1"], zone=None)]
        mock_kube_client.discovery_v1.list_namespaced_endpoint_slice.return_value.items = [
            slc
        ]

        result = es_manager.get_endpoints_by_zone("web", "default")
        assert result == {"__unknown__": ["10.0.0.1"]}


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, es_manager: EndpointSliceManager) -> None:
        assert es_manager._kind() == "EndpointSlice"
        assert es_manager._api_version() == "discovery.k8s.io/v1"
        assert es_manager._resource_name() == "endpoint_slice"
