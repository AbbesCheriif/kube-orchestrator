from __future__ import annotations

from typing import Any

from kubernetes.client import (
    RbacAuthorizationV1Api,
    V1ClusterRoleBinding,
    V1RoleBinding,
)

from kube_orchestrator.resources.base import BaseResourceManager


class RoleBindingManager(BaseResourceManager[V1RoleBinding]):
    def _get_api(self) -> RbacAuthorizationV1Api:
        return self.client.rbac_v1

    def _kind(self) -> str:
        return "RoleBinding"

    def _api_version(self) -> str:
        return "rbac.authorization.k8s.io/v1"

    def _resource_name(self) -> str:
        return "role_binding"

    def create_rolebinding(
        self,
        name: str,
        namespace: str,
        role_ref_kind: str,
        role_ref_name: str,
        subjects: list[dict[str, Any]],
        labels: dict[str, str] | None = None,
    ) -> V1RoleBinding:
        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": {"name": name, "namespace": namespace, "labels": labels or {}},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": role_ref_kind,
                "name": role_ref_name,
            },
            "subjects": subjects,
        }
        return self.create(manifest, namespace)

    def bind_service_account(
        self,
        name: str,
        namespace: str,
        role_name: str,
        service_account_name: str,
        service_account_namespace: str,
        role_kind: str = "Role",
    ) -> V1RoleBinding:
        subjects = [
            {
                "kind": "ServiceAccount",
                "name": service_account_name,
                "namespace": service_account_namespace,
            }
        ]
        return self.create_rolebinding(name, namespace, role_kind, role_name, subjects)

    def bind_user(
        self,
        name: str,
        namespace: str,
        role_name: str,
        username: str,
        role_kind: str = "Role",
    ) -> V1RoleBinding:
        subjects = [
            {"kind": "User", "name": username, "apiGroup": "rbac.authorization.k8s.io"}
        ]
        return self.create_rolebinding(name, namespace, role_kind, role_name, subjects)

    def bind_group(
        self,
        name: str,
        namespace: str,
        role_name: str,
        group_name: str,
        role_kind: str = "Role",
    ) -> V1RoleBinding:
        subjects = [
            {
                "kind": "Group",
                "name": group_name,
                "apiGroup": "rbac.authorization.k8s.io",
            }
        ]
        return self.create_rolebinding(name, namespace, role_kind, role_name, subjects)

    def get_rolebinding(self, name: str, namespace: str) -> V1RoleBinding:
        return self.get(name, namespace)

    def list_rolebindings(self, namespace: str) -> list[V1RoleBinding]:
        return self.list(namespace)

    def delete_rolebinding(self, name: str, namespace: str) -> None:
        self.delete(name, namespace)

    def add_subject(
        self, name: str, namespace: str, subject: dict[str, Any]
    ) -> V1RoleBinding:
        rb = self.get(name, namespace)
        subjects: list[Any] = rb.subjects or []
        subjects.append(subject)
        return self.patch(name, {"subjects": subjects}, namespace)

    def remove_subject(
        self, name: str, namespace: str, subject_name: str
    ) -> V1RoleBinding:
        rb = self.get(name, namespace)
        subjects = [s for s in (rb.subjects or []) if s.name != subject_name]
        return self.patch(name, {"subjects": subjects}, namespace)


class ClusterRoleBindingManager(BaseResourceManager[V1ClusterRoleBinding]):
    def _get_api(self) -> RbacAuthorizationV1Api:
        return self.client.rbac_v1

    def _kind(self) -> str:
        return "ClusterRoleBinding"

    def _api_version(self) -> str:
        return "rbac.authorization.k8s.io/v1"

    def create_clusterrolebinding(
        self,
        name: str,
        role_ref_name: str,
        subjects: list[dict[str, Any]],
        labels: dict[str, str] | None = None,
    ) -> V1ClusterRoleBinding:
        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": {"name": name, "labels": labels or {}},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": role_ref_name,
            },
            "subjects": subjects,
        }
        return self.create(manifest)

    def bind_service_account(
        self,
        name: str,
        role_ref_name: str,
        service_account_name: str,
        service_account_namespace: str,
        labels: dict[str, str] | None = None,
    ) -> V1ClusterRoleBinding:
        subjects = [
            {
                "kind": "ServiceAccount",
                "name": service_account_name,
                "namespace": service_account_namespace,
            }
        ]
        return self.create_clusterrolebinding(name, role_ref_name, subjects, labels)

    def bind_user(
        self,
        name: str,
        role_ref_name: str,
        username: str,
        labels: dict[str, str] | None = None,
    ) -> V1ClusterRoleBinding:
        subjects = [
            {"kind": "User", "name": username, "apiGroup": "rbac.authorization.k8s.io"}
        ]
        return self.create_clusterrolebinding(name, role_ref_name, subjects, labels)

    def bind_group(
        self,
        name: str,
        role_ref_name: str,
        group_name: str,
        labels: dict[str, str] | None = None,
    ) -> V1ClusterRoleBinding:
        subjects = [
            {
                "kind": "Group",
                "name": group_name,
                "apiGroup": "rbac.authorization.k8s.io",
            }
        ]
        return self.create_clusterrolebinding(name, role_ref_name, subjects, labels)

    def get_clusterrolebinding(self, name: str) -> V1ClusterRoleBinding:
        return self.get(name)

    def list_clusterrolebindings(self) -> list[V1ClusterRoleBinding]:
        return self.list()

    def delete_clusterrolebinding(self, name: str) -> None:
        self.delete(name)
