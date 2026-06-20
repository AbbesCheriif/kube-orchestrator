"""Integration tests for the full apply workflow."""
from __future__ import annotations

from pathlib import Path

import pytest


EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.integration
@pytest.mark.slow
class TestApplyWorkflow:
    def test_dry_run_nginx_deployment(self, kube_client) -> None:
        """Load, validate, render and dry-run apply the nginx example manifest."""
        from kube_orchestrator.manifest.applier import ManifestApplier
        from kube_orchestrator.manifest.loader import load_file
        from kube_orchestrator.manifest.validator import validate_manifest

        manifest_path = EXAMPLES_DIR / "nginx-deployment.yaml"
        if not manifest_path.exists():
            pytest.skip("nginx-deployment.yaml example not found")

        manifests = load_file(str(manifest_path))
        assert len(manifests) > 0

        for manifest in manifests:
            errors = validate_manifest(manifest)
            assert errors == [], f"Validation errors: {errors}"

        applier = ManifestApplier(client=kube_client, dry_run=True, force=False, server_side=False)
        results = applier.apply_file(str(manifest_path), namespace="default")
        assert all(r.get("dry_run") is True for r in results)

    def test_apply_and_delete_configmap(self, kube_client, test_namespace) -> None:
        """Apply a ConfigMap, verify it exists, then delete it."""
        from kube_orchestrator.resources.storage.configmap import ConfigMapManager

        manager = ConfigMapManager(kube_client=kube_client)
        manager.create_configmap(
            name="integration-test-cm",
            namespace=test_namespace,
            data={"key": "value", "env": "test"},
        )
        cm = manager.get_configmap("integration-test-cm", test_namespace)
        assert cm.data["key"] == "value"
        manager.delete_configmap("integration-test-cm", test_namespace)
        from kube_orchestrator.core.exceptions import ResourceNotFoundError

        with pytest.raises(Exception):
            manager.get_configmap("integration-test-cm", test_namespace)
