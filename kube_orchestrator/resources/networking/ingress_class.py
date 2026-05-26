"""IngressClassManager — full IngressClass spec coverage (controller, parameters)."""

from __future__ import annotations

from typing import Any

from kubernetes.client import (
    NetworkingV1Api,
    V1IngressClass,
)
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata

_DEFAULT_ANNOTATION = "ingressclass.kubernetes.io/is-default-class"


class IngressClassManager(BaseResourceManager[V1IngressClass]):
    """Manage Kubernetes IngressClass resources (cluster-scoped)."""

    def _get_api(self) -> NetworkingV1Api:
        return self.client.networking_v1

    def _kind(self) -> str:
        return "IngressClass"

    def _api_version(self) -> str:
        return "networking.k8s.io/v1"

    # ------------------------------------------------------------------
    # Full-spec factory
    # ------------------------------------------------------------------

    def create_ingress_class(
        self,
        name: str,
        controller: str,
        parameters: dict | None = None,
        is_default: bool = False,
        labels: dict | None = None,
    ) -> V1IngressClass:
        annotations: dict[str, str] | None = None
        if is_default:
            annotations = {_DEFAULT_ANNOTATION: "true"}

        spec: dict[str, Any] = {"controller": controller}
        if parameters is not None:
            spec["parameters"] = self._build_parameters(parameters)

        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": build_metadata(
                name=name,
                namespace=None,
                labels=labels,
                annotations=annotations,
            ),
            "spec": spec,
        }
        try:
            result = self.client.networking_v1.create_ingress_class(
                body=manifest,
                dry_run=self.dry_run,
            )
            self.logger.info("created IngressClass", name=name)
            return result
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # CRUD operations (cluster-scoped — no namespace)
    # ------------------------------------------------------------------

    def get_ingress_class(self, name: str) -> V1IngressClass:
        try:
            return self.client.networking_v1.read_ingress_class(name=name)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def list_ingress_classes(self) -> list[V1IngressClass]:
        try:
            result = self.client.networking_v1.list_ingress_class()
            return result.items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def delete_ingress_class(self, name: str) -> None:
        try:
            self.client.networking_v1.delete_ingress_class(
                name=name,
                dry_run=self.dry_run,
            )
            self.logger.info("deleted IngressClass", name=name)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    # ------------------------------------------------------------------
    # Default class management
    # ------------------------------------------------------------------

    def set_as_default(self, name: str) -> V1IngressClass:
        """Annotate this IngressClass as the cluster default."""
        try:
            return self.client.networking_v1.patch_ingress_class(
                name=name,
                body={
                    "metadata": {
                        "annotations": {_DEFAULT_ANNOTATION: "true"}
                    }
                },
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def unset_default(self, name: str) -> V1IngressClass:
        """Remove the default annotation from this IngressClass."""
        try:
            return self.client.networking_v1.patch_ingress_class(
                name=name,
                body={
                    "metadata": {
                        "annotations": {_DEFAULT_ANNOTATION: None}
                    }
                },
                dry_run=self.dry_run,
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_default(self) -> V1IngressClass | None:
        """Return the cluster-default IngressClass, or None if none is set."""
        for ic in self.list_ingress_classes():
            annotations = getattr(getattr(ic, "metadata", None), "annotations", None) or {}
            if annotations.get(_DEFAULT_ANNOTATION) == "true":
                return ic
        return None

    # ------------------------------------------------------------------
    # Internal builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_parameters(params: dict) -> dict[str, Any]:
        """Normalize IngressClass parameters (apiGroup, kind, name, namespace, scope)."""
        result: dict[str, Any] = {
            "kind": params.get("kind", ""),
            "name": params.get("name", ""),
        }
        if "apiGroup" in params:
            result["apiGroup"] = params["apiGroup"]
        if "namespace" in params:
            result["namespace"] = params["namespace"]
        if "scope" in params:
            result["scope"] = params["scope"]
        return result
