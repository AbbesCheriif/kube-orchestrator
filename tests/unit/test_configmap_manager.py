"""Unit tests for ConfigMapManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.storage.configmap import ConfigMapManager


@pytest.fixture
def cm_manager(mock_kube_client: MagicMock) -> ConfigMapManager:
    return ConfigMapManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestConfigMapManager:
    def test_create_configmap(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_config_map.return_value = MagicMock()
        cm_manager.create_configmap(
            name="my-config",
            namespace="default",
            data={"key1": "value1", "key2": "value2"},
        )
        mock_core_v1.create_namespaced_config_map.assert_called_once()

    def test_set_key(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        mock_cm = MagicMock()
        mock_cm.data = {"existing": "val"}
        mock_core_v1.read_namespaced_config_map.return_value = mock_cm
        mock_core_v1.replace_namespaced_config_map.return_value = mock_cm
        cm_manager.set_key("my-config", "default", "new-key", "new-value")
        mock_core_v1.replace_namespaced_config_map.assert_called_once()

    def test_build_volume_spec(self, cm_manager: ConfigMapManager) -> None:
        spec = cm_manager.build_volume_spec("my-config")
        assert spec["configMap"]["name"] == "my-config"

    def test_build_env_from_spec(self, cm_manager: ConfigMapManager) -> None:
        spec = cm_manager.build_env_from_spec("my-config")
        assert spec["configMapRef"]["name"] == "my-config"

    def test_build_env_key_ref(self, cm_manager: ConfigMapManager) -> None:
        spec = cm_manager.build_env_key_ref("my-config", "DB_URL")
        assert spec["valueFrom"]["configMapKeyRef"]["name"] == "my-config"
        assert spec["valueFrom"]["configMapKeyRef"]["key"] == "DB_URL"

    def test_delete_configmap(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        cm_manager.delete_configmap("my-config", "default")
        mock_core_v1.delete_namespaced_config_map.assert_called_once()
