"""Unit tests for IngressManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.networking.ingress import IngressManager


@pytest.fixture
def ing_manager(mock_kube_client: MagicMock) -> IngressManager:
    return IngressManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestIngressManager:
    def test_create_ingress(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        mock_networking_v1.create_namespaced_ingress.return_value = MagicMock()
        ing_manager.create_ingress(
            name="my-ingress",
            namespace="default",
            rules=[
                {
                    "host": "example.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": "my-svc",
                                        "port": {"number": 80},
                                    }
                                },
                            }
                        ]
                    },
                }
            ],
        )
        mock_networking_v1.create_namespaced_ingress.assert_called_once()

    def test_add_tls(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        mock_ing = MagicMock()
        mock_ing.spec.tls = []
        mock_networking_v1.read_namespaced_ingress.return_value = mock_ing
        mock_networking_v1.patch_namespaced_ingress.return_value = mock_ing
        ing_manager.add_tls(
            "my-ingress", "default", hosts=["example.com"], secret_name="tls-secret"
        )
        mock_networking_v1.patch_namespaced_ingress.assert_called_once()

    def test_delete_ingress(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        ing_manager.delete_ingress("my-ingress", "default")
        mock_networking_v1.delete_namespaced_ingress.assert_called_once()
