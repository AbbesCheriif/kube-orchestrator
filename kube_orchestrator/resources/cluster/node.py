from __future__ import annotations

from typing import Any

from kubernetes.client import CoreV1Api, V1Node, V1Pod

from kube_orchestrator.resources.base import BaseResourceManager


class NodeManager(BaseResourceManager[V1Node]):
    def _get_api(self) -> CoreV1Api:
        return self.client.core_v1()

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
        info = node.status.node_info
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
            for c in (node.status.conditions or [])
        ]

    def is_ready(self, name: str) -> bool:
        for cond in self.get_conditions(name):
            if cond["type"] == "Ready":
                return cond["status"] == "True"
        return False

    def get_allocatable(self, name: str) -> dict[str, str]:
        node = self.get_node(name)
        return dict(node.status.allocatable or {})

    def get_capacity(self, name: str) -> dict[str, str]:
        node = self.get_node(name)
        return dict(node.status.capacity or {})

    def get_addresses(self, name: str) -> dict[str, str | None]:
        node = self.get_node(name)
        result: dict[str, str | None] = {
            "internal_ip": None,
            "external_ip": None,
            "hostname": None,
        }
        for addr in node.status.addresses or []:
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
            for img in (node.status.images or [])
        ]

    def is_schedulable(self, name: str) -> bool:
        node = self.get_node(name)
        return not bool(node.spec.unschedulable)

    def get_pods(self, name: str) -> list[V1Pod]:
        result = self.client.core_v1().list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={name}"
        )
        return result.items

    def get_labels(self, name: str) -> dict[str, str]:
        node = self.get_node(name)
        return dict(node.metadata.labels or {})

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
            for container in pod.spec.containers or []:
                if container.resources and container.resources.requests:
                    cpu_req += _parse_cpu(
                        container.resources.requests.get("cpu", "0")
                    )
                    mem_req += _parse_memory(
                        container.resources.requests.get("memory", "0")
                    )
        return {
            "pod_count": len(pods),
            "cpu_requested_millicores": cpu_req,
            "memory_requested_bytes": mem_req,
        }


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
