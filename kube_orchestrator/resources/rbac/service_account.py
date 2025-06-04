from __future__ import annotations

from kubernetes.client import V1LocalObjectReference, V1ObjectMeta, V1ServiceAccount

from kube_orchestrator.resources.base import BaseResourceManager


class ServiceAccountManager(BaseResourceManager[V1ServiceAccount]):

    def _get_api(self):
        return self.client.core_v1()

    def _kind(self) -> str:
        return "ServiceAccount"

    def _api_version(self) -> str:
        return "v1"

    def create_service_account(
        self,
        name: str,
        namespace: str,
        automount_token: bool = True,
        image_pull_secrets: list[str] | None = None,
        labels: dict | None = None,
        annotations: dict | None = None,
    ) -> V1ServiceAccount:
        body = V1ServiceAccount(
            api_version="v1",
            kind="ServiceAccount",
            metadata=V1ObjectMeta(
                name=name,
                namespace=namespace,
                labels=labels,
                annotations=annotations,
            ),
            automount_service_account_token=automount_token,
            image_pull_secrets=(
                [V1LocalObjectReference(name=s) for s in image_pull_secrets]
                if image_pull_secrets
                else None
            ),
        )
        return self._get_api().create_namespaced_service_account(
            namespace=namespace, body=body, dry_run=self.dry_run
        )

    def get_service_account(self, name: str, namespace: str) -> V1ServiceAccount:
        return self._get_api().read_namespaced_service_account(
            name=name, namespace=namespace
        )

    def list_service_accounts(
        self,
        namespace: str,
        label_selector: str | None = None,
    ) -> list[V1ServiceAccount]:
        return self._get_api().list_namespaced_service_account(
            namespace=namespace, label_selector=label_selector
        ).items

    def delete_service_account(self, name: str, namespace: str) -> None:
        self._get_api().delete_namespaced_service_account(
            name=name, namespace=namespace, dry_run=self.dry_run
        )

    def get_token(
        self,
        name: str,
        namespace: str,
        expiration_seconds: int | None = None,
        audiences: list[str] | None = None,
        bound_object_ref: dict | None = None,
    ) -> str:
        body: dict = {"spec": {}}
        if expiration_seconds:
            body["spec"]["expirationSeconds"] = expiration_seconds
        if audiences:
            body["spec"]["audiences"] = audiences
        if bound_object_ref:
            body["spec"]["boundObjectRef"] = bound_object_ref
        resp = self._get_api().create_namespaced_service_account_token(
            name=name, namespace=namespace, body=body
        )
        return resp.status.token

    def add_image_pull_secret(
        self, name: str, namespace: str, secret_name: str
    ) -> V1ServiceAccount:
        sa = self.get_service_account(name, namespace)
        sa.image_pull_secrets = sa.image_pull_secrets or []
        sa.image_pull_secrets.append(V1LocalObjectReference(name=secret_name))
        return self._get_api().replace_namespaced_service_account(
            name=name, namespace=namespace, body=sa, dry_run=self.dry_run
        )

    def remove_image_pull_secret(
        self, name: str, namespace: str, secret_name: str
    ) -> V1ServiceAccount:
        sa = self.get_service_account(name, namespace)
        sa.image_pull_secrets = [
            s for s in (sa.image_pull_secrets or []) if s.name != secret_name
        ]
        return self._get_api().replace_namespaced_service_account(
            name=name, namespace=namespace, body=sa, dry_run=self.dry_run
        )

    def set_automount(
        self, name: str, namespace: str, enabled: bool
    ) -> V1ServiceAccount:
        sa = self.get_service_account(name, namespace)
        sa.automount_service_account_token = enabled
        return self._get_api().replace_namespaced_service_account(
            name=name, namespace=namespace, body=sa, dry_run=self.dry_run
        )

    def get_secrets(self, name: str, namespace: str) -> list:
        sa = self.get_service_account(name, namespace)
        return sa.secrets or []
