from __future__ import annotations

from typing import Any

from kubernetes.client import StorageV1Api, V1ObjectMeta, V1StorageClass

from kube_orchestrator.core.exceptions import ResourceNotFoundError
from kube_orchestrator.resources.base import BaseResourceManager


class StorageClassManager(BaseResourceManager[V1StorageClass]):

    def _get_api(self) -> StorageV1Api:
        return self.client.storage_v1

    def _resource_name(self) -> str:
        return "storage_class"

    def _kind(self) -> str:
        return "StorageClass"

    def _api_version(self) -> str:
        return "storage.k8s.io/v1"

    def create_storage_class(
        self,
        name: str,
        provisioner: str,
        parameters: dict[str, Any] | None = None,
        reclaim_policy: str = "Delete",
        volume_binding_mode: str = "Immediate",
        allow_volume_expansion: bool = False,
        mount_options: list[str] | None = None,
        allowed_topologies: list[dict[str, Any]] | None = None,
        labels: dict[str, Any] | None = None,
        annotations: dict[str, Any] | None = None,
    ) -> V1StorageClass:
        body = V1StorageClass(
            api_version="storage.k8s.io/v1",
            kind="StorageClass",
            metadata=V1ObjectMeta(name=name, labels=labels, annotations=annotations),
            provisioner=provisioner,
            parameters=parameters,
            reclaim_policy=reclaim_policy,
            volume_binding_mode=volume_binding_mode,
            allow_volume_expansion=allow_volume_expansion,
            mount_options=mount_options,
            allowed_topologies=allowed_topologies,  # type: ignore[arg-type]  # plain dicts accepted at runtime
        )
        return self._get_api().create_storage_class(body=body, dry_run=self.dry_run)

    def get_storage_class(self, name: str) -> V1StorageClass:
        return self._get_api().read_storage_class(name=name)

    def list_storage_classes(self) -> list[V1StorageClass]:
        return self._get_api().list_storage_class().items

    def delete_storage_class(self, name: str) -> None:
        self._get_api().delete_storage_class(name=name, dry_run=self.dry_run)

    def set_as_default(self, name: str) -> V1StorageClass:
        sc = self.get_storage_class(name)
        if sc.metadata is None:
            raise ResourceNotFoundError(self._kind(), name, "")
        sc.metadata.annotations = sc.metadata.annotations or {}
        sc.metadata.annotations["storageclass.kubernetes.io/is-default-class"] = "true"
        return self._get_api().replace_storage_class(
            name=name, body=sc, dry_run=self.dry_run
        )

    def unset_default(self, name: str) -> V1StorageClass:
        sc = self.get_storage_class(name)
        if sc.metadata and sc.metadata.annotations:
            sc.metadata.annotations.pop(
                "storageclass.kubernetes.io/is-default-class", None
            )
        return self._get_api().replace_storage_class(
            name=name, body=sc, dry_run=self.dry_run
        )

    def get_default(self) -> V1StorageClass | None:
        for sc in self.list_storage_classes():
            ann = (sc.metadata and sc.metadata.annotations) or {}
            if ann.get("storageclass.kubernetes.io/is-default-class") == "true":
                return sc
        return None

    def update_reclaim_policy(self, name: str, policy: str) -> V1StorageClass:
        sc = self.get_storage_class(name)
        sc.reclaim_policy = policy
        return self._get_api().replace_storage_class(
            name=name, body=sc, dry_run=self.dry_run
        )

    def get_pvs_using(self, name: str) -> list[Any]:
        pvs = self.client.core_v1.list_persistent_volume().items
        return [pv for pv in pvs if pv.spec and pv.spec.storage_class_name == name]
