"""Unit tests for EventManager."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError
from kube_orchestrator.resources.cluster.event_manager import EventManager


@pytest.fixture
def event_manager(mock_kube_client: MagicMock) -> EventManager:
    return EventManager(kube_client=mock_kube_client)


def _fake_event(
    name: str = "evt-1",
    namespace: str = "default",
    reason: str = "Scheduled",
    event_type: str = "Normal",
    last_timestamp: datetime | None = None,
) -> MagicMock:
    event = MagicMock()
    event.metadata.name = name
    event.metadata.namespace = namespace
    event.reason = reason
    event.message = "message"
    event.type = event_type
    event.count = 1
    event.first_timestamp = last_timestamp
    event.last_timestamp = last_timestamp
    event.involved_object.kind = "Pod"
    event.involved_object.name = "web-1"
    event.source.component = "kubelet"
    event.source.host = "worker-1"
    return event


@pytest.mark.unit
class TestListEvents:
    def test_list_events_without_filters(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_event.return_value.items = [_fake_event()]
        result = event_manager.list_events("default")
        assert result[0]["name"] == "evt-1"
        kwargs = mock_core_v1.list_namespaced_event.call_args.kwargs
        assert kwargs["field_selector"] is None

    def test_list_events_uses_default_namespace_when_omitted(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_event.return_value.items = []
        event_manager.list_events()
        kwargs = mock_core_v1.list_namespaced_event.call_args.kwargs
        assert kwargs["namespace"] == event_manager.default_namespace

    def test_list_events_builds_combined_field_selector(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_event.return_value.items = []
        event_manager.list_events(
            "default",
            involved_object_name="web-1",
            involved_object_kind="Pod",
            event_type="Warning",
            reason="Failed",
        )
        kwargs = mock_core_v1.list_namespaced_event.call_args.kwargs
        assert kwargs["field_selector"] == (
            "involvedObject.name=web-1,involvedObject.kind=Pod,"
            "type=Warning,reason=Failed"
        )

    def test_list_events_raises_parsed_exception(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_event.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            event_manager.list_events("default")

    def test_get_events_for_pod(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_event.return_value.items = [_fake_event()]
        result = event_manager.get_events_for_pod("web-1", "default")
        kwargs = mock_core_v1.list_namespaced_event.call_args.kwargs
        assert "involvedObject.name=web-1" in kwargs["field_selector"]
        assert result[0]["involved_object_kind"] == "Pod"

    def test_get_events_for_node(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_event_for_all_namespaces.return_value.items = [
            _fake_event()
        ]
        result = event_manager.get_events_for_node("worker-1")
        assert len(result) == 1

    def test_get_events_for_node_raises_parsed_exception(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_event_for_all_namespaces.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            event_manager.get_events_for_node("worker-1")

    def test_get_warning_events(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_event.return_value.items = [
            _fake_event(event_type="Warning")
        ]
        result = event_manager.get_warning_events("default")
        kwargs = mock_core_v1.list_namespaced_event.call_args.kwargs
        assert kwargs["field_selector"] == "type=Warning"
        assert result[0]["type"] == "Warning"

    def test_get_recent_events_filters_by_cutoff(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        recent = _fake_event(name="recent", last_timestamp=now)
        old = _fake_event(name="old", last_timestamp=now - timedelta(hours=2))
        mock_core_v1.list_namespaced_event.return_value.items = [recent, old]

        result = event_manager.get_recent_events("default", last_minutes=30)

        assert [e["name"] for e in result] == ["recent"]

    def test_get_recent_events_skips_events_without_timestamp(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        no_ts = _fake_event(name="no-ts", last_timestamp=None)
        mock_core_v1.list_namespaced_event.return_value.items = [no_ts]
        result = event_manager.get_recent_events("default")
        assert result == []


@pytest.mark.unit
class TestStreamEvents:
    def test_stream_events_invokes_callback(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        fake_obj = _fake_event()
        events = [{"type": "ADDED", "object": fake_obj}]
        received = []

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            event_manager.stream_events("default", callback=received.append)

        assert received[0]["watch_type"] == "ADDED"
        assert received[0]["name"] == "evt-1"

    def test_stream_events_without_callback(
        self, event_manager: EventManager, mock_core_v1: MagicMock
    ) -> None:
        events = [{"type": "ADDED", "object": _fake_event()}]
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            event_manager.stream_events()  # should not raise


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, event_manager: EventManager) -> None:
        assert event_manager._kind() == "Event"
        assert event_manager._api_version() == "v1"
