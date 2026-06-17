from __future__ import annotations

import base64
import json

from kubernetes.client import V1ObjectMeta, V1Secret

from kube_orchestrator.resources.base import BaseResourceManager


class SecretManager(BaseResourceManager[V1Secret]):

    def _get_api(self):
        return self.client.core_v1

    def _kind(self) -> str:
        return "Secret"

    def _api_version(self) -> str:
        return "v1"

    def create_secret(
        self,
        name: str,
        namespace: str,
        string_data: dict[str, str] | None = None,
        data: dict[str, bytes] | None = None,
        secret_type: str = "Opaque",
        immutable: bool = False,
        labels: dict | None = None,
        annotations: dict | None = None,
    ) -> V1Secret:
        encoded: dict[str, str] | None = None
        if data:
            encoded = {k: base64.b64encode(v).decode() for k, v in data.items()}
        body = V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=V1ObjectMeta(
                name=name,
                namespace=namespace,
                labels=labels,
                annotations=annotations,
            ),
            string_data=string_data,
            data=encoded,
            type=secret_type,
            immutable=immutable if immutable else None,
        )
        return self._get_api().create_namespaced_secret(
            namespace=namespace, body=body, dry_run=self.dry_run
        )

    def create_opaque(
        self,
        name: str,
        namespace: str,
        data: dict[str, str],
        immutable: bool = False,
    ) -> V1Secret:
        return self.create_secret(
            name=name,
            namespace=namespace,
            string_data=data,
            secret_type="Opaque",
            immutable=immutable,
        )

    def create_tls_secret(
        self,
        name: str,
        namespace: str,
        cert_path: str,
        key_path: str,
    ) -> V1Secret:
        with open(cert_path) as f:
            cert = f.read()
        with open(key_path) as f:
            key = f.read()
        return self.create_secret(
            name=name,
            namespace=namespace,
            string_data={"tls.crt": cert, "tls.key": key},
            secret_type="kubernetes.io/tls",
        )

    def create_docker_registry_secret(
        self,
        name: str,
        namespace: str,
        server: str,
        username: str,
        password: str,
        email: str | None = None,
    ) -> V1Secret:
        auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        docker_config: dict = {
            "auths": {
                server: {
                    "username": username,
                    "password": password,
                    "auth": auth,
                }
            }
        }
        if email:
            docker_config["auths"][server]["email"] = email
        return self.create_secret(
            name=name,
            namespace=namespace,
            string_data={".dockerconfigjson": json.dumps(docker_config)},
            secret_type="kubernetes.io/dockerconfigjson",
        )

    def create_basic_auth_secret(
        self,
        name: str,
        namespace: str,
        username: str,
        password: str,
    ) -> V1Secret:
        return self.create_secret(
            name=name,
            namespace=namespace,
            string_data={"username": username, "password": password},
            secret_type="kubernetes.io/basic-auth",
        )

    def create_ssh_auth_secret(
        self,
        name: str,
        namespace: str,
        private_key_path: str,
    ) -> V1Secret:
        with open(private_key_path) as f:
            key = f.read()
        return self.create_secret(
            name=name,
            namespace=namespace,
            string_data={"ssh-privatekey": key},
            secret_type="kubernetes.io/ssh-auth",
        )

    def get_secret(self, name: str, namespace: str) -> V1Secret:
        return self._get_api().read_namespaced_secret(name=name, namespace=namespace)

    def list_secrets(
        self,
        namespace: str,
        label_selector: str | None = None,
        secret_type: str | None = None,
    ) -> list[V1Secret]:
        items = self._get_api().list_namespaced_secret(
            namespace=namespace, label_selector=label_selector
        ).items
        if secret_type:
            items = [s for s in items if s.type == secret_type]
        return items

    def get_decoded_value(self, name: str, namespace: str, key: str) -> str:
        secret = self.get_secret(name, namespace)
        raw = (secret.data or {})[key]
        return base64.b64decode(raw).decode()

    def update_secret(
        self,
        name: str,
        namespace: str,
        string_data: dict,
    ) -> V1Secret:
        secret = self.get_secret(name, namespace)
        secret.string_data = string_data
        return self._get_api().replace_namespaced_secret(
            name=name, namespace=namespace, body=secret, dry_run=self.dry_run
        )

    def set_key(self, name: str, namespace: str, key: str, value: str) -> V1Secret:
        secret = self.get_secret(name, namespace)
        encoded = base64.b64encode(value.encode()).decode()
        secret.data = secret.data or {}
        secret.data[key] = encoded
        return self._get_api().replace_namespaced_secret(
            name=name, namespace=namespace, body=secret, dry_run=self.dry_run
        )

    def delete_key(self, name: str, namespace: str, key: str) -> V1Secret:
        secret = self.get_secret(name, namespace)
        if secret.data and key in secret.data:
            del secret.data[key]
        return self._get_api().replace_namespaced_secret(
            name=name, namespace=namespace, body=secret, dry_run=self.dry_run
        )

    def delete_secret(self, name: str, namespace: str) -> None:
        self._get_api().delete_namespaced_secret(
            name=name, namespace=namespace, dry_run=self.dry_run
        )

    def set_immutable(self, name: str, namespace: str, immutable: bool) -> V1Secret:
        secret = self.get_secret(name, namespace)
        secret.immutable = immutable
        return self._get_api().replace_namespaced_secret(
            name=name, namespace=namespace, body=secret, dry_run=self.dry_run
        )

    def build_volume_spec(
        self,
        name: str,
        items: list[dict] | None = None,
        default_mode: int | None = None,
        optional: bool = False,
    ) -> dict:
        spec: dict = {"secret": {"secretName": name, "optional": optional}}
        if items:
            spec["secret"]["items"] = items
        if default_mode is not None:
            spec["secret"]["defaultMode"] = default_mode
        return spec

    def build_env_from_spec(
        self,
        name: str,
        prefix: str | None = None,
        optional: bool = False,
    ) -> dict:
        spec: dict = {"secretRef": {"name": name, "optional": optional}}
        if prefix:
            spec["prefix"] = prefix
        return spec

    def build_env_key_ref(
        self,
        secret_name: str,
        key: str,
        optional: bool = False,
    ) -> dict:
        return {
            "valueFrom": {
                "secretKeyRef": {
                    "name": secret_name,
                    "key": key,
                    "optional": optional,
                }
            }
        }
