"""CustomObjectManager — Adapter Pattern for any custom Kubernetes resource."""

from __future__ import annotations

from typing import Any, Callable

from kubernetes import client, watch
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception


class CustomObjectManager:
    """Generic manager for any Custom Resource via the CustomObjects API.

    Implements the Adapter Pattern: wraps the generic kubernetes CustomObjectsApi
    and exposes a consistent interface matching the built-in resource managers.
    """

    def __init__(
        self,
        group: str,
        version: str,
        plural: str,
        kube_client: KubeClient,
    ) -> None:
        self.group = group
        self.version = version
        self.plural = plural
        self.client = kube_client

    def _api(self) -> client.CustomObjectsApi:
        return self.client.custom_objects()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        manifest: dict[str, Any],
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Create a custom resource, cluster-scoped or namespace-scoped."""
        try:
            if namespace:
                return self._api().create_namespaced_custom_object(
                    self.group, self.version, namespace, self.plural, manifest
                )
            return self._api().create_cluster_custom_object(
                self.group, self.version, self.plural, manifest
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get(
        self,
        name: str,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a single custom resource by name."""
        try:
            if namespace:
                return self._api().get_namespaced_custom_object(
                    self.group, self.version, namespace, self.plural, name
                )
            return self._api().get_cluster_custom_object(
                self.group, self.version, self.plural, name
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def list(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all custom resources of this type."""
        try:
            kwargs: dict[str, Any] = {}
            if label_selector:
                kwargs["label_selector"] = label_selector
            if namespace:
                result = self._api().list_namespaced_custom_object(
                    self.group, self.version, namespace, self.plural, **kwargs
                )
            else:
                result = self._api().list_cluster_custom_object(
                    self.group, self.version, self.plural, **kwargs
                )
            return result.get("items", [])
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def update(
        self,
        name: str,
        manifest: dict[str, Any],
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Replace a custom resource entirely."""
        try:
            if namespace:
                return self._api().replace_namespaced_custom_object(
                    self.group, self.version, namespace, self.plural, name, manifest
                )
            return self._api().replace_cluster_custom_object(
                self.group, self.version, self.plural, name, manifest
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def patch(
        self,
        name: str,
        patch: dict[str, Any],
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Apply a merge patch to a custom resource."""
        try:
            if namespace:
                return self._api().patch_namespaced_custom_object(
                    self.group, self.version, namespace, self.plural, name, patch
                )
            return self._api().patch_cluster_custom_object(
                self.group, self.version, self.plural, name, patch
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def delete(
        self,
        name: str,
        namespace: str | None = None,
    ) -> None:
        """Delete a custom resource."""
        try:
            if namespace:
                self._api().delete_namespaced_custom_object(
                    self.group, self.version, namespace, self.plural, name
                )
            else:
                self._api().delete_cluster_custom_object(
                    self.group, self.version, self.plural, name
                )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def exists(
        self,
        name: str,
        namespace: str | None = None,
    ) -> bool:
        """Return True if the custom resource exists."""
        try:
            self.get(name, namespace)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Watch
    # ------------------------------------------------------------------

    def watch(
        self,
        namespace: str | None = None,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Stream watch events for this custom resource type."""
        w = watch.Watch()
        api = self._api()
        if namespace:
            stream = w.stream(
                api.list_namespaced_custom_object,
                self.group, self.version, namespace, self.plural,
            )
        else:
            stream = w.stream(
                api.list_cluster_custom_object,
                self.group, self.version, self.plural,
            )
        for event in stream:
            if callback:
                callback(event)
