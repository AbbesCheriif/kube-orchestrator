"""Unit tests for kube_orchestrator.controllers.watcher."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.controllers.watcher import HooksRegistry, ResourceWatcher


def _run_and_join(watcher: ResourceWatcher, action: Callable[[], None]) -> None:
    action()
    thread = watcher._watchers[-1]
    thread.join(timeout=2)
    assert not thread.is_alive()


@pytest.fixture
def watcher(mock_kube_client: MagicMock) -> ResourceWatcher:
    return ResourceWatcher(client=mock_kube_client)


@pytest.mark.unit
class TestResourceWatcherStreams:
    def test_watch_pods_invokes_callback_per_event(
        self, watcher: ResourceWatcher
    ) -> None:
        fake_obj = MagicMock()
        fake_obj.to_dict.return_value = {"kind": "Pod"}
        events = [{"type": "ADDED", "object": fake_obj}]
        received: list[tuple[str, dict]] = []

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            _run_and_join(
                watcher,
                lambda: watcher.watch_pods(
                    "default", callback=lambda t, o: received.append((t, o))
                ),
            )

        assert received == [("ADDED", {"kind": "Pod"})]

    def test_watch_deployments_invokes_callback(self, watcher: ResourceWatcher) -> None:
        events = [{"type": "MODIFIED", "object": {"kind": "Deployment"}}]
        received: list[str] = []

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            _run_and_join(
                watcher,
                lambda: watcher.watch_deployments(
                    "default", callback=lambda t, o: received.append(t)
                ),
            )

        assert received == ["MODIFIED"]

    def test_watch_nodes_invokes_callback(self, watcher: ResourceWatcher) -> None:
        events = [{"type": "ADDED", "object": {"kind": "Node"}}]
        received: list[str] = []

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            _run_and_join(
                watcher,
                lambda: watcher.watch_nodes(callback=lambda t, o: received.append(t)),
            )

        assert received == ["ADDED"]

    def test_watch_events_invokes_callback(self, watcher: ResourceWatcher) -> None:
        events = [{"type": "ADDED", "object": {"kind": "Event"}}]
        received: list[str] = []

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            _run_and_join(
                watcher,
                lambda: watcher.watch_events(
                    "default", callback=lambda t, o: received.append(t)
                ),
            )

        assert received == ["ADDED"]

    def test_watch_with_no_callback_does_not_raise(
        self, watcher: ResourceWatcher
    ) -> None:
        events = [{"type": "ADDED", "object": {"kind": "Pod"}}]
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            _run_and_join(watcher, lambda: watcher.watch_pods("default"))

    def test_callback_error_is_caught_and_logged(
        self, watcher: ResourceWatcher
    ) -> None:
        events = [{"type": "ADDED", "object": {"kind": "Pod"}}]

        def _boom(_t: str, _o: dict) -> None:
            raise RuntimeError("callback exploded")

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            _run_and_join(
                watcher, lambda: watcher.watch_pods("default", callback=_boom)
            )

    def test_stream_error_is_caught_and_logged(self, watcher: ResourceWatcher) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.side_effect = RuntimeError("connection lost")
            _run_and_join(watcher, lambda: watcher.watch_pods("default"))

    def test_stop_event_set_before_streaming_stops_watch_loop(
        self, watcher: ResourceWatcher
    ) -> None:
        events = [{"type": "ADDED", "object": {"kind": "Pod"}}]
        received: list[str] = []
        watcher.stop_all()

        with patch("kubernetes.watch.Watch") as watch_cls:
            fake_watch = watch_cls.return_value
            fake_watch.stream.return_value = events
            _run_and_join(
                watcher,
                lambda: watcher.watch_pods(
                    "default", callback=lambda t, o: received.append(t)
                ),
            )
            fake_watch.stop.assert_called_once()

        assert received == []

    def test_watch_pods_passes_timeout_seconds(self, watcher: ResourceWatcher) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = []
            _run_and_join(
                watcher, lambda: watcher.watch_pods("default", timeout_seconds=30)
            )
            _, kwargs = watch_cls.return_value.stream.call_args
            assert kwargs["timeout_seconds"] == 30


@pytest.mark.unit
class TestResourceWatcherAny:
    def test_watch_any_pods_namespaced(self, watcher: ResourceWatcher) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = []
            _run_and_join(
                watcher, lambda: watcher.watch_any("pods", namespace="default")
            )
            watch_cls.return_value.stream.assert_called_once()

    def test_watch_any_pods_cluster_wide(self, watcher: ResourceWatcher) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = []
            _run_and_join(watcher, lambda: watcher.watch_any("pods"))

    def test_watch_any_deployments(self, watcher: ResourceWatcher) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = []
            _run_and_join(
                watcher, lambda: watcher.watch_any("deployments", namespace="default")
            )

    def test_watch_any_nodes_ignores_namespace(self, watcher: ResourceWatcher) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = []
            _run_and_join(
                watcher, lambda: watcher.watch_any("nodes", namespace="default")
            )

    def test_watch_any_unsupported_resource_raises(
        self, watcher: ResourceWatcher
    ) -> None:
        with pytest.raises(ValueError, match="Unsupported resource type"):
            watcher.watch_any("bogus")

    def test_watch_any_is_case_insensitive(self, watcher: ResourceWatcher) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = []
            _run_and_join(
                watcher, lambda: watcher.watch_any("PODS", namespace="default")
            )


@pytest.mark.unit
class TestResourceWatcherStopAll:
    def test_stop_all_sets_stop_event(self, watcher: ResourceWatcher) -> None:
        watcher.stop_all()
        assert watcher._stop_event.is_set()


@pytest.mark.unit
class TestHooksRegistry:
    def test_register_returns_hook_id_and_lists_it(self) -> None:
        registry = HooksRegistry()
        hook_id = registry.register("POD_FAILED", lambda r: None)
        assert hook_id in registry.list_hooks()["POD_FAILED"]

    def test_trigger_invokes_registered_handler(self) -> None:
        registry = HooksRegistry()
        received: list[dict] = []
        registry.register("POD_FAILED", lambda r: received.append(r))
        registry.trigger("POD_FAILED", {"name": "web-1"})
        assert received == [{"name": "web-1"}]

    def test_trigger_unknown_event_type_is_noop(self) -> None:
        registry = HooksRegistry()
        registry.trigger("UNKNOWN_EVENT", {})  # should not raise

    def test_trigger_catches_handler_errors(self) -> None:
        registry = HooksRegistry()

        def _boom(_resource: dict) -> None:
            raise RuntimeError("handler exploded")

        registry.register("POD_FAILED", _boom)
        registry.trigger("POD_FAILED", {})  # should not raise

    def test_unregister_removes_hook(self) -> None:
        registry = HooksRegistry()
        hook_id = registry.register("POD_FAILED", lambda r: None)
        registry.unregister(hook_id)
        assert hook_id not in registry.list_hooks().get("POD_FAILED", [])

    def test_unregister_unknown_hook_id_is_noop(self) -> None:
        registry = HooksRegistry()
        registry.unregister("does-not-exist")  # should not raise

    def test_list_hooks_empty_by_default(self) -> None:
        registry = HooksRegistry()
        assert registry.list_hooks() == {}
