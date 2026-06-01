"""IngressManager — full Ingress spec coverage (rules, TLS, defaultBackend)."""

from __future__ import annotations

from typing import Any

from kubernetes.client import (
    NetworkingV1Api,
    V1Ingress,
)
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class IngressManager(BaseResourceManager[V1Ingress]):
    """Manage Kubernetes Ingress resources with full spec coverage."""

    def _get_api(self) -> NetworkingV1Api:
        return self.client.networking_v1

    def _kind(self) -> str:
        return "Ingress"

    def _api_version(self) -> str:
        return "networking.k8s.io/v1"

    # ------------------------------------------------------------------
    # Full-spec factory
    # ------------------------------------------------------------------

    def create_ingress(
        self,
        name: str,
        namespace: str,
        rules: list[dict] | None = None,
        ingress_class_name: str | None = None,
        default_backend: dict | None = None,
        tls: list[dict] | None = None,
        labels: dict | None = None,
        annotations: dict | None = None,
    ) -> V1Ingress:
        spec: dict[str, Any] = {}

        if ingress_class_name is not None:
            spec["ingressClassName"] = ingress_class_name
        if default_backend is not None:
            spec["defaultBackend"] = self._build_backend(default_backend)
        if rules:
            spec["rules"] = self._build_rules(rules)
        if tls:
            spec["tls"] = self._build_tls(tls)

        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": build_metadata(
                name=name,
                namespace=namespace,
                labels=labels,
                annotations=annotations,
            ),
            "spec": spec,
        }
        return self.create(manifest, namespace)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def get_ingress(self, name: str, namespace: str) -> V1Ingress:
        return self.get(name, namespace)

    def list_ingresses(
        self,
        namespace: str,
        label_selector: str | None = None,
    ) -> list[V1Ingress]:
        return self.list(namespace, label_selector=label_selector)

    def delete_ingress(self, name: str, namespace: str) -> None:
        self.delete(name, namespace)

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(
        self,
        name: str,
        namespace: str,
        host: str,
        paths: list[dict],
    ) -> V1Ingress:
        ingress = self.get_ingress(name, namespace)
        existing_rules = list(getattr(getattr(ingress, "spec", None), "rules", None) or [])
        existing_dicts = [self._rule_obj_to_dict(r) for r in existing_rules]
        existing_dicts.append({"host": host, "http": {"paths": paths}})
        return self.patch(
            name,
            {"spec": {"rules": existing_dicts}},
            namespace,
            patch_type="merge",
        )

    def remove_rule(self, name: str, namespace: str, host: str) -> V1Ingress:
        ingress = self.get_ingress(name, namespace)
        existing_rules = list(getattr(getattr(ingress, "spec", None), "rules", None) or [])
        updated = [
            self._rule_obj_to_dict(r)
            for r in existing_rules
            if getattr(r, "host", None) != host
        ]
        return self.patch(
            name,
            {"spec": {"rules": updated}},
            namespace,
            patch_type="merge",
        )

    # ------------------------------------------------------------------
    # TLS management
    # ------------------------------------------------------------------

    def add_tls(
        self,
        name: str,
        namespace: str,
        hosts: list[str],
        secret_name: str,
    ) -> V1Ingress:
        ingress = self.get_ingress(name, namespace)
        existing_tls = list(getattr(getattr(ingress, "spec", None), "tls", None) or [])
        existing_dicts = [self._tls_obj_to_dict(t) for t in existing_tls]
        existing_dicts.append({"hosts": hosts, "secretName": secret_name})
        return self.patch(
            name,
            {"spec": {"tls": existing_dicts}},
            namespace,
            patch_type="merge",
        )

    def remove_tls(
        self,
        name: str,
        namespace: str,
        hosts: list[str],
    ) -> V1Ingress:
        ingress = self.get_ingress(name, namespace)
        existing_tls = list(getattr(getattr(ingress, "spec", None), "tls", None) or [])
        hosts_set = set(hosts)
        updated = [
            self._tls_obj_to_dict(t)
            for t in existing_tls
            if not hosts_set.intersection(set(getattr(t, "hosts", None) or []))
        ]
        return self.patch(
            name,
            {"spec": {"tls": updated}},
            namespace,
            patch_type="merge",
        )

    # ------------------------------------------------------------------
    # Spec mutation helpers
    # ------------------------------------------------------------------

    def set_ingress_class(
        self,
        name: str,
        namespace: str,
        class_name: str,
    ) -> V1Ingress:
        return self.patch(
            name,
            {"spec": {"ingressClassName": class_name}},
            namespace,
            patch_type="merge",
        )

    def set_default_backend(
        self,
        name: str,
        namespace: str,
        service_name: str,
        service_port: int | str,
    ) -> V1Ingress:
        backend: dict[str, Any] = {
            "service": {
                "name": service_name,
                "port": (
                    {"number": service_port}
                    if isinstance(service_port, int)
                    else {"name": service_port}
                ),
            }
        }
        return self.patch(
            name,
            {"spec": {"defaultBackend": backend}},
            namespace,
            patch_type="merge",
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_all_hosts(self, name: str, namespace: str) -> list[str]:
        ingress = self.get_ingress(name, namespace)
        rules = getattr(getattr(ingress, "spec", None), "rules", None) or []
        return [getattr(r, "host", "") for r in rules if getattr(r, "host", None)]

    def get_all_rules(self, name: str, namespace: str) -> list[dict]:
        ingress = self.get_ingress(name, namespace)
        rules = getattr(getattr(ingress, "spec", None), "rules", None) or []
        return [self._rule_obj_to_dict(r) for r in rules]

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_backend(backend: dict) -> dict[str, Any]:
        """Normalize a backend dict (service or resource reference)."""
        result: dict[str, Any] = {}
        if "service" in backend:
            svc = backend["service"]
            port = svc.get("port", {})
            result["service"] = {
                "name": svc["name"],
                "port": port,
            }
        if "resource" in backend:
            result["resource"] = backend["resource"]
        return result

    @staticmethod
    def _build_rules(rules: list[dict]) -> list[dict[str, Any]]:
        normalized = []
        for rule in rules:
            entry: dict[str, Any] = {}
            if "host" in rule:
                entry["host"] = rule["host"]
            if "http" in rule:
                paths = []
                for p in rule["http"].get("paths", []):
                    path_entry: dict[str, Any] = {
                        "pathType": p.get("pathType", "Prefix"),
                    }
                    if "path" in p:
                        path_entry["path"] = p["path"]
                    if "backend" in p:
                        svc = p["backend"].get("service", {})
                        port = svc.get("port", {})
                        path_entry["backend"] = {
                            "service": {"name": svc.get("name", ""), "port": port}
                        }
                        if "resource" in p["backend"]:
                            path_entry["backend"]["resource"] = p["backend"]["resource"]
                    paths.append(path_entry)
                entry["http"] = {"paths": paths}
            normalized.append(entry)
        return normalized

    @staticmethod
    def _build_tls(tls: list[dict]) -> list[dict[str, Any]]:
        normalized = []
        for t in tls:
            entry: dict[str, Any] = {}
            if "hosts" in t:
                entry["hosts"] = t["hosts"]
            if "secretName" in t:
                entry["secretName"] = t["secretName"]
            normalized.append(entry)
        return normalized

    @staticmethod
    def _rule_obj_to_dict(rule: Any) -> dict[str, Any]:
        entry: dict[str, Any] = {}
        if getattr(rule, "host", None):
            entry["host"] = rule.host
        http = getattr(rule, "http", None)
        if http is not None:
            paths = []
            for p in getattr(http, "paths", None) or []:
                path_entry: dict[str, Any] = {
                    "pathType": getattr(p, "path_type", "Prefix"),
                }
                if getattr(p, "path", None):
                    path_entry["path"] = p.path
                backend = getattr(p, "backend", None)
                if backend is not None:
                    svc = getattr(backend, "service", None)
                    if svc is not None:
                        port = getattr(svc, "port", None)
                        port_dict: dict[str, Any] = {}
                        if getattr(port, "number", None) is not None:
                            port_dict["number"] = port.number
                        if getattr(port, "name", None) is not None:
                            port_dict["name"] = port.name
                        path_entry["backend"] = {
                            "service": {"name": svc.name, "port": port_dict}
                        }
                paths.append(path_entry)
            entry["http"] = {"paths": paths}
        return entry

    @staticmethod
    def _tls_obj_to_dict(tls: Any) -> dict[str, Any]:
        entry: dict[str, Any] = {}
        hosts = getattr(tls, "hosts", None)
        if hosts:
            entry["hosts"] = list(hosts)
        secret = getattr(tls, "secret_name", None)
        if secret:
            entry["secretName"] = secret
        return entry
