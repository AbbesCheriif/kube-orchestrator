"""Unit tests for kube_orchestrator.resources.workloads._builders.statefulset_builder."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder
from kube_orchestrator.resources.workloads._builders.statefulset_builder import (
    StatefulSetBuilder,
)


@pytest.mark.unit
class TestStatefulSetBuilderMetadata:
    def test_minimal_build(self) -> None:
        manifest = StatefulSetBuilder("db").build()
        assert manifest["apiVersion"] == "apps/v1"
        assert manifest["kind"] == "StatefulSet"
        assert manifest["metadata"] == {"name": "db", "namespace": "default"}

    def test_full_metadata(self) -> None:
        manifest = StatefulSetBuilder(
            "db", namespace="prod", labels={"app": "db"}, annotations={"team": "core"}
        ).build()
        assert manifest["metadata"]["labels"] == {"app": "db"}
        assert manifest["metadata"]["annotations"] == {"team": "core"}


@pytest.mark.unit
class TestReplicasServiceSelector:
    def test_with_replicas(self) -> None:
        assert StatefulSetBuilder("db").with_replicas(3).build()["spec"]["replicas"] == 3

    def test_with_service_name(self) -> None:
        manifest = StatefulSetBuilder("db").with_service_name("db-headless").build()
        assert manifest["spec"]["serviceName"] == "db-headless"

    def test_with_selector_match_labels_only(self) -> None:
        manifest = StatefulSetBuilder("db").with_selector({"app": "db"}).build()
        assert manifest["spec"]["selector"] == {"matchLabels": {"app": "db"}}

    def test_with_selector_match_expressions(self) -> None:
        expr = [{"key": "tier", "operator": "In", "values": ["backend"]}]
        manifest = StatefulSetBuilder("db").with_selector(
            {"app": "db"}, match_expressions=expr
        ).build()
        assert manifest["spec"]["selector"]["matchExpressions"] == expr


@pytest.mark.unit
class TestPodManagementAndStrategy:
    def test_with_pod_management_policy(self) -> None:
        manifest = StatefulSetBuilder("db").with_pod_management_policy("Parallel").build()
        assert manifest["spec"]["podManagementPolicy"] == "Parallel"

    def test_with_rolling_update_minimal(self) -> None:
        manifest = StatefulSetBuilder("db").with_rolling_update().build()
        assert manifest["spec"]["updateStrategy"] == {
            "type": "RollingUpdate",
            "rollingUpdate": {"partition": 0},
        }

    def test_with_rolling_update_with_max_unavailable(self) -> None:
        manifest = StatefulSetBuilder("db").with_rolling_update(
            max_unavailable=1, partition=2
        ).build()
        rolling = manifest["spec"]["updateStrategy"]["rollingUpdate"]
        assert rolling == {"partition": 2, "maxUnavailable": 1}

    def test_with_on_delete_strategy(self) -> None:
        manifest = StatefulSetBuilder("db").with_on_delete_strategy().build()
        assert manifest["spec"]["updateStrategy"] == {"type": "OnDelete"}


@pytest.mark.unit
class TestRolloutControls:
    def test_with_revision_history_limit(self) -> None:
        manifest = StatefulSetBuilder("db").with_revision_history_limit(5).build()
        assert manifest["spec"]["revisionHistoryLimit"] == 5

    def test_with_min_ready_seconds(self) -> None:
        manifest = StatefulSetBuilder("db").with_min_ready_seconds(10).build()
        assert manifest["spec"]["minReadySeconds"] == 10

    def test_with_ordinals(self) -> None:
        manifest = StatefulSetBuilder("db").with_ordinals(2).build()
        assert manifest["spec"]["ordinals"] == {"start": 2}

    def test_with_pvc_retention_policy_defaults(self) -> None:
        manifest = StatefulSetBuilder("db").with_pvc_retention_policy().build()
        assert manifest["spec"]["persistentVolumeClaimRetentionPolicy"] == {
            "whenDeleted": "Retain",
            "whenScaled": "Retain",
        }

    def test_with_pvc_retention_policy_custom(self) -> None:
        manifest = StatefulSetBuilder("db").with_pvc_retention_policy(
            when_deleted="Delete", when_scaled="Delete"
        ).build()
        policy = manifest["spec"]["persistentVolumeClaimRetentionPolicy"]
        assert policy == {"whenDeleted": "Delete", "whenScaled": "Delete"}


@pytest.mark.unit
class TestVolumeClaimTemplates:
    def test_add_volume_claim_template_minimal(self) -> None:
        manifest = StatefulSetBuilder("db").add_volume_claim_template(
            "data", "10Gi", ["ReadWriteOnce"]
        ).build()
        pvc = manifest["spec"]["volumeClaimTemplates"][0]
        assert pvc["metadata"]["name"] == "data"
        assert pvc["spec"]["resources"]["requests"]["storage"] == "10Gi"

    def test_add_volume_claim_template_full(self) -> None:
        manifest = StatefulSetBuilder("db").add_volume_claim_template(
            "data",
            "10Gi",
            ["ReadWriteOnce"],
            storage_class_name="fast",
            volume_mode="Filesystem",
            selector={"matchLabels": {"tier": "gold"}},
        ).build()
        pvc_spec = manifest["spec"]["volumeClaimTemplates"][0]["spec"]
        assert pvc_spec["storageClassName"] == "fast"
        assert pvc_spec["volumeMode"] == "Filesystem"
        assert pvc_spec["selector"]["matchLabels"] == {"tier": "gold"}

    def test_multiple_templates_accumulate(self) -> None:
        builder = StatefulSetBuilder("db")
        builder.add_volume_claim_template("data", "10Gi", ["ReadWriteOnce"])
        builder.add_volume_claim_template("logs", "5Gi", ["ReadWriteOnce"])
        manifest = builder.build()
        assert len(manifest["spec"]["volumeClaimTemplates"]) == 2


@pytest.mark.unit
class TestPodTemplateAndAssembly:
    def test_with_pod_template(self) -> None:
        pod = PodBuilder("db", labels={"app": "db"}).with_container("app", "postgres")
        manifest = StatefulSetBuilder("db").with_pod_template(pod).build()
        template = manifest["spec"]["template"]
        assert template["metadata"]["labels"] == {"app": "db"}
        assert template["spec"]["containers"][0]["image"] == "postgres"

    def test_full_chain(self) -> None:
        pod = PodBuilder("db").with_container("app", "postgres")
        manifest = (
            StatefulSetBuilder("db", namespace="prod")
            .with_replicas(3)
            .with_service_name("db-headless")
            .with_selector({"app": "db"})
            .with_rolling_update(partition=1)
            .add_volume_claim_template("data", "10Gi", ["ReadWriteOnce"])
            .with_pod_template(pod)
            .build()
        )
        assert manifest["spec"]["replicas"] == 3
        assert manifest["spec"]["serviceName"] == "db-headless"
        assert manifest["spec"]["updateStrategy"]["rollingUpdate"]["partition"] == 1
        assert len(manifest["spec"]["volumeClaimTemplates"]) == 1
