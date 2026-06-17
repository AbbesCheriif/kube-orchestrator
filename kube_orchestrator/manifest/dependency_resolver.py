"""DependencyResolver — ordered apply and readiness waiting for manifest sets."""

from __future__ import annotations

import time
from typing import Any

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.manifest.validator import order_by_dependency


class DependencyResolver:
    """Resolve manifest apply order and wait for resource readiness."""

    def __init__(self, client: KubeClient, default_timeout: int = 120) -> None:
        self.client = client
        self.default_timeout = default_timeout

    def resolve(self, manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return manifests sorted in safe dependency order."""
        return order_by_dependency(manifests)

    # ------------------------------------------------------------------
    # Readiness waiting
    # ------------------------------------------------------------------

    def wait_for_namespace_ready(
        self, name: str, timeout: int | None = None
    ) -> bool:
        """Block until the namespace phase is Active or timeout is reached."""
        deadline = time.monotonic() + (timeout or self.default_timeout)
        from kube_orchestrator.resources.cluster.namespace import NamespaceManager

        mgr = NamespaceManager(self.client)
        while time.monotonic() < deadline:
            try:
                ns = mgr.get_namespace(name)
                if ns.status and ns.status.phase == "Active":
                    return True
            except Exception:
                pass
            time.sleep(2)
        return False

    def wait_for_crd_ready(
        self, name: str, timeout: int | None = None
    ) -> bool:
        """Block until the CRD has an Established condition or timeout elapses."""
        deadline = time.monotonic() + (timeout or self.default_timeout)
        api = self.client.api_extensions_v1
        while time.monotonic() < deadline:
            try:
                crd = api.read_custom_resource_definition(name)
                conditions = (crd.status and crd.status.conditions) or []
                for c in conditions:
                    if c.type == "Established" and c.status == "True":
                        return True
            except Exception:
                pass
            time.sleep(2)
        return False

    def wait_for_resource_ready(
        self,
        manifest: dict[str, Any],
        timeout: int | None = None,
    ) -> bool:
        """Block until the resource described by the manifest is ready.

        Dispatches to the appropriate wait helper based on kind.
        """
        kind = manifest.get("kind", "")
        meta = manifest.get("metadata", {})
        name = meta.get("name", "")

        if kind == "Namespace":
            return self.wait_for_namespace_ready(name, timeout)
        if kind == "CustomResourceDefinition":
            return self.wait_for_crd_ready(name, timeout)

        deadline = time.monotonic() + (timeout or self.default_timeout)
        from kube_orchestrator.manifest.validator import route_by_kind

        manager_cls = route_by_kind(manifest)
        if manager_cls is None:
            return True

        mgr = manager_cls(self.client)
        ns = meta.get("namespace", "default")
        while time.monotonic() < deadline:
            try:
                resource = mgr.get(name, ns)
                if resource is not None:
                    return True
            except Exception:
                pass
            time.sleep(2)
        return False
