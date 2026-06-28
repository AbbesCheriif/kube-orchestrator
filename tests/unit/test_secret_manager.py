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
