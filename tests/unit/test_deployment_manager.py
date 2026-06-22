"""Unit tests for DeploymentManager."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.workloads.deployment import DeploymentManager


@pytest.fixture
def dep_manager(mock_kube_client: MagicMock) -> DeploymentManager:
    return DeploymentManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestDeploymentManagerCreate:
    def test_create_from_manifest(self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock, sample_deployment_manifest: dict) -> None:
        mock_apps_v1.create_namespaced_deployment.return_value = MagicMock()
        result = dep_manager.create_deployment(manifest=sample_deployment_manifest, namespace="default")
        mock_apps_v1.create_namespaced_deployment.assert_called_once()

    def test_get_deployment(self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock) -> None:
        mock_dep = MagicMock()
        mock_apps_v1.read_namespaced_deployment.return_value = mock_dep
        result = dep_manager.get_deployment("test-deploy", "default")
        assert result is mock_dep

    def test_list_deployments(self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock) -> None:
        mock_list = MagicMock()
        mock_list.items = [MagicMock(), MagicMock(), MagicMock()]
        mock_apps_v1.list_namespaced_deployment.return_value = mock_list
        result = dep_manager.list_deployments("default")
        assert len(result) == 3

    def test_scale(self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock) -> None:
        mock_scale = MagicMock()
        mock_apps_v1.patch_namespaced_deployment_scale.return_value = mock_scale
        dep_manager.scale("test-deploy", "default", replicas=5)
        mock_apps_v1.patch_namespaced_deployment_scale.assert_called_once()

    def test_delete_deployment(self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock) -> None:
        dep_manager.delete_deployment("test-deploy", "default")
        mock_apps_v1.delete_namespaced_deployment.assert_called_once()

    def test_is_available_true(self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock) -> None:
        mock_dep = MagicMock()
        mock_condition = MagicMock()
        mock_condition.type = "Available"
        mock_condition.status = "True"
        mock_dep.status.conditions = [mock_condition]
        mock_apps_v1.read_namespaced_deployment.return_value = mock_dep
        assert dep_manager.is_available("test-deploy", "default") is True

    def test_is_available_false(self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock) -> None:
        mock_dep = MagicMock()
        mock_dep.status.conditions = []
        mock_apps_v1.read_namespaced_deployment.return_value = mock_dep
        assert dep_manager.is_available("test-deploy", "default") is False

    def test_pause_rollout(self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock) -> None:
        mock_dep = MagicMock()
        mock_dep.spec.paused = False
        mock_apps_v1.read_namespaced_deployment.return_value = mock_dep
        mock_apps_v1.patch_namespaced_deployment.return_value = mock_dep
        dep_manager.pause_rollout("test-deploy", "default")
        mock_apps_v1.patch_namespaced_deployment.assert_called_once()
