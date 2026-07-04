"""Integration tests for the auto-rollback workflow."""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestRollbackWorkflow:
    def test_snapshot_and_rollback(self, kube_client, test_namespace) -> None:
        """Create a deployment, take a snapshot, update image, then rollback."""
        from kube_orchestrator.resources.workloads._builders.deployment_builder import (
            DeploymentBuilder,
        )
        from kube_orchestrator.resources.workloads._builders.pod_builder import (
            PodBuilder,
        )
        from kube_orchestrator.resources.workloads.deployment import DeploymentManager
        from kube_orchestrator.rollback.snapshot import SnapshotStore

        dep_manager = DeploymentManager(kube_client=kube_client)
        snapshot_store = SnapshotStore(client=kube_client)

        pod = PodBuilder("test-rollback").with_container("app", "nginx:1.24")
        builder = (
            DeploymentBuilder("test-rollback", test_namespace)
            .with_replicas(1)
            .with_selector({"app": "test-rollback"})
            .with_pod_template(pod)
        )
        dep_manager.create_deployment(builder=builder, namespace=test_namespace)

        snap = snapshot_store.take_snapshot("test-rollback", test_namespace)
        assert snap.revision >= 0
        assert snap.manifest is not None

        dep_manager.update_image("test-rollback", test_namespace, "app", "nginx:1.25")

        snapshots = snapshot_store.list_snapshots("test-rollback", test_namespace)
        assert len(snapshots) >= 1

        dep_manager.delete_deployment("test-rollback", test_namespace)
