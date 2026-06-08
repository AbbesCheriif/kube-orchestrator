from __future__ import annotations

import time

from kubernetes.client import V1PersistentVolumeClaim

from kube_orchestrator.resources.base import BaseResourceManager


class PVCManager(BaseResourceManager[V1PersistentVolumeClaim]):

    def _get_api(self):
        return self.client.core_v1()

    def _kind(self) -> str:
        return "PersistentVolumeClaim"

    def _api_version(self) -> str:
        return "v1"

    def create_pvc(
        self,
        name: str,
        namespace: str,
        access_modes: list[str],
        storage_request: str,
        storage_class_name: str | None = None,
        volume_mode: str = "Filesystem",
        volume_name: str | None = None,
        selector: dict | None = None,
        data_source: dict | None = None,
        data_source_ref: dict | None = None,
        storage_limit: str | None = None,
        labels: dict | None = None,
    ) -> V1PersistentVolumeClaim:
        resources: dict = {"requests": {"storage": storage_request}}
        if storage_limit:
            resources["limits"] = {"storage": storage_limit}

        spec: dict = {
            "accessModes": access_modes,
            "resources": resources,
            "volumeMode": volume_mode,
        }
        if storage_class_name is not None:
            spec["storageClassName"] = storage_class_name
        if volume_name:
            spec["volumeName"] = volume_name
        if selector:
            spec["selector"] = selector
        if data_source:
            spec["dataSource"] = data_source
        if data_source_ref:
            spec["dataSourceRef"] = data_source_ref

        body = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels or {},
            },
            "spec": spec,
        }
        return self._get_api().create_namespaced_persistent_volume_claim(
            namespace=namespace, body=body, dry_run=self.dry_run
        )

    def get_pvc(self, name: str, namespace: str) -> V1PersistentVolumeClaim:
        return self._get_api().read_namespaced_persistent_volume_claim(
            name=name, namespace=namespace
        )

    def list_pvcs(
        self,
        namespace: str,
        label_selector: str | None = None,
        phase: str | None = None,
    ) -> list[V1PersistentVolumeClaim]:
        items = self._get_api().list_namespaced_persistent_volume_claim(
            namespace=namespace, label_selector=label_selector
        ).items
        if phase:
            items = [pvc for pvc in items if pvc.status and pvc.status.phase == phase]
        return items

    def delete_pvc(self, name: str, namespace: str, wait: bool = False) -> None:
        self._get_api().delete_namespaced_persistent_volume_claim(
            name=name, namespace=namespace, dry_run=self.dry_run
        )
        if wait:
            deadline = time.time() + 120
            while time.time() < deadline:
                try:
                    self.get_pvc(name, namespace)
                    time.sleep(2)
                except Exception:
                    break

    def get_phase(self, name: str, namespace: str) -> str:
        pvc = self.get_pvc(name, namespace)
        return pvc.status.phase if pvc.status else "Unknown"

    def get_bound_pv(self, name: str, namespace: str) -> str | None:
        pvc = self.get_pvc(name, namespace)
        return pvc.spec.volume_name if pvc.spec else None

    def wait_for_bound(
        self, name: str, namespace: str, timeout_seconds: int = 60
    ) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.get_phase(name, namespace) == "Bound":
                return True
            time.sleep(2)
        return False

    def expand(
        self, name: str, namespace: str, new_storage: str
    ) -> V1PersistentVolumeClaim:
        pvc = self.get_pvc(name, namespace)
        pvc.spec.resources.requests["storage"] = new_storage
        return self._get_api().replace_namespaced_persistent_volume_claim(
            name=name, namespace=namespace, body=pvc, dry_run=self.dry_run
        )

    def get_capacity(self, name: str, namespace: str) -> str:
        pvc = self.get_pvc(name, namespace)
        if pvc.status and pvc.status.capacity:
            return pvc.status.capacity.get("storage", "")
        return ""

    def get_used_by_pods(self, name: str, namespace: str) -> list:
        pods = self.client.core_v1().list_namespaced_pod(namespace=namespace).items
        result = []
        for pod in pods:
            if not pod.spec or not pod.spec.volumes:
                continue
            for vol in pod.spec.volumes:
                if (
                    vol.persistent_volume_claim
                    and vol.persistent_volume_claim.claim_name == name
                ):
                    result.append(pod)
                    break
        return result
