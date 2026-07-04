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

    def test_create_configmap_with_binary_data(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        import base64

        cm_manager.create_configmap(
            name="bin-config", namespace="default", binary_data={"blob": b"raw"}
        )
        call_body = mock_core_v1.create_namespaced_config_map.call_args.kwargs["body"]
        assert call_body.binary_data == {
            "blob": base64.b64encode(b"raw").decode("ascii")
        }

    def test_create_from_file(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock, tmp_path
    ) -> None:
        file_path = tmp_path / "app.conf"
        file_path.write_text("key=value")
        cm_manager.create_from_file(
            "from-file", "default", [str(file_path)], key_prefix="cfg-"
        )
        call_body = mock_core_v1.create_namespaced_config_map.call_args.kwargs["body"]
        assert call_body.data == {"cfg-app.conf": "key=value"}

    def test_create_from_directory(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock, tmp_path
    ) -> None:
        (tmp_path / "a.txt").write_text("A")
        (tmp_path / "b.txt").write_text("B")
        cm_manager.create_from_directory("from-dir", "default", str(tmp_path))
        call_body = mock_core_v1.create_namespaced_config_map.call_args.kwargs["body"]
        assert call_body.data == {"a.txt": "A", "b.txt": "B"}

    def test_create_from_directory_recursive(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock, tmp_path
    ) -> None:
        (tmp_path / "top.txt").write_text("TOP")
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "inner.txt").write_text("INNER")

        # The recursive call re-invokes create_configmap for the nested dir,
        # so the mock must echo back the real body it was called with instead
        # of a bare MagicMock, otherwise `sub.data` isn't a real dict to merge.
        mock_core_v1.create_namespaced_config_map.side_effect = lambda **kwargs: kwargs[
            "body"
        ]

        cm_manager.create_from_directory(
            "from-dir", "default", str(tmp_path), recursive=True
        )
        call_body = mock_core_v1.create_namespaced_config_map.call_args.kwargs["body"]
        assert call_body.data == {"top.txt": "TOP", "inner.txt": "INNER"}

    def test_get_configmap(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_config_map.return_value = "cm-obj"
        assert cm_manager.get_configmap("my-config", "default") == "cm-obj"

    def test_list_configmaps(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_config_map.return_value.items = ["a", "b"]
        assert cm_manager.list_configmaps("default") == ["a", "b"]

    def test_update_configmap_with_binary_data(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        mock_core_v1.read_namespaced_config_map.return_value = existing
        cm_manager.update_configmap(
            "my-config", "default", {"k": "v"}, binary_data={"b": "YQ=="}
        )
        assert existing.data == {"k": "v"}
        assert existing.binary_data == {"b": "YQ=="}

    def test_delete_key_removes_existing_key(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.data = {"key1": "value1"}
        mock_core_v1.read_namespaced_config_map.return_value = existing
        cm_manager.delete_key("my-config", "default", "key1")
        assert "key1" not in existing.data

    def test_delete_key_missing_key_is_noop(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.data = {}
        mock_core_v1.read_namespaced_config_map.return_value = existing
        cm_manager.delete_key("my-config", "default", "missing")
        mock_core_v1.replace_namespaced_config_map.assert_called_once()

    def test_get_value(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.data = {"key1": "value1"}
        mock_core_v1.read_namespaced_config_map.return_value = existing
        assert cm_manager.get_value("my-config", "default", "key1") == "value1"

    def test_set_immutable(
        self, cm_manager: ConfigMapManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        mock_core_v1.read_namespaced_config_map.return_value = existing
        cm_manager.set_immutable("my-config", "default", True)
        assert existing.immutable is True

    def test_build_volume_spec_with_items_and_mode(
        self, cm_manager: ConfigMapManager
    ) -> None:
        spec = cm_manager.build_volume_spec(
            "my-config", items=[{"key": "a"}], default_mode=0o644
        )
        assert spec["configMap"]["items"] == [{"key": "a"}]
        assert spec["configMap"]["defaultMode"] == 0o644

    def test_build_env_from_spec_with_prefix(
        self, cm_manager: ConfigMapManager
    ) -> None:
        spec = cm_manager.build_env_from_spec("my-config", prefix="APP_")
        assert spec["prefix"] == "APP_"

    def test_kind_and_api_version(self, cm_manager: ConfigMapManager) -> None:
        assert cm_manager._kind() == "ConfigMap"
        assert cm_manager._api_version() == "v1"
        assert cm_manager._resource_name() == "config_map"
