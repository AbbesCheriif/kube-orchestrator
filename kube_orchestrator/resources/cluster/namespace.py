"""NamespaceManager — cluster-scoped Namespace resource manager."""

from __future__ import annotations

import time
from typing import Any

from kubernetes.client import CoreV1Api, V1Namespace
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.exceptions import ResourceNotFoundError, parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata
from kube_orchestrator.resources.cluster.resource_quota import ResourceQuotaManager
from kube_orchestrator.resources.cluster.limit_range import LimitRangeManager


class NamespaceManager(BaseResourceManager[V1Namespace]):
    """Manage Kubernetes Namespace resources (cluster-scoped)."""

    def _get_api(self) -> CoreV1Api:
        return self.client.core_v1

    def _kind(self) -> str:
        return "Namespace"

    def _api_version(self) -> str:
        return "v1"

    def create_namespace(
        self,
        name: str,
        labels: dict | None = None,
        annotations: dict | None = None,
        finalizers: list[str] | None = None,
    ) -> V1Namespace:
        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": build_metadata(
                name=name,
                namespace=None,
                labels=labels,
                annotations=annotations,
                finalizers=finalizers,
            ),
        }
        if finalizers:
            manifest["spec"] = {"finalizers": finalizers}
        return self.create(manifest)

    def get_namespace(self, name: str) -> V1Namespace:
        return self.get(name)

    def list_namespaces(
        self,
        label_selector: str | None = None,
        field_selector: str | None = None,
    ) -> list[V1Namespace]:
        return self.list(
            namespace=None,
            label_selector=label_selector,
            field_selector=field_selector,
        )

    def delete_namespace(
        self,
        name: str,
        grace_period_seconds: int | None = None,
    ) -> None:
        self.delete(name, grace_period_seconds=grace_period_seconds)

    def label_namespace(self, name: str, labels: dict) -> V1Namespace:
        ns = self.get_namespace(name)
        existing = dict(ns.metadata.labels or {})
        existing.update(labels)
        return self.patch(name, {"metadata": {"labels": existing}})

    def annotate_namespace(self, name: str, annotations: dict) -> V1Namespace:
        ns = self.get_namespace(name)
        existing = dict(ns.metadata.annotations or {})
        existing.update(annotations)
        return self.patch(name, {"metadata": {"annotations": existing}})

    def add_finalizer(self, name: str, finalizer: str) -> V1Namespace:
        ns = self.get_namespace(name)
        finalizers = list(ns.spec.finalizers or []) if ns.spec else []
        if finalizer not in finalizers:
            finalizers.append(finalizer)
        return self.patch(name, {"spec": {"finalizers": finalizers}})

    def remove_finalizer(self, name: str, finalizer: str) -> V1Namespace:
        ns = self.get_namespace(name)
        finalizers = list(ns.spec.finalizers or []) if ns.spec else []
        finalizers = [f for f in finalizers if f != finalizer]
        return self.patch(name, {"spec": {"finalizers": finalizers}})

    def get_phase(self, name: str) -> str:
        ns = self.get_namespace(name)
        return ns.status.phase if ns.status else "Unknown"

    def wait_for_active(self, name: str, timeout_seconds: int = 60) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                if self.get_phase(name) == "Active":
                    return True
            except ResourceNotFoundError:
                pass
            time.sleep(2)
        return False

    def wait_for_deletion(self, name: str, timeout_seconds: int = 120) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self.exists(name):
                return True
            time.sleep(2)
        return False

    def get_resource_usage(self, name: str) -> dict:
        """Return ResourceQuota hard/used stats for each quota in the namespace."""
        api = self._get_api()
        try:
            quotas = api.list_namespaced_resource_quota(namespace=name)
            usage: dict[str, Any] = {}
            for quota in quotas.items:
                if quota.status:
                    usage[quota.metadata.name] = {
                        "hard": dict(quota.status.hard or {}),
                        "used": dict(quota.status.used or {}),
                    }
            return usage
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_all_resources(self, name: str) -> dict[str, list]:
        """Return all namespaced resources grouped by type.

        Covers workloads, services, configmaps, secrets, and PVCs.
        Networking and storage managers return empty lists until those
        modules are implemented in later days.
        """
        api = self._get_api()
        result: dict[str, list] = {
            "pods": [],
            "deployments": [],
            "statefulsets": [],
            "daemonsets": [],
            "replicasets": [],
            "jobs": [],
            "cronjobs": [],
            "services": [],
            "configmaps": [],
            "secrets": [],
            "persistentvolumeclaims": [],
            "resourcequotas": [],
            "limitranges": [],
        }
        try:
            result["pods"] = api.list_namespaced_pod(namespace=name).items
            result["services"] = api.list_namespaced_service(namespace=name).items
            result["configmaps"] = api.list_namespaced_config_map(namespace=name).items
            result["secrets"] = api.list_namespaced_secret(namespace=name).items
            result["persistentvolumeclaims"] = api.list_namespaced_persistent_volume_claim(namespace=name).items
            result["resourcequotas"] = api.list_namespaced_resource_quota(namespace=name).items
            result["limitranges"] = api.list_namespaced_limit_range(namespace=name).items

            apps_api = self.client.apps_v1
            result["deployments"] = apps_api.list_namespaced_deployment(namespace=name).items
            result["statefulsets"] = apps_api.list_namespaced_stateful_set(namespace=name).items
            result["daemonsets"] = apps_api.list_namespaced_daemon_set(namespace=name).items
            result["replicasets"] = apps_api.list_namespaced_replica_set(namespace=name).items

            batch_api = self.client.batch_v1
            result["jobs"] = batch_api.list_namespaced_job(namespace=name).items
            result["cronjobs"] = batch_api.list_namespaced_cron_job(namespace=name).items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc
        return result

    def clone_namespace_config(self, source: str, dest: str) -> None:
        """Copy ResourceQuotas and LimitRanges from *source* namespace to *dest*."""
        quota_mgr = ResourceQuotaManager(client=self.client, default_namespace=source)
        lr_mgr = LimitRangeManager(client=self.client, default_namespace=source)

        for quota in quota_mgr.list_quotas(namespace=source):
            spec = quota.spec
            hard = dict(spec.hard) if spec and spec.hard else {}
            scopes = list(spec.scopes) if spec and spec.scopes else None
            scope_selector = spec.scope_selector.to_dict() if spec and spec.scope_selector else None
            try:
                quota_mgr.create_quota(
                    name=quota.metadata.name,
                    namespace=dest,
                    hard=hard,
                    scopes=scopes,
                    scope_selector=scope_selector,
                )
            except Exception:
                pass

        for lr in lr_mgr.list_limit_ranges(namespace=source):
            spec_lr = lr.spec
            limits = [item.to_dict() for item in (spec_lr.limits or [])] if spec_lr else []
            try:
                lr_mgr.create_limit_range(
                    name=lr.metadata.name,
                    namespace=dest,
                    limits=limits,
                )
            except Exception:
                pass

    def get_resource_summary(self, name: str) -> dict[str, int]:
        """Return a condensed count of each resource type in the namespace."""
        all_resources = self.get_all_resources(name)
        return {kind: len(items) for kind, items in all_resources.items()}
