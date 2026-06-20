"""Unit tests for StatefulSetManager."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.workloads.statefulset import StatefulSetManager


@pytest.fixture
def ss_manager(mock_kube_client: MagicMock) -> StatefulSetManager:
    return StatefulSetManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestStatefulSetManager:
    def test_create_statefulset(self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock) -> None:
        mock_apps_v1.create_namespaced_stateful_set.return_value = MagicMock()
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": "my-ss", "namespace": "default"},
            "spec": {
                "serviceName": "my-ss",
                "replicas": 3,
                "selector": {"matchLabels": {"app": "my-ss"}},
                "template": {"metadata": {"labels": {"app": "my-ss"}}, "spec": {"containers": [{"name": "app", "image": "nginx"}]}},
                "volumeClaimTemplates": [
                    {
                        "metadata": {"name": "data"},
                        "spec": {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": "10Gi"}}},
                    }
                ],
            },
        }
        ss_manager.create_statefulset(manifest=manifest, namespace="default")
        mock_apps_v1.create_namespaced_stateful_set.assert_called_once()

    def test_scale(self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock) -> None:
        mock_scale = MagicMock()
        mock_apps_v1.read_namespaced_stateful_set_scale.return_value = mock_scale
        mock_apps_v1.replace_namespaced_stateful_set_scale.return_value = mock_scale
        ss_manager.scale("my-ss", "default", replicas=2)
        mock_apps_v1.replace_namespaced_stateful_set_scale.assert_called_once()

    def test_set_partition_update(self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock) -> None:
        mock_ss = MagicMock()
        mock_apps_v1.read_namespaced_stateful_set.return_value = mock_ss
        mock_apps_v1.patch_namespaced_stateful_set.return_value = mock_ss
        ss_manager.set_partition_update("my-ss", "default", partition=2)
        mock_apps_v1.patch_namespaced_stateful_set.assert_called_once()
