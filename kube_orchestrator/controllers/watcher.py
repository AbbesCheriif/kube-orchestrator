from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import Any

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.logging import get_logger


class EventTypes:
    POD_FAILED = "POD_FAILED"
    POD_RUNNING = "POD_RUNNING"
    DEPLOYMENT_UPDATED = "DEPLOYMENT_UPDATED"
    NODE_READY = "NODE_READY"
    NODE_NOT_READY = "NODE_NOT_READY"
    CRD_ADDED = "CRD_ADDED"
    ROLLOUT_FAILED = "ROLLOUT_FAILED"
    SCALING_EVENT = "SCALING_EVENT"


class ResourceWatcher:
    def __init__(self, client: KubeClient | None = None) -> None:
        self._client = client or KubeClient.get_instance()
        self._logger = get_logger(__name__)
        self._watchers: list[threading.Thread] = []
        self._stop_event = threading.Event()

    def watch_pods(
        self,
        namespace: str,
        label_selector: str | None = None,
        timeout_seconds: int = 0,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._start_watch(
            list_func=self._client.core_v1.list_namespaced_pod,
            kwargs={"namespace": namespace, "label_selector": label_selector},
            timeout_seconds=timeout_seconds,
            callback=callback,
        )

    def watch_deployments(
        self,
        namespace: str,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._start_watch(
            list_func=self._client.apps_v1.list_namespaced_deployment,
            kwargs={"namespace": namespace},
            timeout_seconds=0,
            callback=callback,
        )

    def watch_nodes(
        self,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._start_watch(
            list_func=self._client.core_v1.list_node,
            kwargs={},
            timeout_seconds=0,
            callback=callback,
        )

    def watch_events(
        self,
        namespace: str,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._start_watch(
            list_func=self._client.core_v1.list_namespaced_event,
            kwargs={"namespace": namespace},
            timeout_seconds=0,
            callback=callback,
        )

    def watch_any(
        self,
        resource_type: str,
        namespace: str | None = None,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        _resource_map = {
            "pods": (
                self._client.core_v1.list_namespaced_pod,
                self._client.core_v1.list_pod_for_all_namespaces,
            ),
            "deployments": (
                self._client.apps_v1.list_namespaced_deployment,
                self._client.apps_v1.list_deployment_for_all_namespaces,
            ),
            "nodes": (None, self._client.core_v1.list_node),
        }
        resource_type_lower = resource_type.lower()
        if resource_type_lower not in _resource_map:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        namespaced_func, cluster_func = _resource_map[resource_type_lower]
        if namespace and namespaced_func:
            self._start_watch(
                list_func=namespaced_func,
                kwargs={"namespace": namespace},
                timeout_seconds=0,
                callback=callback,
            )
        else:
            self._start_watch(
                list_func=cluster_func,  # type: ignore[arg-type]  # bound method signature vs Callable[..., Any]
                kwargs={},
                timeout_seconds=0,
                callback=callback,
            )

    def stop_all(self) -> None:
        self._stop_event.set()
        self._logger.info("watcher_stop_all", count=len(self._watchers))

    def _start_watch(
        self,
        list_func: Callable[..., Any],
        kwargs: dict[str, Any],
        timeout_seconds: int,
        callback: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        from kubernetes import watch as k8s_watch  # type: ignore[attr-defined]

        stop_event = self._stop_event

        def _run() -> None:
            w = k8s_watch.Watch()
            try:
                stream_kwargs = {**kwargs}
                if timeout_seconds:
                    stream_kwargs["timeout_seconds"] = timeout_seconds
                for event in w.stream(list_func, **stream_kwargs):
                    if stop_event.is_set():
                        w.stop()
                        break
                    event_type: str = event.get("type", "")
                    obj = event.get("object", {})
                    if callback:
                        try:
                            raw = obj.to_dict() if hasattr(obj, "to_dict") else obj
                            callback(event_type, raw)
                        except Exception as exc:
                            self._logger.error("watcher_callback_error", error=str(exc))
            except Exception as exc:
                if not stop_event.is_set():
                    self._logger.error("watcher_error", error=str(exc))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        self._watchers.append(thread)


class HooksRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, dict[str, Callable[..., Any]]] = {}
        self._logger = get_logger(__name__)

    def register(self, event_type: str, handler: Callable[..., Any]) -> str:
        hook_id = str(uuid.uuid4())
        self._hooks.setdefault(event_type, {})[hook_id] = handler
        self._logger.info("hook_registered", event_type=event_type, hook_id=hook_id)
        return hook_id

    def unregister(self, hook_id: str) -> None:
        for event_type, hooks in self._hooks.items():
            if hook_id in hooks:
                del hooks[hook_id]
                self._logger.info(
                    "hook_unregistered", event_type=event_type, hook_id=hook_id
                )
                return

    def trigger(self, event_type: str, resource: dict[str, Any]) -> None:
        for hook_id, handler in list(self._hooks.get(event_type, {}).items()):
            try:
                handler(resource)
            except Exception as exc:
                self._logger.error(
                    "hook_trigger_error",
                    event_type=event_type,
                    hook_id=hook_id,
                    error=str(exc),
                )

    def list_hooks(self) -> dict[str, Any]:
        return {
            event_type: list(hooks.keys()) for event_type, hooks in self._hooks.items()
        }
