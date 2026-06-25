from __future__ import annotations

from typing import Any

from kubernetes.client import AuthorizationV1Api

from kube_orchestrator.core.client import KubeClient


class AccessValidator:
    def __init__(self, client: KubeClient | None = None) -> None:
        self._client = client or KubeClient.get_instance()

    def _auth_api(self) -> AuthorizationV1Api:
        return AuthorizationV1Api(self._client._api_client)

    def can_i(
        self,
        verb: str,
        resource: str,
        namespace: str | None = None,
        resource_name: str | None = None,
        subresource: str | None = None,
    ) -> bool:
        body: dict[str, Any] = {
            "apiVersion": "authorization.k8s.io/v1",
            "kind": "SelfSubjectAccessReview",
            "spec": {
                "resourceAttributes": {
                    "verb": verb,
                    "resource": resource,
                    "namespace": namespace,
                    "name": resource_name,
                    "subresource": subresource,
                }
            },
        }
        result = self._auth_api().create_self_subject_access_review(
            body  # type: ignore[arg-type]  # dict body accepted at runtime
        )
        return bool(result.status and result.status.allowed)

    def can_service_account(
        self,
        sa_name: str,
        sa_namespace: str,
        verb: str,
        resource: str,
        namespace: str | None = None,
    ) -> bool:
        body: dict[str, Any] = {
            "apiVersion": "authorization.k8s.io/v1",
            "kind": "SubjectAccessReview",
            "spec": {
                "user": f"system:serviceaccount:{sa_namespace}:{sa_name}",
                "resourceAttributes": {
                    "verb": verb,
                    "resource": resource,
                    "namespace": namespace,
                },
            },
        }
        result = self._auth_api().create_subject_access_review(
            body  # type: ignore[arg-type]  # dict body accepted at runtime
        )
        return bool(result.status and result.status.allowed)

    def list_permissions_for_subject(
        self,
        kind: str,
        name: str,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        rbac = self._client.rbac_v1
        permissions: dict[str, Any] = {"roles": [], "cluster_roles": []}

        if namespace:
            bindings = rbac.list_namespaced_role_binding(namespace)
            for rb in bindings.items:
                for subject in rb.subjects or []:
                    if subject.kind == kind and subject.name == name:
                        permissions["roles"].append(rb.role_ref.name)

        cluster_bindings = rbac.list_cluster_role_binding()
        for crb in cluster_bindings.items:
            for subject in crb.subjects or []:
                if subject.kind == kind and subject.name == name:
                    permissions["cluster_roles"].append(crb.role_ref.name)

        return permissions

    def check_rbac_coverage(
        self,
        namespace: str,
        required_permissions: list[dict[str, Any]],
    ) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for perm in required_permissions:
            key = f"{perm.get('verb')}:{perm.get('resource')}"
            results[key] = self.can_i(
                verb=perm.get("verb", ""),
                resource=perm.get("resource", ""),
                namespace=namespace,
            )
        return results

    def get_who_can(
        self, verb: str, resource: str, namespace: str
    ) -> list[dict[str, Any]]:
        rbac = self._client.rbac_v1
        subjects: list[dict[str, Any]] = []
        bindings = rbac.list_namespaced_role_binding(namespace)
        for rb in bindings.items:
            for subject in rb.subjects or []:
                subjects.append(
                    {
                        "kind": subject.kind,
                        "name": subject.name,
                        "namespace": getattr(subject, "namespace", None),
                        "role": rb.role_ref.name,
                    }
                )
        return subjects

    def audit_service_account(self, sa_name: str, namespace: str) -> dict[str, Any]:
        permissions = self.list_permissions_for_subject(
            "ServiceAccount", sa_name, namespace
        )
        common_checks = [
            ("get", "pods"),
            ("list", "pods"),
            ("create", "deployments"),
            ("delete", "secrets"),
            ("get", "secrets"),
        ]
        access: dict[str, bool] = {}
        for verb, resource in common_checks:
            access[f"{verb}:{resource}"] = self.can_service_account(
                sa_name, namespace, verb, resource, namespace
            )
        return {"permissions": permissions, "access_checks": access}
