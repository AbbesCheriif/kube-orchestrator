"""PodDisruptionBudgetManager — full lifecycle management for Kubernetes PDBs."""

from __future__ import annotations

from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class PodDisruptionBudgetManager(BaseResourceManager[client.V1PodDisruptionBudget]):
    """Manage Kubernetes PodDisruptionBudget resources (namespace-scoped)."""

    def __init__(
        self,
        kube_client: "KubeClient | None" = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.PolicyV1Api:
        return self.client.policy_v1

    def _kind(self) -> str:
        return "PodDisruptionBudget"

    def _api_version(self) -> str:
        return "policy/v1"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_pdb(
        self,
        name: str,
        namespace: str | None = None,
        selector: dict | None = None,
        min_available: int | str | None = None,
        max_unavailable: int | str | None = None,
        unhealthy_pod_eviction_policy: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> client.V1PodDisruptionBudget:
        ns = namespace or self.default_namespace
        metadata = build_metadata(name=name, namespace=ns, labels=labels)

        spec: dict[str, Any] = {
            "selector": selector or {},
        }
        if min_available is not None:
            spec["minAvailable"] = min_available
        if max_unavailable is not None:
            spec["maxUnavailable"] = max_unavailable
        if unhealthy_pod_eviction_policy is not None:
            spec["unhealthyPodEvictionPolicy"] = unhealthy_pod_eviction_policy

        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": metadata,
            "spec": spec,
        }

        try:
            return self.client.policy_v1.create_namespaced_pod_disruption_budget(
                namespace=ns,
                body=manifest,
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_pdb(
        self, name: str, namespace: str | None = None
    ) -> client.V1PodDisruptionBudget:
        ns = namespace or self.default_namespace
        try:
            return self.client.policy_v1.read_namespaced_pod_disruption_budget(
                name=name, namespace=ns
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def list_pdbs(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1PodDisruptionBudget]:
        ns = namespace or self.default_namespace
        try:
            result = self.client.policy_v1.list_namespaced_pod_disruption_budget(
                namespace=ns, label_selector=label_selector
            )
            return result.items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def update_pdb(
        self,
        name: str,
        namespace: str | None = None,
        min_available: int | str | None = None,
        max_unavailable: int | str | None = None,
    ) -> client.V1PodDisruptionBudget:
        ns = namespace or self.default_namespace
        patch: dict[str, Any] = {"spec": {}}
        if min_available is not None:
            patch["spec"]["minAvailable"] = min_available
        if max_unavailable is not None:
            patch["spec"]["maxUnavailable"] = max_unavailable

        try:
            return self.client.policy_v1.patch_namespaced_pod_disruption_budget(
                name=name,
                namespace=ns,
                body=patch,
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def delete_pdb(
        self, name: str, namespace: str | None = None
    ) -> None:
        ns = namespace or self.default_namespace
        try:
            self.client.policy_v1.delete_namespaced_pod_disruption_budget(
                name=name,
                namespace=ns,
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_status(
        self, name: str, namespace: str | None = None
    ) -> dict:
        pdb = self.get_pdb(name, namespace)
        status = pdb.status
        return {
            "current_healthy": (status.current_healthy or 0) if status else 0,
            "desired_healthy": (status.desired_healthy or 0) if status else 0,
            "disruptions_allowed": (status.disruptions_allowed or 0) if status else 0,
            "expected_pods": (status.expected_pods or 0) if status else 0,
            "observed_generation": (status.observed_generation or 0) if status else 0,
            "conditions": [
                c.to_dict() if hasattr(c, "to_dict") else c
                for c in (status.conditions or [])
            ] if status else [],
        }

    def get_disruptions_allowed(
        self, name: str, namespace: str | None = None
    ) -> int:
        pdb = self.get_pdb(name, namespace)
        return (pdb.status.disruptions_allowed or 0) if pdb.status else 0

    def is_disruption_allowed(
        self, name: str, namespace: str | None = None
    ) -> bool:
        return self.get_disruptions_allowed(name, namespace) > 0
