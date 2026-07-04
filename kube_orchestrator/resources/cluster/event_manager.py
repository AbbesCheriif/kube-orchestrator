"""EventManager — list and stream Kubernetes events from the cluster."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from kubernetes import (  # type: ignore[attr-defined]  # kubernetes-stubs has no watch submodule stub
    client,
    watch,
)
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager


class EventManager(BaseResourceManager[Any]):
    """Query and stream Kubernetes core events (v1)."""

    def __init__(
        self,
        kube_client: KubeClient | None = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.CoreV1Api:
        return self.client.core_v1

    def _kind(self) -> str:
        return "Event"

    def _api_version(self) -> str:
        return "v1"

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_events(
        self,
        namespace: str | None = None,
        involved_object_name: str | None = None,
        involved_object_kind: str | None = None,
        event_type: str | None = None,
        reason: str | None = None,
    ) -> list[dict[str, Any]]:
        ns = namespace or self.default_namespace
        field_parts: list[str] = []
        if involved_object_name:
            field_parts.append(f"involvedObject.name={involved_object_name}")
        if involved_object_kind:
            field_parts.append(f"involvedObject.kind={involved_object_kind}")
        if event_type:
            field_parts.append(f"type={event_type}")
        if reason:
            field_parts.append(f"reason={reason}")
        field_selector = ",".join(field_parts) if field_parts else None
        try:
            api = self._get_api()
            result = api.list_namespaced_event(
                namespace=ns,
                field_selector=field_selector,
            )
            return [self._event_to_dict(e) for e in result.items]
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_events_for_pod(
        self, pod_name: str, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        return self.list_events(
            namespace=namespace,
            involved_object_name=pod_name,
            involved_object_kind="Pod",
        )

    def get_events_for_node(self, node_name: str) -> list[dict[str, Any]]:
        try:
            api = self._get_api()
            result = api.list_event_for_all_namespaces(
                field_selector=(
                    f"involvedObject.name={node_name}," "involvedObject.kind=Node"
                ),
            )
            return [self._event_to_dict(e) for e in result.items]
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_warning_events(self, namespace: str | None = None) -> list[dict[str, Any]]:
        return self.list_events(namespace=namespace, event_type="Warning")

    def get_recent_events(
        self, namespace: str | None = None, last_minutes: int = 30
    ) -> list[dict[str, Any]]:
        events = self.list_events(namespace=namespace)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=last_minutes)
        return [
            e
            for e in events
            if e.get("last_timestamp") and e["last_timestamp"] >= cutoff
        ]

    def stream_events(
        self,
        namespace: str | None = None,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        ns = namespace or self.default_namespace
        w = watch.Watch()
        api = self._get_api()
        for raw_event in w.stream(api.list_namespaced_event, namespace=ns):
            event_dict = self._event_to_dict(raw_event["object"])
            event_dict["watch_type"] = raw_event["type"]
            if callback:
                callback(event_dict)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _event_to_dict(event: Any) -> dict[str, Any]:
        return {
            "name": event.metadata.name if event.metadata else None,
            "namespace": event.metadata.namespace if event.metadata else None,
            "reason": event.reason,
            "message": event.message,
            "type": event.type,
            "count": event.count,
            "first_timestamp": event.first_timestamp,
            "last_timestamp": event.last_timestamp,
            "involved_object_kind": (
                event.involved_object.kind if event.involved_object else None
            ),
            "involved_object_name": (
                event.involved_object.name if event.involved_object else None
            ),
            "source_component": (event.source.component if event.source else None),
            "source_host": (event.source.host if event.source else None),
        }
