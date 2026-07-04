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

    def test_create_ingress_with_class_default_backend_and_tls(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        ing_manager.create_ingress(
            "my-ingress",
            "default",
            ingress_class_name="nginx",
            default_backend={"service": {"name": "default-svc", "port": {"number": 80}}},
            tls=[{"hosts": ["example.com"], "secretName": "tls-secret"}],
        )
        call_kwargs = mock_networking_v1.create_namespaced_ingress.call_args.kwargs
        spec = call_kwargs["body"]["spec"]
        assert spec["ingressClassName"] == "nginx"
        assert spec["defaultBackend"]["service"]["name"] == "default-svc"
        assert spec["tls"][0]["secretName"] == "tls-secret"

    def test_create_ingress_with_resource_backend(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        ing_manager.create_ingress(
            "my-ingress",
            "default",
            rules=[
                {
                    "host": "static.example.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/assets",
                                "backend": {
                                    "resource": {"apiGroup": "k8s.io", "kind": "StorageBucket", "name": "assets"}
                                },
                            }
                        ]
                    },
                }
            ],
        )
        call_kwargs = mock_networking_v1.create_namespaced_ingress.call_args.kwargs
        path = call_kwargs["body"]["spec"]["rules"][0]["http"]["paths"][0]
        assert path["backend"]["resource"]["kind"] == "StorageBucket"

    def test_get_ingress(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        mock_networking_v1.read_namespaced_ingress.return_value = "ing-obj"
        assert ing_manager.get_ingress("my-ingress", "default") == "ing-obj"

    def test_list_ingresses(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        mock_networking_v1.list_namespaced_ingress.return_value.items = ["a"]
        assert ing_manager.list_ingresses("default") == ["a"]

    def test_add_rule_appends_to_existing(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        existing_rule = MagicMock()
        existing_rule.host = "old.example.com"
        existing_rule.http = None
        ing = MagicMock()
        ing.spec.rules = [existing_rule]
        mock_networking_v1.read_namespaced_ingress.return_value = ing

        ing_manager.add_rule(
            "my-ingress",
            "default",
            "new.example.com",
            [{"path": "/", "pathType": "Prefix"}],
        )

        call_kwargs = mock_networking_v1.patch_namespaced_ingress.call_args.kwargs
        hosts = [r["host"] for r in call_kwargs["body"]["spec"]["rules"] if "host" in r]
        assert "old.example.com" in hosts
        assert "new.example.com" in hosts

    def test_remove_rule_filters_by_host(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        keep_rule = MagicMock()
        keep_rule.host = "keep.example.com"
        keep_rule.http = None
        remove_rule = MagicMock()
        remove_rule.host = "remove.example.com"
        remove_rule.http = None
        ing = MagicMock()
        ing.spec.rules = [keep_rule, remove_rule]
        mock_networking_v1.read_namespaced_ingress.return_value = ing

        ing_manager.remove_rule("my-ingress", "default", "remove.example.com")

        call_kwargs = mock_networking_v1.patch_namespaced_ingress.call_args.kwargs
        hosts = [r["host"] for r in call_kwargs["body"]["spec"]["rules"]]
        assert hosts == ["keep.example.com"]

    def test_remove_tls_filters_by_host_overlap(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        keep_tls = MagicMock()
        keep_tls.hosts = ["keep.example.com"]
        keep_tls.secret_name = "keep-secret"
        remove_tls = MagicMock()
        remove_tls.hosts = ["remove.example.com"]
        remove_tls.secret_name = "remove-secret"
        ing = MagicMock()
        ing.spec.tls = [keep_tls, remove_tls]
        mock_networking_v1.read_namespaced_ingress.return_value = ing

        ing_manager.remove_tls("my-ingress", "default", ["remove.example.com"])

        call_kwargs = mock_networking_v1.patch_namespaced_ingress.call_args.kwargs
        secrets = [t["secretName"] for t in call_kwargs["body"]["spec"]["tls"]]
        assert secrets == ["keep-secret"]

    def test_set_ingress_class(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        ing_manager.set_ingress_class("my-ingress", "default", "traefik")
        call_kwargs = mock_networking_v1.patch_namespaced_ingress.call_args.kwargs
        assert call_kwargs["body"]["spec"]["ingressClassName"] == "traefik"

    def test_set_default_backend_with_int_port(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        ing_manager.set_default_backend("my-ingress", "default", "web-svc", 80)
        call_kwargs = mock_networking_v1.patch_namespaced_ingress.call_args.kwargs
        assert call_kwargs["body"]["spec"]["defaultBackend"]["service"]["port"] == {
            "number": 80
        }

    def test_set_default_backend_with_named_port(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        ing_manager.set_default_backend("my-ingress", "default", "web-svc", "http")
        call_kwargs = mock_networking_v1.patch_namespaced_ingress.call_args.kwargs
        assert call_kwargs["body"]["spec"]["defaultBackend"]["service"]["port"] == {
            "name": "http"
        }

    def test_get_all_hosts(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        rule = MagicMock()
        rule.host = "example.com"
        ing = MagicMock()
        ing.spec.rules = [rule]
        mock_networking_v1.read_namespaced_ingress.return_value = ing

        assert ing_manager.get_all_hosts("my-ingress", "default") == ["example.com"]

    def test_get_all_rules_with_full_backend(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        port = MagicMock(number=80)
        port.name = "http"
        svc = MagicMock(port=port)
        svc.name = "web-svc"
        backend = MagicMock(service=svc)
        path = MagicMock(backend=backend)
        path.path = "/"
        path.path_type = "Prefix"
        http = MagicMock(paths=[path])
        rule = MagicMock(http=http)
        rule.host = "example.com"
        ing = MagicMock()
        ing.spec.rules = [rule]
        mock_networking_v1.read_namespaced_ingress.return_value = ing

        rules = ing_manager.get_all_rules("my-ingress", "default")

        assert rules[0]["host"] == "example.com"
        assert rules[0]["http"]["paths"][0]["backend"]["service"]["name"] == "web-svc"
        assert rules[0]["http"]["paths"][0]["backend"]["service"]["port"] == {
            "number": 80,
            "name": "http",
        }

    def test_create_ingress_with_default_backend_resource(
        self, ing_manager: IngressManager, mock_networking_v1: MagicMock
    ) -> None:
        ing_manager.create_ingress(
            "my-ingress",
            "default",
            default_backend={
                "resource": {"apiGroup": "k8s.io", "kind": "StorageBucket", "name": "assets"}
            },
        )
        call_kwargs = mock_networking_v1.create_namespaced_ingress.call_args.kwargs
        assert call_kwargs["body"]["spec"]["defaultBackend"]["resource"]["kind"] == (
            "StorageBucket"
        )

    def test_kind_and_api_version(self, ing_manager: IngressManager) -> None:
        assert ing_manager._kind() == "Ingress"
        assert ing_manager._api_version() == "networking.k8s.io/v1"
