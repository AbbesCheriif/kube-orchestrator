"""Unit tests for kube_orchestrator.crd.custom_object_manager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError, ResourceNotFoundError
from kube_orchestrator.crd.custom_object_manager import CustomObjectManager


@pytest.fixture
def manager(mock_kube_client: MagicMock) -> CustomObjectManager:
    return CustomObjectManager(
        group="example.com", version="v1", plural="foos", kube_client=mock_kube_client
    )


@pytest.fixture
def api(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.custom_objects


@pytest.mark.unit
class TestCreate:
    def test_namespaced(self, manager: CustomObjectManager, api: MagicMock) -> None:
        api.create_namespaced_custom_object.return_value = {"kind": "Foo"}
        result = manager.create({"kind": "Foo"}, namespace="default")
        api.create_namespaced_custom_object.assert_called_once_with(
            "example.com", "v1", "default", "foos", {"kind": "Foo"}
        )
        assert result == {"kind": "Foo"}

    def test_cluster_scoped(self, manager: CustomObjectManager, api: MagicMock) -> None:
        api.create_cluster_custom_object.return_value = {"kind": "Foo"}
        manager.create({"kind": "Foo"})
        api.create_cluster_custom_object.assert_called_once_with(
            "example.com", "v1", "foos", {"kind": "Foo"}
        )

    def test_raises_parsed_exception(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.create_cluster_custom_object.side_effect = ApiException(status=409)
        with pytest.raises(Exception):
            manager.create({"kind": "Foo"})


@pytest.mark.unit
class TestGet:
    def test_namespaced(self, manager: CustomObjectManager, api: MagicMock) -> None:
        api.get_namespaced_custom_object.return_value = {"kind": "Foo"}
        assert manager.get("my-foo", namespace="default") == {"kind": "Foo"}

    def test_cluster_scoped(self, manager: CustomObjectManager, api: MagicMock) -> None:
        api.get_cluster_custom_object.return_value = {"kind": "Foo"}
        assert manager.get("my-foo") == {"kind": "Foo"}

    def test_raises_parsed_exception(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.get_cluster_custom_object.side_effect = ApiException(status=404)
        with pytest.raises(ResourceNotFoundError):
            manager.get("missing")


@pytest.mark.unit
class TestList:
    def test_namespaced_with_selector(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.list_namespaced_custom_object.return_value = {"items": [{"kind": "Foo"}]}
        result = manager.list(namespace="default", label_selector="app=web")
        api.list_namespaced_custom_object.assert_called_once_with(
            "example.com", "v1", "default", "foos", label_selector="app=web"
        )
        assert result == [{"kind": "Foo"}]

    def test_cluster_scoped_without_selector(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.list_cluster_custom_object.return_value = {"items": []}
        assert manager.list() == []
        api.list_cluster_custom_object.assert_called_once_with(
            "example.com", "v1", "foos"
        )

    def test_raises_parsed_exception(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.list_cluster_custom_object.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.list()


@pytest.mark.unit
class TestUpdate:
    def test_namespaced(self, manager: CustomObjectManager, api: MagicMock) -> None:
        api.replace_namespaced_custom_object.return_value = {"kind": "Foo"}
        manager.update("my-foo", {"kind": "Foo"}, namespace="default")
        api.replace_namespaced_custom_object.assert_called_once_with(
            "example.com", "v1", "default", "foos", "my-foo", {"kind": "Foo"}
        )

    def test_cluster_scoped(self, manager: CustomObjectManager, api: MagicMock) -> None:
        api.replace_cluster_custom_object.return_value = {"kind": "Foo"}
        manager.update("my-foo", {"kind": "Foo"})
        api.replace_cluster_custom_object.assert_called_once_with(
            "example.com", "v1", "foos", "my-foo", {"kind": "Foo"}
        )

    def test_raises_parsed_exception(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.replace_cluster_custom_object.side_effect = ApiException(status=409)
        with pytest.raises(Exception):
            manager.update("my-foo", {})


@pytest.mark.unit
class TestPatch:
    def test_namespaced(self, manager: CustomObjectManager, api: MagicMock) -> None:
        api.patch_namespaced_custom_object.return_value = {"kind": "Foo"}
        manager.patch("my-foo", {"spec": {}}, namespace="default")
        api.patch_namespaced_custom_object.assert_called_once_with(
            "example.com", "v1", "default", "foos", "my-foo", {"spec": {}}
        )

    def test_cluster_scoped(self, manager: CustomObjectManager, api: MagicMock) -> None:
        api.patch_cluster_custom_object.return_value = {"kind": "Foo"}
        manager.patch("my-foo", {"spec": {}})
        api.patch_cluster_custom_object.assert_called_once_with(
            "example.com", "v1", "foos", "my-foo", {"spec": {}}
        )

    def test_raises_parsed_exception(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.patch_cluster_custom_object.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.patch("my-foo", {})


@pytest.mark.unit
class TestDelete:
    def test_namespaced(self, manager: CustomObjectManager, api: MagicMock) -> None:
        manager.delete("my-foo", namespace="default")
        api.delete_namespaced_custom_object.assert_called_once_with(
            "example.com", "v1", "default", "foos", "my-foo"
        )

    def test_cluster_scoped(self, manager: CustomObjectManager, api: MagicMock) -> None:
        manager.delete("my-foo")
        api.delete_cluster_custom_object.assert_called_once_with(
            "example.com", "v1", "foos", "my-foo"
        )

    def test_raises_parsed_exception(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.delete_cluster_custom_object.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.delete("my-foo")


@pytest.mark.unit
class TestExists:
    def test_true_when_get_succeeds(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.get_cluster_custom_object.return_value = {"kind": "Foo"}
        assert manager.exists("my-foo") is True

    def test_false_when_get_fails(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        api.get_cluster_custom_object.side_effect = ApiException(status=404)
        assert manager.exists("my-foo") is False


@pytest.mark.unit
class TestWatch:
    def test_namespaced_stream_dispatches_to_callback(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        received = []
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = [
                {"type": "ADDED", "object": {"kind": "Foo"}}
            ]
            manager.watch(namespace="default", callback=received.append)

        watch_cls.return_value.stream.assert_called_once_with(
            api.list_namespaced_custom_object,
            "example.com",
            "v1",
            "default",
            "foos",
        )
        assert received == [{"type": "ADDED", "object": {"kind": "Foo"}}]

    def test_cluster_scoped_stream_without_callback(
        self, manager: CustomObjectManager, api: MagicMock
    ) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = [
                {"type": "ADDED", "object": {"kind": "Foo"}}
            ]
            manager.watch()

        watch_cls.return_value.stream.assert_called_once_with(
            api.list_cluster_custom_object, "example.com", "v1", "foos"
        )
