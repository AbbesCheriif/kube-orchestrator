"""Integration tests for the manifest engine (directory apply)."""
from __future__ import annotations

from pathlib import Path

import pytest


EXAMPLES_FULL_APP = Path(__file__).parent.parent.parent / "examples" / "full-app"


@pytest.mark.integration
@pytest.mark.slow
class TestManifestEngine:
    def test_directory_dry_run(self, kube_client, test_namespace) -> None:
        """Dry-run apply an entire directory of manifests."""
        if not EXAMPLES_FULL_APP.exists():
            pytest.skip("examples/full-app/ directory not found")

        from kube_orchestrator.manifest.applier import ManifestApplier

        applier = ManifestApplier(client=kube_client, dry_run=True, force=False, server_side=False)
        results = applier.apply_directory(str(EXAMPLES_FULL_APP), namespace=test_namespace, recursive=False)
        assert len(results) > 0
        assert all(r.get("dry_run") is True for r in results)

    def test_multi_doc_yaml_loading(self) -> None:
        """Verify multi-document YAML files load all documents."""
        from kube_orchestrator.manifest.loader import load_string

        content = (
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: cm1\n"
            "---\n"
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: cm2\n"
            "---\n"
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: dep1\n"
        )
        docs = load_string(content)
        assert len(docs) == 3

    def test_dependency_ordering(self) -> None:
        """Verify manifests are ordered by dependency (Namespace first)."""
        from kube_orchestrator.manifest.validator import order_by_dependency

        manifests = [
            {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "app"}},
            {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "config"}},
            {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "my-ns"}},
        ]
        ordered = order_by_dependency(manifests)
        kinds = [m["kind"] for m in ordered]
        assert kinds[0] == "Namespace"
