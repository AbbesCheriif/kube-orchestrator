"""ManifestDeleter — safe delete engine for Kubernetes manifests."""

from __future__ import annotations

from typing import Any

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.manifest.loader import load_directory, load_file
from kube_orchestrator.manifest.validator import order_by_dependency, route_by_kind


class ManifestDeleter:
    """Delete Kubernetes resources described by manifest files, safely."""

    def __init__(
        self,
        client: KubeClient,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.dry_run = dry_run

    # ------------------------------------------------------------------
    # Delete operations
    # ------------------------------------------------------------------

    def delete_manifest(
        self,
        manifest: dict[str, Any],
        namespace: str | None = None,
        cascade: bool = True,
        grace_period: int | None = None,
    ) -> str | None:
        """Delete a single resource. Returns the resource name if deleted."""
        manager_cls = route_by_kind(manifest)
        if manager_cls is None:
            return None

        meta = manifest.get("metadata", {})
        name = meta.get("name", "")
        ns = namespace or meta.get("namespace", "default")
        propagation = "Foreground" if cascade else "Orphan"

        if self.dry_run:
            return f"(dry-run) would delete {manifest.get('kind')}/{name}"

        manager = manager_cls(self.client)
        try:
            manager.delete(
                name,
                ns,
                grace_period_seconds=grace_period,
                propagation_policy=propagation,
            )
            return f"{manifest.get('kind')}/{name}"
        except Exception:
            return None

    def delete_file(
        self,
        path: str,
        namespace: str | None = None,
        cascade: bool = True,
        grace_period: int | None = None,
    ) -> list[str]:
        """Delete all resources described in a manifest file.

        Resources are deleted in reverse dependency order (dependents first).
        """
        manifests = load_file(path)
        ordered = list(reversed(order_by_dependency(manifests)))
        deleted: list[str] = []
        for m in ordered:
            result = self.delete_manifest(m, namespace, cascade, grace_period)
            if result:
                deleted.append(result)
        return deleted

    def delete_directory(
        self,
        path: str,
        namespace: str | None = None,
        recursive: bool = False,
    ) -> list[str]:
        """Delete all resources found in a directory of manifest files."""
        manifests = load_directory(path, recursive=recursive)
        ordered = list(reversed(order_by_dependency(manifests)))
        deleted: list[str] = []
        for m in ordered:
            result = self.delete_manifest(m, namespace)
            if result:
                deleted.append(result)
        return deleted

    def dry_run_delete(self, path: str) -> list[dict[str, Any]]:
        """Return what would be deleted from a file without actually deleting."""
        manifests = load_file(path)
        ordered = list(reversed(order_by_dependency(manifests)))
        plan: list[dict[str, Any]] = []
        for m in ordered:
            meta = m.get("metadata", {})
            plan.append(
                {
                    "action": "delete",
                    "kind": m.get("kind"),
                    "name": meta.get("name"),
                    "namespace": meta.get("namespace"),
                    "dry_run": True,
                }
            )
        return plan

    def detect_orphans(
        self,
        namespace: str,
    ) -> list[dict[str, Any]]:
        """Detect ReplicaSets in a namespace that have no owning Deployment."""
        from kube_orchestrator.resources.workloads.replicaset import ReplicaSetManager

        mgr = ReplicaSetManager(self.client, default_namespace=namespace)
        try:
            orphans = mgr.list_orphan_replicasets(namespace)
            return [
                {
                    "kind": "ReplicaSet",
                    "name": rs.metadata.name if rs.metadata else None,
                    "namespace": namespace,
                }
                for rs in orphans
            ]
        except Exception:
            return []
