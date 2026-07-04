"""Unit tests for kube_orchestrator.crd.watcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.crd.watcher import CRDWatcher


@pytest.fixture
def watcher(mock_kube_client: MagicMock) -> CRDWatcher:
    return CRDWatcher(kube_client=mock_kube_client)


def _event(event_type: str, name: str = "foos.example.com") -> dict:
    obj = MagicMock()
    obj.metadata.name = name
    obj.to_dict.return_value = {"metadata": {"name": name}}
    return {"type": event_type, "object": obj}


@pytest.mark.unit
class TestCRDWatcherHandlerRegistration:
    def test_on_crd_added_registers_handler(self, watcher: CRDWatcher) -> None:
        handler = MagicMock()
        watcher.on_crd_added(handler)
        assert handler in watcher._on_added

    def test_on_crd_modified_registers_handler(self, watcher: CRDWatcher) -> None:
        handler = MagicMock()
        watcher.on_crd_modified(handler)
        assert handler in watcher._on_modified

    def test_on_crd_deleted_registers_handler(self, watcher: CRDWatcher) -> None:
        handler = MagicMock()
        watcher.on_crd_deleted(handler)
        assert handler in watcher._on_deleted


@pytest.mark.unit
class TestCRDWatcherWatchAll:
    def test_dispatches_added_event_to_handler_and_callback(
        self, watcher: CRDWatcher
    ) -> None:
        added_handler = MagicMock()
        callback = MagicMock()
        watcher.on_crd_added(added_handler)

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = [_event("ADDED")]
            watcher.watch_all(callback=callback)

        added_handler.assert_called_once()
        callback.assert_called_once()
        event = callback.call_args.args[0]
        assert event["type"] == "ADDED"
        assert event["name"] == "foos.example.com"
        assert event["object"] == {"metadata": {"name": "foos.example.com"}}

    def test_dispatches_modified_event(self, watcher: CRDWatcher) -> None:
        modified_handler = MagicMock()
        watcher.on_crd_modified(modified_handler)

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = [_event("MODIFIED")]
            watcher.watch_all()

        modified_handler.assert_called_once()

    def test_dispatches_deleted_event(self, watcher: CRDWatcher) -> None:
        deleted_handler = MagicMock()
        watcher.on_crd_deleted(deleted_handler)

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = [_event("DELETED")]
            watcher.watch_all()

        deleted_handler.assert_called_once()

    def test_handles_object_without_to_dict_method(self, watcher: CRDWatcher) -> None:
        class _FakeK8sObject:
            def __init__(self, name: str) -> None:
                self.metadata = type("Meta", (), {"name": name})()

        fake_obj = _FakeK8sObject("raw")
        raw_event = {"type": "ADDED", "object": fake_obj}
        callback = MagicMock()

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = [raw_event]
            watcher.watch_all(callback=callback)

        event = callback.call_args.args[0]
        assert event["name"] == "raw"
        assert event["object"] is fake_obj

    def test_unknown_event_type_only_invokes_callback(
        self, watcher: CRDWatcher
    ) -> None:
        added_handler = MagicMock()
        watcher.on_crd_added(added_handler)
        callback = MagicMock()

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = [_event("BOOKMARK")]
            watcher.watch_all(callback=callback)

        callback.assert_called_once()
        added_handler.assert_not_called()
