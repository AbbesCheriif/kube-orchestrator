"""ManifestApplier — diff detection and apply decision engine."""

from __future__ import annotations

import copy
from typing import Any

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.manifest.validator import route_by_kind


_MANAGED_FIELDS_KEYS = ("managedFields", "resourceVersion", "uid", "generation",
                        "creationTimestamp", "selfLink")


class ManifestApplier:
    """Apply, diff and manage Kubernetes manifests idempotently."""

    def __init__(
        self,
        client: KubeClient,
        dry_run: bool = False,
        force: bool = False,
        server_side: bool = False,
    ) -> None:
        self.client = client
        self.dry_run = dry_run
        self.force = force
        self.server_side = server_side

    # ------------------------------------------------------------------
    # Live resource retrieval
    # ------------------------------------------------------------------

    def get_live_resource(self, manifest: dict[str, Any]) -> dict[str, Any] | None:
        """Fetch the current cluster state for the resource, or None if absent."""
        manager_cls = route_by_kind(manifest)
        if manager_cls is None:
            return None
        manager = manager_cls(self.client)
        meta = manifest.get("metadata", {})
        name = meta.get("name", "")
        namespace = meta.get("namespace", "default")
        try:
            resource = manager.get(name, namespace)
            if hasattr(resource, "to_dict"):
                return resource.to_dict()
            return dict(resource)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Diff and decision
    # ------------------------------------------------------------------

    def compute_diff(
        self, live: dict[str, Any], desired: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute a shallow field-level diff between live and desired specs."""
        diff: dict[str, Any] = {"added": {}, "changed": {}, "removed": {}}
        live_spec = live.get("spec") or {}
        desired_spec = desired.get("spec") or {}

        for key, value in desired_spec.items():
            if key not in live_spec:
                diff["added"][key] = value
            elif live_spec[key] != value:
                diff["changed"][key] = {"from": live_spec[key], "to": value}

        for key in live_spec:
            if key not in desired_spec:
                diff["removed"][key] = live_spec[key]

        return diff

    def decide_action(
        self,
        live: dict[str, Any] | None,
        desired: dict[str, Any],
    ) -> str:
        """Return 'create', 'update', 'skip', or 'replace'."""
        if live is None:
            return "create"
        diff = self.compute_diff(live, desired)
        if not diff["added"] and not diff["changed"] and not diff["removed"]:
            return "skip"
        if self.force:
            return "replace"
        return "update"

    def format_diff_output(self, diff: dict[str, Any]) -> str:
        """Return a human-readable diff summary string."""
        lines: list[str] = []
        for key, value in diff.get("added", {}).items():
            lines.append(f"+ {key}: {value}")
        for key, info in diff.get("changed", {}).items():
            lines.append(f"~ {key}: {info['from']} → {info['to']}")
        for key, value in diff.get("removed", {}).items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines) if lines else "(no spec changes)"
