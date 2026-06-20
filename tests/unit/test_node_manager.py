"""Unit tests for NodeManager."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.resources.cluster.node import NodeManager


@pytest.fixture
def node_manager(mock_kube_client: MagicMock) -> NodeManager:
    return NodeManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestNodeManagerCordonUncordon:
    def test_cordon(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_node = MagicMock()
        mock_node.spec.unschedulable = False
        mock_core_v1.read_node.return_value = mock_node
        mock_core_v1.patch_node.return_value = mock_node
        node_manager.cordon("worker-1")
        mock_core_v1.patch_node.assert_called_once()
        call_body = mock_core_v1.patch_node.call_args[0][1]
        assert call_body["spec"]["unschedulable"] is True

    def test_uncordon(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_node = MagicMock()
        mock_node.spec.unschedulable = True
        mock_core_v1.read_node.return_value = mock_node
        mock_core_v1.patch_node.return_value = mock_node
        node_manager.uncordon("worker-1")
        call_body = mock_core_v1.patch_node.call_args[0][1]
        assert call_body["spec"]["unschedulable"] is False

    def test_is_schedulable_true(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_node = MagicMock()
        mock_node.spec.unschedulable = None
        mock_core_v1.read_node.return_value = mock_node
        assert node_manager.is_schedulable("worker-1") is True

    def test_is_schedulable_false(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_node = MagicMock()
        mock_node.spec.unschedulable = True
        mock_core_v1.read_node.return_value = mock_node
        assert node_manager.is_schedulable("worker-1") is False


@pytest.mark.unit
class TestNodeManagerTaints:
    def test_add_taint(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_node = MagicMock()
        mock_node.spec.taints = []
        mock_core_v1.read_node.return_value = mock_node
        mock_core_v1.patch_node.return_value = mock_node
        node_manager.add_taint("worker-1", "dedicated", "gpu", "NoSchedule")
        mock_core_v1.patch_node.assert_called_once()

    def test_remove_taint(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        existing_taint = MagicMock()
        existing_taint.key = "dedicated"
        existing_taint.effect = "NoSchedule"
        mock_node = MagicMock()
        mock_node.spec.taints = [existing_taint]
        mock_core_v1.read_node.return_value = mock_node
        mock_core_v1.patch_node.return_value = mock_node
        node_manager.remove_taint("worker-1", "dedicated")
        call_body = mock_core_v1.patch_node.call_args[0][1]
        assert call_body["spec"]["taints"] == []

    def test_has_taint_true(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        taint = MagicMock()
        taint.key = "dedicated"
        taint.effect = "NoSchedule"
        mock_node = MagicMock()
        mock_node.spec.taints = [taint]
        mock_core_v1.read_node.return_value = mock_node
        assert node_manager.has_taint("worker-1", "dedicated") is True

    def test_has_taint_false(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_node = MagicMock()
        mock_node.spec.taints = []
        mock_core_v1.read_node.return_value = mock_node
        assert node_manager.has_taint("worker-1", "missing-key") is False
