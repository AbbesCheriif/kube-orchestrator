from __future__ import annotations

import os

from kubernetes.client import V1ConfigMap, V1ObjectMeta

from kube_orchestrator.resources.base import BaseResourceManager


class ConfigMapManager(BaseResourceManager[V1ConfigMap]):

    def _get_api(self):
        return self.client.core_v1()

    def _kind(self) -> str:
        return "ConfigMap"

    def _api_version(self) -> str:
        return "v1"

    def create_configmap(
        self,
        name: str,
        namespace: str,
        data: dict[str, str] | None = None,
        binary_data: dict[str, bytes] | None = None,
        immutable: bool = False,
        labels: dict | None = None,
        annotations: dict | None = None,
    ) -> V1ConfigMap:
        body = V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            metadata=V1ObjectMeta(
                name=name,
                namespace=namespace,
                labels=labels,
                annotations=annotations,
            ),
            data=data,
            binary_data=binary_data,
            immutable=immutable if immutable else None,
        )
        return self._get_api().create_namespaced_config_map(
            namespace=namespace, body=body, dry_run=self.dry_run
        )

    def create_from_file(
        self,
        name: str,
        namespace: str,
        file_paths: list[str],
        key_prefix: str | None = None,
    ) -> V1ConfigMap:
        data: dict[str, str] = {}
        for path in file_paths:
            key = (key_prefix or "") + os.path.basename(path)
            with open(path) as f:
                data[key] = f.read()
        return self.create_configmap(name=name, namespace=namespace, data=data)

    def create_from_directory(
        self,
        name: str,
        namespace: str,
        directory_path: str,
        recursive: bool = False,
    ) -> V1ConfigMap:
        data: dict[str, str] = {}
        for entry in os.scandir(directory_path):
            if entry.is_file():
                with open(entry.path) as f:
                    data[entry.name] = f.read()
            elif recursive and entry.is_dir():
                sub = self.create_from_directory(name, namespace, entry.path, recursive)
                data.update(sub.data or {})
        return self.create_configmap(name=name, namespace=namespace, data=data)

    def get_configmap(self, name: str, namespace: str) -> V1ConfigMap:
        return self._get_api().read_namespaced_config_map(name=name, namespace=namespace)

    def list_configmaps(
        self,
        namespace: str,
        label_selector: str | None = None,
    ) -> list[V1ConfigMap]:
        return self._get_api().list_namespaced_config_map(
            namespace=namespace, label_selector=label_selector
        ).items

    def update_configmap(
        self,
        name: str,
        namespace: str,
        data: dict,
        binary_data: dict | None = None,
    ) -> V1ConfigMap:
        cm = self.get_configmap(name, namespace)
        cm.data = data
        if binary_data is not None:
            cm.binary_data = binary_data
        return self._get_api().replace_namespaced_config_map(
            name=name, namespace=namespace, body=cm, dry_run=self.dry_run
        )

    def set_key(self, name: str, namespace: str, key: str, value: str) -> V1ConfigMap:
        cm = self.get_configmap(name, namespace)
        cm.data = cm.data or {}
        cm.data[key] = value
        return self._get_api().replace_namespaced_config_map(
            name=name, namespace=namespace, body=cm, dry_run=self.dry_run
        )

    def delete_key(self, name: str, namespace: str, key: str) -> V1ConfigMap:
        cm = self.get_configmap(name, namespace)
        if cm.data and key in cm.data:
            del cm.data[key]
        return self._get_api().replace_namespaced_config_map(
            name=name, namespace=namespace, body=cm, dry_run=self.dry_run
        )

    def get_value(self, name: str, namespace: str, key: str) -> str:
        cm = self.get_configmap(name, namespace)
        return (cm.data or {})[key]

    def delete_configmap(self, name: str, namespace: str) -> None:
        self._get_api().delete_namespaced_config_map(
            name=name, namespace=namespace, dry_run=self.dry_run
        )

    def set_immutable(self, name: str, namespace: str, immutable: bool) -> V1ConfigMap:
        cm = self.get_configmap(name, namespace)
        cm.immutable = immutable
        return self._get_api().replace_namespaced_config_map(
            name=name, namespace=namespace, body=cm, dry_run=self.dry_run
        )

    def build_volume_spec(
        self,
        name: str,
        items: list[dict] | None = None,
        default_mode: int | None = None,
        optional: bool = False,
    ) -> dict:
        spec: dict = {"configMap": {"name": name, "optional": optional}}
        if items:
            spec["configMap"]["items"] = items
        if default_mode is not None:
            spec["configMap"]["defaultMode"] = default_mode
        return spec

    def build_env_from_spec(
        self,
        name: str,
        prefix: str | None = None,
        optional: bool = False,
    ) -> dict:
        spec: dict = {"configMapRef": {"name": name, "optional": optional}}
        if prefix:
            spec["prefix"] = prefix
        return spec

    def build_env_key_ref(
        self,
        configmap_name: str,
        key: str,
        optional: bool = False,
    ) -> dict:
        return {
            "valueFrom": {
                "configMapKeyRef": {
                    "name": configmap_name,
                    "key": key,
                    "optional": optional,
                }
            }
        }
