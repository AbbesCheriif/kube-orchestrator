from __future__ import annotations

from typing import Any

from kubernetes.client import CoreV1Api, V1Node, V1Pod

from kube_orchestrator.resources.base import BaseResourceManager


class NodeManager(BaseResourceManager[V1Node]):
    def _get_api(self) -> CoreV1Api:
        return self.client.core_v1

    def _kind(self) -> str:
        return "Node"

    def _api_version(self) -> str:
        return "v1"

    def list_nodes(
        self,
        label_selector: str | None = None,
        field_selector: str | None = None,
    ) -> list[V1Node]:
        return self.list(
            label_selector=label_selector,
            field_selector=field_selector,
        )

    def get_node(self, name: str) -> V1Node:
        return self.get(name)

    def get_node_info(self, name: str) -> dict[str, str]:
        node = self.get_node(name)
        info = node.status.node_info if node.status else None
        if info is None:
            return {}
        return {
            "architecture": info.architecture,
            "os_image": info.os_image,
            "kernel_version": info.kernel_version,
            "kubelet_version": info.kubelet_version,
            "container_runtime_version": info.container_runtime_version,
            "machine_id": info.machine_id,
            "system_uuid": info.system_uuid,
            "boot_id": info.boot_id,
            "operating_system": info.operating_system,
        }

    def get_conditions(self, name: str) -> list[dict[str, Any]]:
        node = self.get_node(name)
        return [
            {
                "type": c.type,
                "status": c.status,
                "reason": c.reason,
                "message": c.message,
                "last_transition_time": str(c.last_transition_time),
            }
            for c in ((node.status.conditions if node.status else None) or [])
        ]

    def is_ready(self, name: str) -> bool:
        for cond in self.get_conditions(name):
            if cond["type"] == "Ready":
                return bool(cond["status"] == "True")
        return False

    def get_allocatable(self, name: str) -> dict[str, str]:
        node = self.get_node(name)
        return dict((node.status.allocatable if node.status else None) or {})

    def get_capacity(self, name: str) -> dict[str, str]:
        node = self.get_node(name)
        return dict((node.status.capacity if node.status else None) or {})

    def get_addresses(self, name: str) -> dict[str, str | None]:
        node = self.get_node(name)
        result: dict[str, str | None] = {
            "internal_ip": None,
            "external_ip": None,
            "hostname": None,
        }
        for addr in (node.status.addresses if node.status else None) or []:
            if addr.type == "InternalIP":
                result["internal_ip"] = addr.address
            elif addr.type == "ExternalIP":
                result["external_ip"] = addr.address
            elif addr.type == "Hostname":
                result["hostname"] = addr.address
        return result

    def get_images(self, name: str) -> list[dict[str, Any]]:
        node = self.get_node(name)
        return [
            {"names": img.names, "size_bytes": img.size_bytes}
            for img in ((node.status.images if node.status else None) or [])
        ]

    def is_schedulable(self, name: str) -> bool:
        node = self.get_node(name)
        return not bool(node.spec and node.spec.unschedulable)

    def get_pods(self, name: str) -> list[V1Pod]:
        result = self.client.core_v1.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={name}"
        )
        return result.items

    def get_labels(self, name: str) -> dict[str, str]:
        node = self.get_node(name)
        return dict((node.metadata.labels if node.metadata else None) or {})

    def set_label(self, name: str, key: str, value: str) -> V1Node:
        return self.patch(name, {"metadata": {"labels": {key: value}}})

    def remove_label(self, name: str, key: str) -> V1Node:
        return self.patch(name, {"metadata": {"labels": {key: None}}})

    def set_annotation(self, name: str, key: str, value: str) -> V1Node:
        return self.patch(name, {"metadata": {"annotations": {key: value}}})

    def get_resource_usage(self, name: str) -> dict[str, Any]:
        pods = self.get_pods(name)
        cpu_req = 0
        mem_req = 0
        for pod in pods:
            for container in (pod.spec.containers if pod.spec else None) or []:
                if container.resources and container.resources.requests:
                    cpu_req += _parse_cpu(container.resources.requests.get("cpu", "0"))
                    mem_req += _parse_memory(
                        container.resources.requests.get("memory", "0")
                    )
        return {
            "pod_count": len(pods),
            "cpu_requested_millicores": cpu_req,
            "memory_requested_bytes": mem_req,
        }

    def cordon(self, name: str) -> V1Node:
        return self.patch(name, {"spec": {"unschedulable": True}})

    def uncordon(self, name: str) -> V1Node:
        return self.patch(name, {"spec": {"unschedulable": False}})

    def drain(
        self,
        name: str,
        ignore_daemonsets: bool = True,
        delete_emptydir_data: bool = False,
        force: bool = False,
        grace_period_seconds: int | None = None,
        timeout_seconds: int = 300,
        dry_run: bool = False,
    ) -> list[str]:
        self.cordon(name)
        pods = self.get_pods(name)
        evicted: list[str] = []
        for pod in pods:
            if (
                pod.metadata is None
                or not pod.metadata.name
                or not pod.metadata.namespace
            ):
                continue
            owner_kinds = [ref.kind for ref in (pod.metadata.owner_references or [])]
            if "DaemonSet" in owner_kinds and ignore_daemonsets:
                continue
            if not force and not owner_kinds:
                continue
            if not dry_run:
                self.evict_pod(
                    pod.metadata.name,
                    pod.metadata.namespace,
                    grace_period_seconds,
                )
            evicted.append(f"{pod.metadata.namespace}/{pod.metadata.name}")
        return evicted

    def evict_pod(
        self,
        pod_name: str,
        namespace: str,
        grace_period_seconds: int | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "apiVersion": "policy/v1",
            "kind": "Eviction",
            "metadata": {"name": pod_name, "namespace": namespace},
        }
        if grace_period_seconds is not None:
            body["deleteOptions"] = {"gracePeriodSeconds": grace_period_seconds}
        self.client.core_v1.create_namespaced_pod_eviction(
            pod_name,
            namespace,
            body,  # type: ignore[arg-type]  # dict body accepted at runtime
        )

    def wait_for_drain(self, name: str, timeout_seconds: int = 300) -> bool:
        import time

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            pods = self.get_pods(name)
            non_daemon = [
                p
                for p in pods
                if "DaemonSet"
                not in [
                    r.kind
                    for r in (
                        (p.metadata.owner_references if p.metadata else None) or []
                    )
                ]
            ]
            if not non_daemon:
                return True
            time.sleep(5)
        return False

    def get_cordoned_nodes(self) -> list[V1Node]:
        return [n for n in self.list_nodes() if bool(n.spec and n.spec.unschedulable)]

    # ── Taint management ────────────────────────────────────────────────

    def add_taint(
        self,
        name: str,
        key: str,
        value: str | None,
        effect: str,
    ) -> V1Node:
        node = self.get_node(name)
        taints: list[dict[str, Any]] = [
            {"key": t.key, "value": t.value, "effect": t.effect}
            for t in ((node.spec.taints if node.spec else None) or [])
            if not (t.key == key and t.effect == effect)
        ]
        taint: dict[str, Any] = {"key": key, "effect": effect}
        if value is not None:
            taint["value"] = value
        taints.append(taint)
        return self.patch(name, {"spec": {"taints": taints}})

    def remove_taint(self, name: str, key: str, effect: str | None = None) -> V1Node:
        node = self.get_node(name)
        taints = [
            {"key": t.key, "value": t.value, "effect": t.effect}
            for t in ((node.spec.taints if node.spec else None) or [])
            if not (t.key == key and (effect is None or t.effect == effect))
        ]
        return self.patch(name, {"spec": {"taints": taints}})

    def get_taints(self, name: str) -> list[dict[str, Any]]:
        node = self.get_node(name)
        return [
            {"key": t.key, "value": t.value, "effect": t.effect}
            for t in ((node.spec.taints if node.spec else None) or [])
        ]

    def has_taint(self, name: str, key: str, effect: str | None = None) -> bool:
        for taint in self.get_taints(name):
            if taint["key"] == key and (effect is None or taint["effect"] == effect):
                return True
        return False

    def list_nodes_with_taint(
        self, key: str, effect: str | None = None
    ) -> list[V1Node]:
        return [
            n
            for n in self.list_nodes()
            if n.metadata
            and n.metadata.name
            and self.has_taint(n.metadata.name, key, effect)
        ]

    def remove_all_taints(self, name: str) -> V1Node:
        return self.patch(name, {"spec": {"taints": []}})


def _parse_cpu(value: str) -> int:
    if value.endswith("m"):
        return int(value[:-1])
    try:
        return int(float(value) * 1000)
    except ValueError:
        return 0


def _parse_memory(value: str) -> int:
    units = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4}
    for suffix, multiplier in units.items():
        if value.endswith(suffix):
            return int(value[: -len(suffix)]) * multiplier
    try:
        return int(value)
    except ValueError:
        return 0
