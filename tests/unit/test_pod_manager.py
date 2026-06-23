"""Unit tests for PodManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.workloads.pod import PodManager


@pytest.fixture
def pod_manager(mock_kube_client: MagicMock) -> PodManager:
    return PodManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestPodManagerCreate:
    def test_create_pod_from_manifest(
        self,
        pod_manager: PodManager,
        mock_core_v1: MagicMock,
        sample_pod_manifest: dict,
    ) -> None:
        mock_core_v1.create_namespaced_pod.return_value = MagicMock(
            metadata=MagicMock(name="test-pod")
        )
        result = pod_manager.create_pod(
            manifest=sample_pod_manifest, namespace="default"
        )
        mock_core_v1.create_namespaced_pod.assert_called_once()
        assert result is not None

    def test_get_pod(self, pod_manager: PodManager, mock_core_v1: MagicMock) -> None:
        mock_pod = MagicMock()
        mock_core_v1.read_namespaced_pod.return_value = mock_pod
        result = pod_manager.get_pod("test-pod", "default")
        mock_core_v1.read_namespaced_pod.assert_called_once_with(
            name="test-pod", namespace="default"
        )
        assert result is mock_pod

    def test_list_pods(self, pod_manager: PodManager, mock_core_v1: MagicMock) -> None:
        mock_list = MagicMock()
        mock_list.items = [MagicMock(), MagicMock()]
        mock_core_v1.list_namespaced_pod.return_value = mock_list
        result = pod_manager.list_pods("default")
        assert len(result) == 2

    def test_delete_pod(self, pod_manager: PodManager, mock_core_v1: MagicMock) -> None:
        pod_manager.delete_pod("test-pod", "default")
        mock_core_v1.delete_namespaced_pod.assert_called_once()

    def test_get_phase(self, pod_manager: PodManager, mock_core_v1: MagicMock) -> None:
        mock_pod = MagicMock()
        mock_pod.status.phase = "Running"
        mock_core_v1.read_namespaced_pod.return_value = mock_pod
        phase = pod_manager.get_phase("test-pod", "default")
        assert phase == "Running"

    def test_is_ready_true(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_pod = MagicMock()
        condition = MagicMock()
        condition.type = "Ready"
        condition.status = "True"
        mock_pod.status.conditions = [condition]
        mock_core_v1.read_namespaced_pod.return_value = mock_pod
        assert pod_manager.is_ready("test-pod", "default") is True

    def test_is_ready_false_when_no_conditions(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_pod = MagicMock()
        mock_pod.status.conditions = []
        mock_core_v1.read_namespaced_pod.return_value = mock_pod
        assert pod_manager.is_ready("test-pod", "default") is False
