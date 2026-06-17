"""PodManager — full lifecycle management for Kubernetes Pods."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any

from kubernetes import client, watch
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import ResourceNotFoundError, parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder


class PodManager(BaseResourceManager[client.V1Pod]):
    """Full lifecycle manager for Kubernetes Pods."""

    def __init__(
        self,
        kube_client: "KubeClient | None" = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.CoreV1Api:
        return self.client.core_v1

    def _kind(self) -> str:
        return "Pod"

    def _api_version(self) -> str:
        return "v1"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_pod(
        self,
        builder: PodBuilder | None = None,
        manifest: dict | None = None,
        namespace: str | None = None,
    ) -> client.V1Pod:
        body = builder.build() if builder else manifest
        ns = namespace or self.default_namespace
        body.setdefault("metadata", {})["namespace"] = ns
        return self.create(body, ns)

    def get_pod(self, name: str, namespace: str | None = None) -> client.V1Pod:
        return self.get(name, namespace)

    def list_pods(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
        field_selector: str | None = None,
        node_name: str | None = None,
    ) -> list[client.V1Pod]:
        if node_name:
            node_field = f"spec.nodeName={node_name}"
            field_selector = (
                f"{field_selector},{node_field}" if field_selector else node_field
            )
        return self.list(namespace, label_selector, field_selector)

    def delete_pod(
        self,
        name: str,
        namespace: str | None = None,
        grace_period_seconds: int | None = None,
    ) -> None:
        self.delete(name, namespace, grace_period_seconds)

    # ------------------------------------------------------------------
    # Exec and logs
    # ------------------------------------------------------------------

    def exec_command(
        self,
        name: str,
        namespace: str | None = None,
        container: str | None = None,
        command: list[str] | None = None,
        stdin: bool = False,
        tty: bool = False,
    ) -> str:
        ns = namespace or self.default_namespace
        kwargs: dict[str, Any] = {
            "command": command or [],
            "stderr": True,
            "stdin": stdin,
            "stdout": True,
            "tty": tty,
        }
        if container:
            kwargs["container"] = container
        try:
            return stream(
                self.client.core_v1.connect_get_namespaced_pod_exec,
                name,
                ns,
                **kwargs,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def stream_logs(
        self,
        name: str,
        namespace: str | None = None,
        container: str | None = None,
        tail_lines: int | None = None,
        since_seconds: int | None = None,
        timestamps: bool = False,
        follow: bool = False,
    ) -> Iterator[str]:
        ns = namespace or self.default_namespace
        kwargs: dict[str, Any] = {
            "timestamps": timestamps,
            "follow": follow,
            "_preload_content": False,
        }
        if container:
            kwargs["container"] = container
        if tail_lines:
            kwargs["tail_lines"] = tail_lines
        if since_seconds:
            kwargs["since_seconds"] = since_seconds
        try:
            resp = self.client.core_v1.read_namespaced_pod_log(name, ns, **kwargs)
            for line in resp:
                yield line.decode("utf-8", errors="replace").rstrip("\n")
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_phase(self, name: str, namespace: str | None = None) -> str:
        pod = self.get_pod(name, namespace)
        return (pod.status and pod.status.phase) or "Unknown"

    def is_ready(self, name: str, namespace: str | None = None) -> bool:
        pod = self.get_pod(name, namespace)
        if not pod.status or not pod.status.conditions:
            return False
        return any(
            c.type == "Ready" and c.status == "True"
            for c in pod.status.conditions
        )

    def get_container_status(
        self,
        name: str,
        namespace: str | None = None,
        container: str = "",
    ) -> dict:
        pod = self.get_pod(name, namespace)
        if not pod.status or not pod.status.container_statuses:
            return {}
        for cs in pod.status.container_statuses:
            if not container or cs.name == container:
                return {
                    "name": cs.name,
                    "ready": cs.ready,
                    "restart_count": cs.restart_count,
                    "image": cs.image,
                    "state": str(cs.state),
                }
        return {}

    def wait_for_running(
        self,
        name: str,
        namespace: str | None = None,
        timeout_seconds: int = 120,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                if self.get_phase(name, namespace) == "Running":
                    return True
            except ResourceNotFoundError:
                pass
            time.sleep(2)
        return False

    def wait_for_completion(
        self,
        name: str,
        namespace: str | None = None,
        timeout_seconds: int = 300,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                phase = self.get_phase(name, namespace)
                if phase in ("Succeeded", "Failed"):
                    return phase == "Succeeded"
            except ResourceNotFoundError:
                pass
            time.sleep(2)
        return False

    def watch_status(
        self,
        name: str,
        namespace: str | None = None,
        timeout_seconds: int = 60,
        callback: Callable[[str, client.V1Pod], None] | None = None,
    ) -> None:
        ns = namespace or self.default_namespace
        w = watch.Watch()
        for event in w.stream(
            self.client.core_v1.list_namespaced_pod,
            namespace=ns,
            field_selector=f"metadata.name={name}",
            timeout_seconds=timeout_seconds,
        ):
            if callback:
                callback(event["type"], event["object"])

    # ------------------------------------------------------------------
    # Advanced operations
    # ------------------------------------------------------------------

    def get_resource_usage(self, name: str, namespace: str | None = None) -> dict:
        ns = namespace or self.default_namespace
        try:
            return self.client.custom_objects.get_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=ns,
                plural="pods",
                name=name,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Filtered list helpers
    # ------------------------------------------------------------------

    def list_pods_by_phase(
        self,
        phase: str,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1Pod]:
        field_selector = f"status.phase={phase}"
        return self.list_pods(namespace, label_selector, field_selector)

    def list_running_pods(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1Pod]:
        return self.list_pods_by_phase("Running", namespace, label_selector)

    def list_failed_pods(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1Pod]:
        return self.list_pods_by_phase("Failed", namespace, label_selector)

    def list_pending_pods(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1Pod]:
        return self.list_pods_by_phase("Pending", namespace, label_selector)

    def list_pods_on_node(
        self,
        node_name: str,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1Pod]:
        return self.list_pods(namespace, label_selector, node_name=node_name)

    def attach_ephemeral_container(
        self,
        name: str,
        namespace: str | None = None,
        container: dict | None = None,
    ) -> client.V1Pod:
        ns = namespace or self.default_namespace
        pod = self.get_pod(name, ns)
        existing = list(pod.spec.ephemeral_containers or [])
        existing.append(container or {})
        body = client.V1Pod(spec=client.V1PodSpec(ephemeral_containers=existing))
        try:
            return self.client.core_v1.patch_namespaced_pod_ephemeralcontainers(
                name=name, namespace=ns, body=body
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc
