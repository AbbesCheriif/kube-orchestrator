"""Unit tests for IngressClassManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError
from kube_orchestrator.resources.networking.ingress_class import IngressClassManager


@pytest.fixture
def ic_manager(mock_kube_client: MagicMock) -> IngressClassManager:
    return IngressClassManager(kube_client=mock_kube_client)


@pytest.fixture
def networking_api(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.networking_v1


@pytest.mark.unit
class TestCreateIngressClass:
    def test_creates_minimal(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        ic_manager.create_ingress_class("nginx", "k8s.io/ingress-nginx")
        call_kwargs = networking_api.create_ingress_class.call_args.kwargs
        assert call_kwargs["body"]["spec"]["controller"] == "k8s.io/ingress-nginx"
        assert "annotations" not in call_kwargs["body"]["metadata"]

    def test_creates_default_class_with_annotation(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        ic_manager.create_ingress_class(
            "nginx", "k8s.io/ingress-nginx", is_default=True
        )
        call_kwargs = networking_api.create_ingress_class.call_args.kwargs
        annotations = call_kwargs["body"]["metadata"]["annotations"]
        assert annotations["ingressclass.kubernetes.io/is-default-class"] == "true"

    def test_creates_with_parameters(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        ic_manager.create_ingress_class(
            "nginx",
            "k8s.io/ingress-nginx",
            parameters={
                "apiGroup": "k8s.io",
                "kind": "IngressParameters",
                "name": "nginx-params",
                "namespace": "ingress-system",
                "scope": "Namespace",
            },
        )
        call_kwargs = networking_api.create_ingress_class.call_args.kwargs
        params = call_kwargs["body"]["spec"]["parameters"]
        assert params["apiGroup"] == "k8s.io"
        assert params["namespace"] == "ingress-system"
        assert params["scope"] == "Namespace"

    def test_raises_parsed_exception(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        networking_api.create_ingress_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            ic_manager.create_ingress_class("nginx", "k8s.io/ingress-nginx")


@pytest.mark.unit
class TestGetListDelete:
    def test_get_ingress_class(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        networking_api.read_ingress_class.return_value = "ic-obj"
        assert ic_manager.get_ingress_class("nginx") == "ic-obj"

    def test_get_ingress_class_raises_parsed_exception(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        networking_api.read_ingress_class.side_effect = ApiException(status=404)
        with pytest.raises(Exception):
            ic_manager.get_ingress_class("missing")

    def test_list_ingress_classes(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        networking_api.list_ingress_class.return_value.items = ["a"]
        assert ic_manager.list_ingress_classes() == ["a"]

    def test_list_ingress_classes_raises_parsed_exception(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        networking_api.list_ingress_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            ic_manager.list_ingress_classes()

    def test_delete_ingress_class(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        ic_manager.delete_ingress_class("nginx")
        networking_api.delete_ingress_class.assert_called_once()

    def test_delete_ingress_class_raises_parsed_exception(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        networking_api.delete_ingress_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            ic_manager.delete_ingress_class("nginx")


@pytest.mark.unit
class TestDefaultManagement:
    def test_set_as_default(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        ic_manager.set_as_default("nginx")
        call_kwargs = networking_api.patch_ingress_class.call_args.kwargs
        annotations = call_kwargs["body"]["metadata"]["annotations"]
        assert annotations["ingressclass.kubernetes.io/is-default-class"] == "true"

    def test_set_as_default_raises_parsed_exception(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        networking_api.patch_ingress_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            ic_manager.set_as_default("nginx")

    def test_unset_default(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        ic_manager.unset_default("nginx")
        call_kwargs = networking_api.patch_ingress_class.call_args.kwargs
        annotations = call_kwargs["body"]["metadata"]["annotations"]
        assert annotations["ingressclass.kubernetes.io/is-default-class"] is None

    def test_unset_default_raises_parsed_exception(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        networking_api.patch_ingress_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            ic_manager.unset_default("nginx")

    def test_get_default_found(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        default_ic = MagicMock()
        default_ic.metadata.annotations = {
            "ingressclass.kubernetes.io/is-default-class": "true"
        }
        other_ic = MagicMock()
        other_ic.metadata.annotations = {}
        networking_api.list_ingress_class.return_value.items = [other_ic, default_ic]

        assert ic_manager.get_default() is default_ic

    def test_get_default_none(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        other_ic = MagicMock()
        other_ic.metadata.annotations = {}
        networking_api.list_ingress_class.return_value.items = [other_ic]
        assert ic_manager.get_default() is None


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, ic_manager: IngressClassManager) -> None:
        assert ic_manager._kind() == "IngressClass"
        assert ic_manager._api_version() == "networking.k8s.io/v1"
        assert ic_manager._resource_name() == "ingress_class"

    def test_get_api_returns_networking_v1(
        self, ic_manager: IngressClassManager, networking_api: MagicMock
    ) -> None:
        assert ic_manager._get_api() is networking_api
