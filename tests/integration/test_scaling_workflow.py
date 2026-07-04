"""Integration tests for the ScalingEngine workflow."""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestScalingWorkflow:
    def test_scale_with_strategy_changes_replica_count(
        self, kube_client, test_namespace
    ) -> None:
        """A CPU strategy reporting high utilization should scale a Deployment up."""
        from kube_orchestrator.resources.workloads._builders.deployment_builder import (
            DeploymentBuilder,
        )
        from kube_orchestrator.resources.workloads._builders.pod_builder import (
            PodBuilder,
        )
        from kube_orchestrator.resources.workloads.deployment import DeploymentManager
        from kube_orchestrator.scaling.engine import CPUScalingStrategy, ScalingEngine

        dep_manager = DeploymentManager(kube_client=kube_client)
        engine = ScalingEngine(client=kube_client)

        pod = PodBuilder("scale-target").with_container("app", "nginx:1.24")
        builder = (
            DeploymentBuilder("scale-target", test_namespace)
            .with_replicas(1)
            .with_selector({"app": "scale-target"})
            .with_pod_template(pod)
        )
        dep_manager.create_deployment(builder=builder, namespace=test_namespace)

        strategy = CPUScalingStrategy(target_cpu_utilization=50)
        engine.scale_with_strategy(
            "scale-target",
            test_namespace,
            "Deployment",
            strategy,
            metrics={"cpu_utilization": 100},
        )

        updated = dep_manager.get_deployment("scale-target", test_namespace)
        assert updated.spec.replicas == 2

        dep_manager.delete_deployment("scale-target", test_namespace)

    def test_metrics_client_handles_missing_metrics_server_gracefully(
        self, kube_client, test_namespace
    ) -> None:
        """Without metrics-server installed, MetricsClient must degrade to empty results."""
        from kube_orchestrator.scaling.metrics import MetricsClient

        metrics_client = MetricsClient(client=kube_client)
        result = metrics_client.list_pod_metrics(test_namespace)
        assert isinstance(result, list)

    def test_resource_watcher_starts_and_stops_cleanly(
        self, kube_client, test_namespace
    ) -> None:
        """ResourceWatcher.watch_pods should start a background watch and stop cleanly."""
        from kube_orchestrator.controllers.watcher import ResourceWatcher

        watcher = ResourceWatcher(client=kube_client)
        events: list[str] = []
        watcher.watch_pods(
            test_namespace, timeout_seconds=5, callback=lambda t, o: events.append(t)
        )
        watcher.stop_all()
