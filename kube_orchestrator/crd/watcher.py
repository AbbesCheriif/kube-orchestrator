"""CRDWatcher — watch CRD lifecycle events from the cluster."""

from __future__ import annotations

from typing import Any, Callable

from kubernetes import client, watch
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception


class CRDWatcher:
    """Watch add/modify/delete events on CustomResourceDefinitions."""

    def __init__(self, kube_client: KubeClient) -> None:
        self.client = kube_client
        self._on_added: list[Callable[[dict[str, Any]], None]] = []
        self._on_modified: list[Callable[[dict[str, Any]], None]] = []
        self._on_deleted: list[Callable[[dict[str, Any]], None]] = []

    def on_crd_added(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback for CRD ADDED events."""
        self._on_added.append(handler)

    def on_crd_modified(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback for CRD MODIFIED events."""
        self._on_modified.append(handler)

    def on_crd_deleted(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback for CRD DELETED events."""
        self._on_deleted.append(handler)

    def watch_all(
        self,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Stream all CRD events and dispatch to registered handlers.

        Blocks until the watch is terminated or an error occurs.
        """
        w = watch.Watch()
        api = self.client.api_extensions_v1
        for raw_event in w.stream(api.list_custom_resource_definition):
            event_type: str = raw_event.get("type", "")
            obj = raw_event.get("object")
            event_dict: dict[str, Any] = {
                "type": event_type,
                "name": (
                    obj.metadata.name
                    if obj and obj.metadata
                    else None
                ),
                "object": obj.to_dict() if hasattr(obj, "to_dict") else obj,
            }
            if callback:
                callback(event_dict)
            if event_type == "ADDED":
                for h in self._on_added:
                    h(event_dict)
            elif event_type == "MODIFIED":
                for h in self._on_modified:
                    h(event_dict)
            elif event_type == "DELETED":
                for h in self._on_deleted:
                    h(event_dict)
