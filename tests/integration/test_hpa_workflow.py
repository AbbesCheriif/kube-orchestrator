"""Integration tests for the HorizontalPodAutoscaler workflow."""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestHpaWorkflow:
    def test_create_scale_and_delete_cpu_hpa(self, kube_client, test_namespace) -> None:
        """Create a Deployment, attach a CPU-based HPA, then tear both down."""
        from kube_orchestrator.resources.cluster.hpa import HPAManager
        from kube_orchestrator.resources.workloads._builders.deployment_builder import (
            DeploymentBuilder,
        )
        from kube_orchestrator.resources.workloads._builders.pod_builder import (
            PodBuilder,
        )
        from kube_orchestrator.resources.workloads.deployment import DeploymentManager

        dep_manager = DeploymentManager(kube_client=kube_client)
        hpa_manager = HPAManager(kube_client=kube_client)

        pod = (
            PodBuilder("hpa-target")
            .with_container("app", "nginx:1.24")
            .with_resources("app", cpu_request="50m")
        )
        builder = (
            DeploymentBuilder("hpa-target", test_namespace)
            .with_replicas(1)
            .with_selector({"app": "hpa-target"})
            .with_pod_template(pod)
        )
        dep_manager.create_deployment(builder=builder, namespace=test_namespace)

        hpa_manager.create_cpu_hpa(
            "hpa-target",
            test_namespace,
            target_kind="Deployment",
            target_name="hpa-target",
            min_replicas=1,
            max_replicas=3,
            target_cpu_utilization=80,
        )

        hpa = hpa_manager.get_hpa("hpa-target", test_namespace)
        assert hpa.spec.max_replicas == 3

        hpa_manager.delete_hpa("hpa-target", test_namespace)
        dep_manager.delete_deployment("hpa-target", test_namespace)

    def test_hpa_status_helpers_reflect_live_state(
        self, kube_client, test_namespace
    ) -> None:
        """get_current_replicas/get_conditions should not raise against a live HPA."""
        from kube_orchestrator.resources.cluster.hpa import HPAManager
        from kube_orchestrator.resources.workloads._builders.deployment_builder import (
            DeploymentBuilder,
        )
        from kube_orchestrator.resources.workloads._builders.pod_builder import (
            PodBuilder,
        )
        from kube_orchestrator.resources.workloads.deployment import DeploymentManager

        dep_manager = DeploymentManager(kube_client=kube_client)
        hpa_manager = HPAManager(kube_client=kube_client)

        pod = PodBuilder("hpa-status").with_container("app", "nginx:1.24")
        builder = (
            DeploymentBuilder("hpa-status", test_namespace)
            .with_replicas(1)
            .with_selector({"app": "hpa-status"})
            .with_pod_template(pod)
        )
        dep_manager.create_deployment(builder=builder, namespace=test_namespace)
        hpa_manager.create_cpu_hpa(
            "hpa-status",
            test_namespace,
            target_name="hpa-status",
            min_replicas=1,
            max_replicas=2,
        )

        # These read live status fields — must not raise even before the HPA
        # has produced any metrics yet.
        hpa_manager.get_current_replicas("hpa-status", test_namespace)
        hpa_manager.get_conditions("hpa-status", test_namespace)

        hpa_manager.delete_hpa("hpa-status", test_namespace)
        dep_manager.delete_deployment("hpa-status", test_namespace)
