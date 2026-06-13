"""CRDInstaller — install, uninstall and inspect Custom Resource Definitions."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import yaml
from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception


class CRDInstaller:
    """Install, verify and manage Kubernetes CustomResourceDefinitions."""

    def __init__(self, kube_client: KubeClient) -> None:
        self.client = kube_client

    def _api(self) -> client.ApiextensionsV1Api:
        return self.client.api_extensions_v1()

    # ------------------------------------------------------------------
    # Install / uninstall
    # ------------------------------------------------------------------

    def install(self, manifest: dict[str, Any]) -> client.V1CustomResourceDefinition:
        """Create or replace a CRD from a manifest dict."""
        name = manifest["metadata"]["name"]
        if self.is_installed(name):
            existing = self._api().read_custom_resource_definition(name)
            manifest["metadata"]["resourceVersion"] = existing.metadata.resource_version
            return self._api().replace_custom_resource_definition(name, manifest)
        try:
            return self._api().create_custom_resource_definition(manifest)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def install_from_file(
        self, path: str
    ) -> client.V1CustomResourceDefinition:
        """Load a CRD YAML file and install it."""
        content = Path(path).read_text(encoding="utf-8")
        manifest = yaml.safe_load(content)
        return self.install(manifest)

    def uninstall(self, name: str) -> None:
        """Delete a CRD by name (also removes all instances of the CR)."""
        try:
            self._api().delete_custom_resource_definition(name)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def is_installed(self, name: str) -> bool:
        """Return True if a CRD with the given name exists in the cluster."""
        try:
            self._api().read_custom_resource_definition(name)
            return True
        except ApiException as exc:
            if exc.status == 404:
                return False
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Wait for readiness
    # ------------------------------------------------------------------

    def wait_for_established(
        self, name: str, timeout_seconds: int = 60
    ) -> bool:
        """Block until the CRD has the Established condition or times out."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                crd = self._api().read_custom_resource_definition(name)
                conditions = (crd.status and crd.status.conditions) or []
                for c in conditions:
                    if c.type == "Established" and c.status == "True":
                        return True
            except ApiException:
                pass
            time.sleep(2)
        return False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_crds(
        self,
        group: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1CustomResourceDefinition]:
        """List all CRDs, optionally filtered by API group or label selector."""
        try:
            result = self._api().list_custom_resource_definition(
                label_selector=label_selector
            )
            items = result.items
            if group:
                items = [
                    crd for crd in items
                    if crd.spec and crd.spec.group == group
                ]
            return items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_crd(self, name: str) -> client.V1CustomResourceDefinition:
        """Fetch a single CRD by its full name (e.g. foos.example.com)."""
        try:
            return self._api().read_custom_resource_definition(name)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_schema(self, name: str) -> dict[str, Any]:
        """Return the OpenAPI v3 validation schema for the CRD's storage version."""
        crd = self.get_crd(name)
        for version in crd.spec.versions or []:
            if version.storage:
                schema = version.schema
                if schema and schema.open_apiv3_schema:
                    val = schema.open_apiv3_schema
                    return val.to_dict() if hasattr(val, "to_dict") else dict(val)
        return {}

    def list_versions(self, name: str) -> list[str]:
        """Return the list of version names defined in the CRD."""
        crd = self.get_crd(name)
        return [v.name for v in (crd.spec.versions or [])]
