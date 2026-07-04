"""Unit tests for kube_orchestrator.resources.base.BaseResourceManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import (
    APIError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
)
from kube_orchestrator.resources.base import BaseResourceManager


class _WidgetManager(BaseResourceManager):
    """Concrete manager used only to exercise the abstract base class."""

    def _get_api(self) -> MagicMock:
        return self.client.core_v1

    def _kind(self) -> str:
        return "Widget"

    def _api_version(self) -> str:
        return "v1"


@pytest.fixture
def manager(mock_kube_client: MagicMock) -> _WidgetManager:
    return _WidgetManager(kube_client=mock_kube_client)


@pytest.fixture
def cluster_scoped_api(mock_kube_client: MagicMock) -> MagicMock:
    """A core_v1 mock with the namespaced verbs removed, forcing the
    cluster-scoped fallback branch of each CRUD method."""
    api = mock_kube_client.core_v1
    for verb in ("read", "list", "create", "replace", "patch", "delete"):
        delattr(api, f"{verb}_namespaced_widget")
    delattr(api, "delete_collection_namespaced_widget")
    return api


@pytest.mark.unit
class TestExists:
    def test_true_when_get_succeeds(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_widget.return_value = MagicMock()
        assert manager.exists("w1") is True

    def test_false_on_not_found(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_widget.side_effect = ApiException(status=404)
        assert manager.exists("w1") is False


@pytest.mark.unit
class TestGet:
    def test_namespaced_branch(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_widget.return_value = "widget-obj"
        assert manager.get("w1", "default") == "widget-obj"
        mock_core_v1.read_namespaced_widget.assert_called_once_with(
            name="w1", namespace="default"
        )

    def test_cluster_scoped_fallback(
        self, manager: _WidgetManager, cluster_scoped_api: MagicMock
    ) -> None:
        cluster_scoped_api.read_widget.return_value = "widget-obj"
        assert manager.get("w1") == "widget-obj"
        cluster_scoped_api.read_widget.assert_called_once_with(name="w1")

    def test_raises_not_found_on_404(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_widget.side_effect = ApiException(status=404)
        with pytest.raises(ResourceNotFoundError):
            manager.get("w1", "default")

    def test_raises_parsed_exception_on_other_error(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_widget.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.get("w1", "default")


@pytest.mark.unit
class TestList:
    def test_namespaced_branch_with_all_filters(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_widget.return_value.items = ["a", "b"]
        result = manager.list(
            "default",
            label_selector="app=web",
            field_selector="status.phase=Running",
            limit=10,
            continue_token="abc",
        )
        assert result == ["a", "b"]
        kwargs = mock_core_v1.list_namespaced_widget.call_args.kwargs
        assert kwargs["label_selector"] == "app=web"
        assert kwargs["field_selector"] == "status.phase=Running"
        assert kwargs["limit"] == 10
        assert kwargs["_continue"] == "abc"

    def test_cluster_scoped_fallback(
        self, manager: _WidgetManager, cluster_scoped_api: MagicMock
    ) -> None:
        cluster_scoped_api.list_widget.return_value.items = ["a"]
        assert manager.list() == ["a"]

    def test_raises_parsed_exception(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_widget.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.list("default")


@pytest.mark.unit
class TestCreate:
    def test_namespaced_branch(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_widget.return_value = "created"
        result = manager.create({"metadata": {"name": "w1"}}, "default")
        assert result == "created"

    def test_cluster_scoped_fallback(
        self, manager: _WidgetManager, cluster_scoped_api: MagicMock
    ) -> None:
        cluster_scoped_api.create_widget.return_value = "created"
        assert manager.create({"metadata": {"name": "w1"}}) == "created"

    def test_includes_dry_run_kwarg_when_enabled(
        self, mock_kube_client: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        manager = _WidgetManager(kube_client=mock_kube_client, dry_run=True)
        manager.create({"metadata": {"name": "w1"}}, "default")
        kwargs = mock_core_v1.create_namespaced_widget.call_args.kwargs
        assert kwargs["dry_run"] == "All"

    def test_raises_already_exists_on_409(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_widget.side_effect = ApiException(status=409)
        with pytest.raises(ResourceAlreadyExistsError):
            manager.create({"metadata": {"name": "w1"}}, "default")

    def test_raises_parsed_exception_on_other_error(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_widget.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.create({"metadata": {}}, "default")


@pytest.mark.unit
class TestUpdate:
    def test_namespaced_branch(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.replace_namespaced_widget.return_value = "replaced"
        assert manager.update("w1", {"metadata": {}}, "default") == "replaced"

    def test_cluster_scoped_fallback(
        self, manager: _WidgetManager, cluster_scoped_api: MagicMock
    ) -> None:
        cluster_scoped_api.replace_widget.return_value = "replaced"
        assert manager.update("w1", {"metadata": {}}) == "replaced"

    def test_raises_not_found_on_404(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.replace_namespaced_widget.side_effect = ApiException(status=404)
        with pytest.raises(ResourceNotFoundError):
            manager.update("w1", {"metadata": {}}, "default")

    def test_raises_parsed_exception_on_other_error(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.replace_namespaced_widget.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.update("w1", {"metadata": {}}, "default")

    def test_includes_dry_run_kwarg(
        self, mock_kube_client: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        manager = _WidgetManager(kube_client=mock_kube_client, dry_run=True)
        manager.update("w1", {"metadata": {}}, "default")
        kwargs = mock_core_v1.replace_namespaced_widget.call_args.kwargs
        assert kwargs["dry_run"] == "All"


@pytest.mark.unit
class TestPatch:
    def test_namespaced_branch(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.patch_namespaced_widget.return_value = "patched"
        result = manager.patch("w1", {"spec": {}}, "default", patch_type="merge")
        assert result == "patched"

    def test_cluster_scoped_fallback(
        self, manager: _WidgetManager, cluster_scoped_api: MagicMock
    ) -> None:
        cluster_scoped_api.patch_widget.return_value = "patched"
        assert manager.patch("w1", {"spec": {}}) == "patched"

    def test_raises_parsed_exception(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.patch_namespaced_widget.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.patch("w1", {"spec": {}}, "default")

    def test_includes_dry_run_kwarg(
        self, mock_kube_client: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        manager = _WidgetManager(kube_client=mock_kube_client, dry_run=True)
        manager.patch("w1", {"spec": {}}, "default")
        kwargs = mock_core_v1.patch_namespaced_widget.call_args.kwargs
        assert kwargs["dry_run"] == "All"


@pytest.mark.unit
class TestApply:
    def test_creates_when_not_existing(self, manager: _WidgetManager) -> None:
        with (
            patch.object(manager, "exists", return_value=False),
            patch.object(manager, "create", return_value="created") as mock_create,
        ):
            result = manager.apply({"metadata": {"name": "w1"}}, "default")
        assert result == "created"
        mock_create.assert_called_once()

    def test_updates_when_existing(self, manager: _WidgetManager) -> None:
        with (
            patch.object(manager, "exists", return_value=True),
            patch.object(manager, "update", return_value="updated") as mock_update,
        ):
            result = manager.apply({"metadata": {"name": "w1"}}, "default")
        assert result == "updated"
        mock_update.assert_called_once()


@pytest.mark.unit
class TestDelete:
    def test_namespaced_branch(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        manager.delete("w1", "default", grace_period_seconds=30)
        mock_core_v1.delete_namespaced_widget.assert_called_once()
        kwargs = mock_core_v1.delete_namespaced_widget.call_args.kwargs
        assert kwargs["body"].grace_period_seconds == 30

    def test_cluster_scoped_fallback(
        self, manager: _WidgetManager, cluster_scoped_api: MagicMock
    ) -> None:
        manager.delete("w1")
        cluster_scoped_api.delete_widget.assert_called_once()

    def test_includes_dry_run_kwarg(
        self, mock_kube_client: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        manager = _WidgetManager(kube_client=mock_kube_client, dry_run=True)
        manager.delete("w1", "default")
        kwargs = mock_core_v1.delete_namespaced_widget.call_args.kwargs
        assert kwargs["dry_run"] == "All"

    def test_raises_not_found_on_404(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.delete_namespaced_widget.side_effect = ApiException(status=404)
        with pytest.raises(ResourceNotFoundError):
            manager.delete("w1", "default")

    def test_raises_parsed_exception_on_other_error(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.delete_namespaced_widget.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            manager.delete("w1", "default")


@pytest.mark.unit
class TestDeleteCollection:
    def test_namespaced_branch_with_label_selector(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        manager.delete_collection("default", label_selector="app=web")
        kwargs = mock_core_v1.delete_collection_namespaced_widget.call_args.kwargs
        assert kwargs["label_selector"] == "app=web"

    def test_cluster_scoped_fallback(
        self, manager: _WidgetManager, cluster_scoped_api: MagicMock
    ) -> None:
        manager.delete_collection()
        cluster_scoped_api.delete_collection_widget.assert_called_once()

    def test_includes_dry_run_kwarg(
        self, mock_kube_client: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        manager = _WidgetManager(kube_client=mock_kube_client, dry_run=True)
        manager.delete_collection("default")
        kwargs = mock_core_v1.delete_collection_namespaced_widget.call_args.kwargs
        assert kwargs["dry_run"] == "All"

    def test_raises_parsed_exception(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.delete_collection_namespaced_widget.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            manager.delete_collection("default")


@pytest.mark.unit
class TestWatch:
    def test_namespaced_branch_invokes_callback(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        events = [{"type": "ADDED", "object": "widget-obj"}]
        received = []
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            manager.watch("default", callback=lambda t, o: received.append((t, o)))
        assert received == [("ADDED", "widget-obj")]

    def test_cluster_scoped_fallback(
        self, manager: _WidgetManager, cluster_scoped_api: MagicMock
    ) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = []
            manager.watch()
        watch_cls.return_value.stream.assert_called_once_with(
            cluster_scoped_api.list_widget, namespace="default", timeout_seconds=60
        )

    def test_without_callback_does_not_raise(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = [
                {"type": "ADDED", "object": "x"}
            ]
            manager.watch("default")

    def test_with_label_selector(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = []
            manager.watch("default", label_selector="app=web")
        kwargs = watch_cls.return_value.stream.call_args.kwargs
        assert kwargs["label_selector"] == "app=web"


@pytest.mark.unit
class TestWaitForCondition:
    def test_returns_true_for_matching_object_condition(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        cond = MagicMock(type="Ready", status="True")
        resource = MagicMock()
        resource.status.conditions = [cond]
        mock_core_v1.read_namespaced_widget.return_value = resource
        assert manager.wait_for_condition("w1", "default", timeout_seconds=5) is True

    def test_returns_true_for_matching_dict_condition(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        resource = MagicMock()
        resource.status.conditions = [{"type": "Ready", "status": "True"}]
        mock_core_v1.read_namespaced_widget.return_value = resource
        assert manager.wait_for_condition("w1", "default", timeout_seconds=5) is True

    def test_ignores_not_found_and_times_out(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_widget.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.base.time.sleep"):
            assert (
                manager.wait_for_condition("w1", "default", timeout_seconds=0.05)
                is False
            )

    def test_times_out_without_matching_condition(
        self, manager: _WidgetManager, mock_core_v1: MagicMock
    ) -> None:
        resource = MagicMock()
        resource.status.conditions = []
        mock_core_v1.read_namespaced_widget.return_value = resource
        with patch("kube_orchestrator.resources.base.time.sleep"):
            assert (
                manager.wait_for_condition("w1", "default", timeout_seconds=0.05)
                is False
            )


@pytest.mark.unit
class TestGetEvents:
    def test_returns_events(
        self, manager: _WidgetManager, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespaced_event.return_value.items = ["evt"]
        assert manager.get_events("w1", "default") == ["evt"]
        kwargs = mock_kube_client.core_v1.list_namespaced_event.call_args.kwargs
        assert (
            kwargs["field_selector"]
            == "involvedObject.name=w1,involvedObject.kind=Widget"
        )

    def test_raises_parsed_exception(
        self, manager: _WidgetManager, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespaced_event.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            manager.get_events("w1", "default")


@pytest.mark.unit
class TestSetDryRunAndResourceName:
    def test_set_dry_run_enabled(self, manager: _WidgetManager) -> None:
        manager.set_dry_run(True)
        assert manager.dry_run == "All"

    def test_set_dry_run_disabled(self, manager: _WidgetManager) -> None:
        manager.set_dry_run(False)
        assert manager.dry_run is None

    def test_resource_name_derived_from_kind(self, manager: _WidgetManager) -> None:
        assert manager._resource_name() == "widget"

    def test_resource_name_replaces_hyphens(self, mock_kube_client: MagicMock) -> None:
        class _HyphenKindManager(_WidgetManager):
            def _kind(self) -> str:
                return "My-Kind"

        mgr = _HyphenKindManager(kube_client=mock_kube_client)
        assert mgr._resource_name() == "my_kind"
