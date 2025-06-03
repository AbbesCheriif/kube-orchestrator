from __future__ import annotations

import time

from kubernetes.client import V1ObjectMeta, V1PersistentVolume

from kube_orchestrator.resources.base import BaseResourceManager


class PersistentVolumeManager(BaseResourceManager[V1PersistentVolume]):

    def _get_api(self):
        return self.client.core_v1()

    def _kind(self) -> str:
        return "PersistentVolume"

    def _api_version(self) -> str:
        return "v1"

    def create_pv(
        self,
        name: str,
        capacity_storage: str,
        access_modes: list[str],
        reclaim_policy: str = "Retain",
        storage_class_name: str | None = None,
        volume_mode: str = "Filesystem",
        nfs: dict | None = None,
        host_path: dict | None = None,
        csi: dict | None = None,
        local: dict | None = None,
        node_affinity: dict | None = None,
        mount_options: list[str] | None = None,
        claim_ref: dict | None = None,
        labels: dict | None = None,
    ) -> V1PersistentVolume:
        spec: dict = {
            "capacity": {"storage": capacity_storage},
            "accessModes": access_modes,
            "persistentVolumeReclaimPolicy": reclaim_policy,
            "volumeMode": volume_mode,
        }
        if storage_class_name:
            spec["storageClassName"] = storage_class_name
        if nfs:
            spec["nfs"] = nfs
        if host_path:
            spec["hostPath"] = host_path
        if csi:
            spec["csi"] = csi
        if local:
            spec["local"] = local
        if node_affinity:
            spec["nodeAffinity"] = node_affinity
        if mount_options:
            spec["mountOptions"] = mount_options
        if claim_ref:
            spec["claimRef"] = claim_ref

        body = {
            "apiVersion": "v1",
            "kind": "PersistentVolume",
            "metadata": {"name": name, "labels": labels or {}},
            "spec": spec,
        }
        return self._get_api().create_persistent_volume(body=body, dry_run=self.dry_run)

    def get_pv(self, name: str) -> V1PersistentVolume:
        return self._get_api().read_persistent_volume(name=name)

    def list_pvs(
        self,
        label_selector: str | None = None,
        phase: str | None = None,
    ) -> list[V1PersistentVolume]:
        items = self._get_api().list_persistent_volume(
            label_selector=label_selector
        ).items
        if phase:
            items = [pv for pv in items if pv.status and pv.status.phase == phase]
        return items

    def delete_pv(self, name: str) -> None:
        self._get_api().delete_persistent_volume(name=name, dry_run=self.dry_run)

    def get_phase(self, name: str) -> str:
        pv = self.get_pv(name)
        return pv.status.phase if pv.status else "Unknown"

    def get_bound_pvc(self, name: str) -> str | None:
        pv = self.get_pv(name)
        ref = pv.spec.claim_ref if pv.spec else None
        if ref:
            return f"{ref.namespace}/{ref.name}"
        return None

    def list_available_pvs(self) -> list[V1PersistentVolume]:
        return self.list_pvs(phase="Available")

    def list_by_storage_class(self, sc_name: str) -> list[V1PersistentVolume]:
        return [pv for pv in self.list_pvs() if pv.spec.storage_class_name == sc_name]

    def wait_for_available(self, name: str, timeout_seconds: int = 60) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.get_phase(name) == "Available":
                return True
            time.sleep(2)
        return False

    def wait_for_released(self, name: str, timeout_seconds: int = 60) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.get_phase(name) == "Released":
                return True
            time.sleep(2)
        return False
