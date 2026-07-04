"""Unit tests for SecretManager."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.storage.secret import SecretManager


@pytest.fixture
def secret_manager(mock_kube_client: MagicMock) -> SecretManager:
    return SecretManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestSecretManager:
    def test_create_opaque_secret(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_secret.return_value = MagicMock()
        secret_manager.create_opaque(
            name="my-secret",
            namespace="default",
            data={"password": "s3cr3t"},
        )
        mock_core_v1.create_namespaced_secret.assert_called_once()
        call_body = mock_core_v1.create_namespaced_secret.call_args.kwargs["body"]
        assert call_body.type == "Opaque"

    def test_create_docker_registry_secret(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_secret.return_value = MagicMock()
        secret_manager.create_docker_registry_secret(
            name="registry-cred",
            namespace="default",
            server="registry.example.com",
            username="user",
            password="pass",
        )
        mock_core_v1.create_namespaced_secret.assert_called_once()
        call_body = mock_core_v1.create_namespaced_secret.call_args.kwargs["body"]
        assert call_body.type == "kubernetes.io/dockerconfigjson"

    def test_get_decoded_value(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        encoded = base64.b64encode(b"my-password").decode()
        mock_secret = MagicMock()
        mock_secret.data = {"password": encoded}
        mock_core_v1.read_namespaced_secret.return_value = mock_secret
        result = secret_manager.get_decoded_value("my-secret", "default", "password")
        assert result == "my-password"

    def test_create_tls_secret(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock, tmp_path
    ) -> None:
        cert_file = tmp_path / "tls.crt"
        key_file = tmp_path / "tls.key"
        cert_file.write_text("CERT_DATA")
        key_file.write_text("KEY_DATA")
        mock_core_v1.create_namespaced_secret.return_value = MagicMock()
        secret_manager.create_tls_secret(
            "tls-secret", "default", str(cert_file), str(key_file)
        )
        call_body = mock_core_v1.create_namespaced_secret.call_args.kwargs["body"]
        assert call_body.type == "kubernetes.io/tls"

    def test_delete_secret(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        secret_manager.delete_secret("my-secret", "default")
        mock_core_v1.delete_namespaced_secret.assert_called_once()

    def test_create_secret_with_binary_data(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        secret_manager.create_secret(
            name="bin-secret", namespace="default", data={"blob": b"raw-bytes"}
        )
        call_body = mock_core_v1.create_namespaced_secret.call_args.kwargs["body"]
        assert call_body.data == {"blob": base64.b64encode(b"raw-bytes").decode()}

    def test_create_basic_auth_secret(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        secret_manager.create_basic_auth_secret("basic", "default", "bob", "pw")
        call_body = mock_core_v1.create_namespaced_secret.call_args.kwargs["body"]
        assert call_body.type == "kubernetes.io/basic-auth"
        assert call_body.string_data == {"username": "bob", "password": "pw"}

    def test_create_ssh_auth_secret(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock, tmp_path
    ) -> None:
        key_file = tmp_path / "id_rsa"
        key_file.write_text("PRIVATE_KEY")
        secret_manager.create_ssh_auth_secret("ssh", "default", str(key_file))
        call_body = mock_core_v1.create_namespaced_secret.call_args.kwargs["body"]
        assert call_body.type == "kubernetes.io/ssh-auth"

    def test_create_docker_registry_secret_with_email(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        secret_manager.create_docker_registry_secret(
            name="registry-cred",
            namespace="default",
            server="registry.example.com",
            username="user",
            password="pass",
            email="user@example.com",
        )
        call_body = mock_core_v1.create_namespaced_secret.call_args.kwargs["body"]
        assert "email" in call_body.string_data[".dockerconfigjson"]

    def test_get_secret(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_secret.return_value = "secret-obj"
        assert secret_manager.get_secret("my-secret", "default") == "secret-obj"

    def test_list_secrets_without_filter(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        s1 = MagicMock(type="Opaque")
        s2 = MagicMock(type="kubernetes.io/tls")
        mock_core_v1.list_namespaced_secret.return_value.items = [s1, s2]
        assert secret_manager.list_secrets("default") == [s1, s2]

    def test_list_secrets_filtered_by_type(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        s1 = MagicMock(type="Opaque")
        s2 = MagicMock(type="kubernetes.io/tls")
        mock_core_v1.list_namespaced_secret.return_value.items = [s1, s2]
        assert secret_manager.list_secrets("default", secret_type="Opaque") == [s1]

    def test_update_secret(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_secret.return_value = MagicMock()
        secret_manager.update_secret("my-secret", "default", {"k": "v"})
        mock_core_v1.replace_namespaced_secret.assert_called_once()

    def test_set_key_encodes_value(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.data = {}
        mock_core_v1.read_namespaced_secret.return_value = existing
        secret_manager.set_key("my-secret", "default", "token", "abc")
        assert existing.data["token"] == base64.b64encode(b"abc").decode()

    def test_delete_key_removes_existing_key(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.data = {"token": "xyz"}
        mock_core_v1.read_namespaced_secret.return_value = existing
        secret_manager.delete_key("my-secret", "default", "token")
        assert "token" not in existing.data

    def test_delete_key_missing_key_is_noop(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.data = {}
        mock_core_v1.read_namespaced_secret.return_value = existing
        secret_manager.delete_key("my-secret", "default", "missing")
        mock_core_v1.replace_namespaced_secret.assert_called_once()

    def test_set_immutable(
        self, secret_manager: SecretManager, mock_core_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        mock_core_v1.read_namespaced_secret.return_value = existing
        secret_manager.set_immutable("my-secret", "default", True)
        assert existing.immutable is True

    def test_build_volume_spec(self, secret_manager: SecretManager) -> None:
        spec = secret_manager.build_volume_spec(
            "my-secret", items=[{"key": "a"}], default_mode=0o400
        )
        assert spec["secret"]["secretName"] == "my-secret"
        assert spec["secret"]["items"] == [{"key": "a"}]
        assert spec["secret"]["defaultMode"] == 0o400

    def test_build_env_from_spec(self, secret_manager: SecretManager) -> None:
        spec = secret_manager.build_env_from_spec("my-secret", prefix="APP_")
        assert spec["secretRef"]["name"] == "my-secret"
        assert spec["prefix"] == "APP_"

    def test_build_env_key_ref(self, secret_manager: SecretManager) -> None:
        spec = secret_manager.build_env_key_ref("my-secret", "TOKEN")
        assert spec["valueFrom"]["secretKeyRef"]["name"] == "my-secret"
        assert spec["valueFrom"]["secretKeyRef"]["key"] == "TOKEN"

    def test_kind_and_api_version(self, secret_manager: SecretManager) -> None:
        assert secret_manager._kind() == "Secret"
        assert secret_manager._api_version() == "v1"
