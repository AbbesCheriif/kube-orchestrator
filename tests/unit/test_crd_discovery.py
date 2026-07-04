"""Unit tests for kube_orchestrator.crd.discovery."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError, AuthorizationError
from kube_orchestrator.crd.discovery import APIDiscovery


@pytest.fixture
def discovery(mock_kube_client: MagicMock) -> APIDiscovery:
    return APIDiscovery(kube_client=mock_kube_client)


@pytest.mark.unit
class TestListApiGroups:
    def test_returns_group_names(
        self, discovery: APIDiscovery, mock_kube_client: MagicMock
    ) -> None:
        group_a = MagicMock()
        group_a.name = "apps"
        group_b = MagicMock()
        group_b.name = "batch"
        with patch("kubernetes.client.ApisApi") as apis_api_cls:
            apis_api_cls.return_value.get_api_versions.return_value.groups = [
                group_a,
                group_b,
            ]
            result = discovery.list_api_groups()

        assert result == ["apps", "batch"]
        apis_api_cls.assert_called_once_with(mock_kube_client._api_client)

    def test_raises_parsed_exception_on_api_error(
        self, discovery: APIDiscovery
    ) -> None:
        with patch("kubernetes.client.ApisApi") as apis_api_cls:
            apis_api_cls.return_value.get_api_versions.side_effect = ApiException(
                status=500, reason="boom"
            )
            with pytest.raises(APIError):
                discovery.list_api_groups()


@pytest.mark.unit
class TestListResourcesForGroup:
    def test_parses_resources_from_response_body(
        self, discovery: APIDiscovery, mock_kube_client: MagicMock
    ) -> None:
        payload = json.dumps({"resources": [{"name": "deployments"}]}).encode()
        response = MagicMock()
        response.data = payload
        mock_kube_client._api_client.call_api.return_value = response

        result = discovery.list_resources_for_group("apps", "v1")

        assert result == [{"name": "deployments"}]

    def test_returns_empty_list_on_tuple_response(
        self, discovery: APIDiscovery, mock_kube_client: MagicMock
    ) -> None:
        payload = json.dumps({"resources": []}).encode()
        response_part = MagicMock()
        response_part.data = payload
        mock_kube_client._api_client.call_api.return_value = (response_part,)

        result = discovery.list_resources_for_group("apps", "v1")

        assert result == []

    def test_returns_empty_list_on_error(
        self, discovery: APIDiscovery, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client._api_client.call_api.side_effect = ApiException(status=404)
        assert discovery.list_resources_for_group("apps", "v1") == []


@pytest.mark.unit
class TestDiscoverAllCrds:
    def test_returns_summaries_for_each_crd(
        self, discovery: APIDiscovery, mock_kube_client: MagicMock
    ) -> None:
        crd = MagicMock()
        crd.metadata.name = "foos.example.com"
        crd.spec.group = "example.com"
        version = MagicMock()
        version.name = "v1"
        crd.spec.versions = [version]
        crd.spec.names.plural = "foos"
        crd.spec.names.kind = "Foo"
        crd.spec.scope = "Namespaced"
        mock_kube_client.api_extensions_v1.list_custom_resource_definition.return_value.items = [
            crd
        ]

        result = discovery.discover_all_crds()

        assert result == [
            {
                "name": "foos.example.com",
                "group": "example.com",
                "versions": ["v1"],
                "plural": "foos",
                "kind": "Foo",
                "scope": "Namespaced",
            }
        ]

    def test_raises_parsed_exception_on_api_error(
        self, discovery: APIDiscovery, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.api_extensions_v1.list_custom_resource_definition.side_effect = ApiException(
            status=403, reason="forbidden"
        )
        with pytest.raises(AuthorizationError):
            discovery.discover_all_crds()


@pytest.mark.unit
class TestBuildDynamicClient:
    def test_returns_configured_custom_object_manager(
        self, discovery: APIDiscovery, mock_kube_client: MagicMock
    ) -> None:
        manager = discovery.build_dynamic_client("example.com", "v1", "foos")
        assert manager.group == "example.com"
        assert manager.version == "v1"
        assert manager.plural == "foos"
        assert manager.client is mock_kube_client
