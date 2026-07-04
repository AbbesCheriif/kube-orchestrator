"""Integration tests for the CRD install + CustomObjectManager workflow."""

from __future__ import annotations

from typing import Any

import pytest


def _crd_manifest(plural: str, singular: str, kind: str, group: str) -> dict[str, Any]:
    return {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {"name": f"{plural}.{group}"},
        "spec": {
            "group": group,
            "names": {"plural": plural, "singular": singular, "kind": kind},
            "scope": "Namespaced",
            "versions": [
                {
                    "name": "v1",
                    "served": True,
                    "storage": True,
                    "schema": {
                        "openAPIV3Schema": {
                            "type": "object",
                            "properties": {
                                "spec": {
                                    "type": "object",
                                    "properties": {"size": {"type": "string"}},
                                }
                            },
                        }
                    },
                }
            ],
        },
    }


@pytest.mark.integration
@pytest.mark.slow
class TestCrdWorkflow:
    def test_install_wait_and_manage_custom_object(self, kube_client) -> None:
        """Install a CRD, wait for it to be Established, then CRUD a custom object."""
        from kube_orchestrator.crd.custom_object_manager import CustomObjectManager
        from kube_orchestrator.crd.installer import CRDInstaller

        manifest = _crd_manifest("widgets", "widget", "Widget", "ko-test.example.com")
        installer = CRDInstaller(kube_client=kube_client)
        installer.install(dict(manifest))
        try:
            established = installer.wait_for_established(
                "widgets.ko-test.example.com", timeout_seconds=60
            )
            assert established is True

            widgets = CustomObjectManager(
                group="ko-test.example.com",
                version="v1",
                plural="widgets",
                kube_client=kube_client,
            )
            widgets.create(
                {
                    "apiVersion": "ko-test.example.com/v1",
                    "kind": "Widget",
                    "metadata": {"name": "my-widget"},
                    "spec": {"size": "large"},
                },
                namespace="default",
            )
            obj = widgets.get("my-widget", namespace="default")
            assert obj["spec"]["size"] == "large"

            widgets.delete("my-widget", namespace="default")
            assert widgets.exists("my-widget", namespace="default") is False
        finally:
            installer.uninstall("widgets.ko-test.example.com")

    def test_discovery_finds_installed_crd(self, kube_client) -> None:
        """APIDiscovery.discover_all_crds should list a freshly installed CRD.

        Uses its own CRD name (distinct from the other test in this class):
        CRD deletion is asynchronous (finalizers), so reusing a name a
        previous test just deleted can race with that deletion and leave
        the freshly (re)created CRD stuck mid-termination.
        """
        from kube_orchestrator.crd.discovery import APIDiscovery
        from kube_orchestrator.crd.installer import CRDInstaller

        manifest = _crd_manifest("gadgets", "gadget", "Gadget", "ko-test.example.com")
        installer = CRDInstaller(kube_client=kube_client)
        installer.install(dict(manifest))
        try:
            established = installer.wait_for_established(
                "gadgets.ko-test.example.com", timeout_seconds=60
            )
            assert established is True

            discovery = APIDiscovery(kube_client=kube_client)
            crds = discovery.discover_all_crds()
            names = [c["name"] for c in crds]
            assert "gadgets.ko-test.example.com" in names
        finally:
            installer.uninstall("gadgets.ko-test.example.com")
