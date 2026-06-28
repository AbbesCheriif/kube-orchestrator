"""Unit tests for ServiceManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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
