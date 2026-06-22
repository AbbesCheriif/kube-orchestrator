"""Unit tests for DaemonSetManager."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.workloads.daemonset import DaemonSetManager


@pytest.fixture
def ds_manager(mock_kube_client: MagicMock) -> DaemonSetManager:
    return DaemonSetManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestDaemonSetManager:
    def test_create_daemonset(self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock) -> None:
        mock_apps_v1.create_namespaced_daemon_set.return_value = MagicMock()
        ds_manager.create_daemonset(
            name="fluentd",
            namespace="kube-system",
            selector={"matchLabels": {"app": "fluentd"}},
            pod_template={
                "metadata": {"labels": {"app": "fluentd"}},
                "spec": {"containers": [{"name": "fluentd", "image": "fluentd:latest"}]},
            },
        )
        mock_apps_v1.create_namespaced_daemon_set.assert_called_once()

    def test_update_image(self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock) -> None:
        mock_ds = MagicMock()
        mock_apps_v1.read_namespaced_daemon_set.return_value = mock_ds
        mock_apps_v1.replace_namespaced_daemon_set.return_value = mock_ds
        ds_manager.update_image("fluentd", "kube-system", "fluentd", "fluentd:v2")
        mock_apps_v1.replace_namespaced_daemon_set.assert_called_once()

    def test_set_node_selector(self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock) -> None:
        mock_ds = MagicMock()
        mock_apps_v1.read_namespaced_daemon_set.return_value = mock_ds
        mock_apps_v1.patch_namespaced_daemon_set.return_value = mock_ds
        ds_manager.set_node_selector("fluentd", "kube-system", {"node-role": "worker"})
        mock_apps_v1.patch_namespaced_daemon_set.assert_called_once()
