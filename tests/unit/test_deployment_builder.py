"""Unit tests for kube_orchestrator.resources.workloads._builders.deployment_builder."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.workloads._builders.deployment_builder import (
    DeploymentBuilder,
)
from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder


@pytest.mark.unit
class TestDeploymentBuilderMetadata:
    def test_minimal_build(self) -> None:
        manifest = DeploymentBuilder("web").build()
        assert manifest["apiVersion"] == "apps/v1"
        assert manifest["kind"] == "Deployment"
        assert manifest["metadata"] == {"name": "web", "namespace": "default"}

    def test_full_metadata(self) -> None:
        manifest = DeploymentBuilder(
            "web", namespace="prod", labels={"app": "web"}, annotations={"team": "core"}
        ).build()
        assert manifest["metadata"]["labels"] == {"app": "web"}
        assert manifest["metadata"]["annotations"] == {"team": "core"}


@pytest.mark.unit
class TestReplicasAndSelector:
    def test_with_replicas(self) -> None:
        manifest = DeploymentBuilder("web").with_replicas(3).build()
        assert manifest["spec"]["replicas"] == 3

    def test_with_selector_match_labels_only(self) -> None:
        manifest = DeploymentBuilder("web").with_selector({"app": "web"}).build()
        assert manifest["spec"]["selector"] == {"matchLabels": {"app": "web"}}

    def test_with_selector_match_expressions(self) -> None:
        expr = [{"key": "tier", "operator": "In", "values": ["frontend"]}]
        manifest = (
            DeploymentBuilder("web")
            .with_selector({"app": "web"}, match_expressions=expr)
            .build()
        )
        assert manifest["spec"]["selector"]["matchExpressions"] == expr


@pytest.mark.unit
class TestStrategy:
    def test_with_rolling_update(self) -> None:
        manifest = (
            DeploymentBuilder("web")
            .with_rolling_update(max_surge=2, max_unavailable=1)
            .build()
        )
        assert manifest["spec"]["strategy"] == {
            "type": "RollingUpdate",
            "rollingUpdate": {"maxSurge": 2, "maxUnavailable": 1},
        }

    def test_with_recreate_strategy(self) -> None:
        manifest = DeploymentBuilder("web").with_recreate_strategy().build()
        assert manifest["spec"]["strategy"] == {"type": "Recreate"}


@pytest.mark.unit
class TestRolloutControls:
    def test_with_revision_history_limit(self) -> None:
        manifest = DeploymentBuilder("web").with_revision_history_limit(5).build()
        assert manifest["spec"]["revisionHistoryLimit"] == 5

    def test_with_progress_deadline(self) -> None:
        manifest = DeploymentBuilder("web").with_progress_deadline(600).build()
        assert manifest["spec"]["progressDeadlineSeconds"] == 600

    def test_with_min_ready_seconds(self) -> None:
        manifest = DeploymentBuilder("web").with_min_ready_seconds(10).build()
        assert manifest["spec"]["minReadySeconds"] == 10

    def test_with_paused(self) -> None:
        manifest = DeploymentBuilder("web").with_paused(True).build()
        assert manifest["spec"]["paused"] is True


@pytest.mark.unit
class TestPodTemplate:
    def test_uses_pod_labels_when_present(self) -> None:
        pod = PodBuilder("web", labels={"app": "web"}).with_container("app", "nginx")
        manifest = (
            DeploymentBuilder("web")
            .with_selector({"app": "web"})
            .with_pod_template(pod)
            .build()
        )
        template = manifest["spec"]["template"]
        assert template["metadata"]["labels"] == {"app": "web"}
        assert template["spec"]["containers"][0]["name"] == "app"

    def test_falls_back_to_selector_labels_when_pod_has_none(self) -> None:
        pod = PodBuilder("web").with_container("app", "nginx")
        manifest = (
            DeploymentBuilder("web")
            .with_selector({"app": "web"})
            .with_pod_template(pod)
            .build()
        )
        assert manifest["spec"]["template"]["metadata"]["labels"] == {"app": "web"}

    def test_includes_pod_annotations(self) -> None:
        pod = PodBuilder("web", annotations={"team": "core"}).with_container(
            "app", "nginx"
        )
        manifest = DeploymentBuilder("web").with_pod_template(pod).build()
        assert manifest["spec"]["template"]["metadata"]["annotations"] == {
            "team": "core"
        }

    def test_without_selector_or_pod_labels_has_no_labels(self) -> None:
        pod = PodBuilder("web").with_container("app", "nginx")
        manifest = DeploymentBuilder("web").with_pod_template(pod).build()
        assert "labels" not in manifest["spec"]["template"]["metadata"]


@pytest.mark.unit
class TestBuildAssembly:
    def test_full_chain(self) -> None:
        pod = PodBuilder("web", labels={"app": "web"}).with_container("app", "nginx")
        manifest = (
            DeploymentBuilder("web", namespace="prod")
            .with_replicas(3)
            .with_selector({"app": "web"})
            .with_rolling_update()
            .with_revision_history_limit(3)
            .with_pod_template(pod)
            .build()
        )
        assert manifest["spec"]["replicas"] == 3
        assert manifest["spec"]["strategy"]["type"] == "RollingUpdate"
        assert manifest["spec"]["template"]["spec"]["containers"][0]["image"] == "nginx"
