"""Unit tests for StatefulSetManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError, ResourceNotFoundError
from kube_orchestrator.resources.workloads.statefulset import StatefulSetManager


@pytest.fixture
def ss_manager(mock_kube_client: MagicMock) -> StatefulSetManager:
    return StatefulSetManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestStatefulSetManager:
    def test_create_statefulset(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.create_namespaced_stateful_set.return_value = MagicMock()
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": "my-ss", "namespace": "default"},
            "spec": {
                "serviceName": "my-ss",
                "replicas": 3,
                "selector": {"matchLabels": {"app": "my-ss"}},
                "template": {
                    "metadata": {"labels": {"app": "my-ss"}},
                    "spec": {"containers": [{"name": "app", "image": "nginx"}]},
                },
                "volumeClaimTemplates": [
                    {
                        "metadata": {"name": "data"},
                        "spec": {
                            "accessModes": ["ReadWriteOnce"],
                            "resources": {"requests": {"storage": "10Gi"}},
                        },
                    }
                ],
            },
        }
        ss_manager.create_statefulset(manifest=manifest, namespace="default")
        mock_apps_v1.create_namespaced_stateful_set.assert_called_once()

    def test_scale(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_scale = MagicMock()
        mock_apps_v1.patch_namespaced_stateful_set_scale.return_value = mock_scale
        ss_manager.scale("my-ss", "default", replicas=2)
        mock_apps_v1.patch_namespaced_stateful_set_scale.assert_called_once()

    def test_set_partition_update(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_ss = MagicMock()
        mock_apps_v1.read_namespaced_stateful_set.return_value = mock_ss
        mock_apps_v1.patch_namespaced_stateful_set.return_value = mock_ss
        ss_manager.set_partition_update("my-ss", "default", partition=2)
        mock_apps_v1.patch_namespaced_stateful_set.assert_called_once()

    def test_create_from_builder(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        from kube_orchestrator.resources.workloads._builders.statefulset_builder import (
            StatefulSetBuilder,
        )

        builder = StatefulSetBuilder("db").with_replicas(1)
        mock_apps_v1.create_namespaced_stateful_set.return_value = MagicMock()
        ss_manager.create_statefulset(builder=builder, namespace="default")
        mock_apps_v1.create_namespaced_stateful_set.assert_called_once()

    def test_create_without_builder_or_manifest_raises(
        self, ss_manager: StatefulSetManager
    ) -> None:
        with pytest.raises(ValueError, match="requires either a builder or a manifest"):
            ss_manager.create_statefulset()

    def test_get_statefulset(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.read_namespaced_stateful_set.return_value = "ss-obj"
        assert ss_manager.get_statefulset("my-ss", "default") == "ss-obj"

    def test_list_statefulsets(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.list_namespaced_stateful_set.return_value.items = ["a"]
        assert ss_manager.list_statefulsets("default") == ["a"]

    def test_update_statefulset(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ss_manager.update_statefulset("my-ss", "default", {"spec": {}})
        mock_apps_v1.replace_namespaced_stateful_set.assert_called_once()

    def test_delete_statefulset(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ss_manager.delete_statefulset("my-ss", "default")
        mock_apps_v1.delete_namespaced_stateful_set.assert_called_once()

    def test_scale_raises_parsed_exception(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.patch_namespaced_stateful_set_scale.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            ss_manager.scale("my-ss", "default", replicas=2)

    def test_kind_and_api_version(self, ss_manager: StatefulSetManager) -> None:
        assert ss_manager._kind() == "StatefulSet"
        assert ss_manager._api_version() == "apps/v1"
        assert ss_manager._resource_name() == "stateful_set"


@pytest.mark.unit
class TestOrderedScaling:
    def test_ordered_scale_up_scales_and_waits(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        sts = MagicMock()
        sts.spec.replicas = 1
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts
        mock_apps_v1.patch_namespaced_stateful_set_scale.return_value = MagicMock()

        pod = MagicMock()
        pod.status.phase = "Running"
        ready_cond = MagicMock(type="Ready", status="True")
        pod.status.conditions = [ready_cond]
        mock_core_v1.read_namespaced_pod.return_value = pod

        ss_manager.ordered_scale_up("my-ss", "default", replicas=2)

        mock_apps_v1.patch_namespaced_stateful_set_scale.assert_called_once()

    def test_ordered_scale_up_without_wait(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        sts = MagicMock()
        sts.spec.replicas = 0
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts
        mock_apps_v1.patch_namespaced_stateful_set_scale.return_value = MagicMock()

        ss_manager.ordered_scale_up("my-ss", "default", replicas=1, wait=False)

        mock_apps_v1.patch_namespaced_stateful_set_scale.assert_called_once()

    def test_ordered_scale_up_without_spec_defaults_current_to_zero(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        sts = MagicMock()
        sts.spec = None
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts
        mock_apps_v1.patch_namespaced_stateful_set_scale.return_value = MagicMock()

        ss_manager.ordered_scale_up("my-ss", "default", replicas=1, wait=False)

        mock_apps_v1.patch_namespaced_stateful_set_scale.assert_called_once()

    def test_ordered_scale_down_scales_and_waits_for_removal(
        self,
        ss_manager: StatefulSetManager,
        mock_apps_v1: MagicMock,
        mock_core_v1: MagicMock,
    ) -> None:
        sts = MagicMock()
        sts.spec.replicas = 2
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts
        mock_apps_v1.patch_namespaced_stateful_set_scale.return_value = MagicMock()
        mock_core_v1.read_namespaced_pod.side_effect = [
            MagicMock(),
            ApiException(status=404),
        ]

        with patch("kube_orchestrator.resources.workloads.statefulset.time.sleep"):
            ss_manager.ordered_scale_down("my-ss", "default", replicas=1)

        mock_apps_v1.patch_namespaced_stateful_set_scale.assert_called_once()

    def test_ordered_scale_down_without_wait(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        sts = MagicMock()
        sts.spec.replicas = 1
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts
        mock_apps_v1.patch_namespaced_stateful_set_scale.return_value = MagicMock()

        ss_manager.ordered_scale_down("my-ss", "default", replicas=0, wait=False)

        mock_apps_v1.patch_namespaced_stateful_set_scale.assert_called_once()


@pytest.mark.unit
class TestPodOrdinalHelpers:
    def test_get_pod_by_ordinal(
        self, ss_manager: StatefulSetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_pod.return_value = "pod-obj"
        assert ss_manager.get_pod_by_ordinal("my-ss", "default", 0) == "pod-obj"
        mock_core_v1.read_namespaced_pod.assert_called_once_with(
            name="my-ss-0", namespace="default"
        )

    def test_get_pod_by_ordinal_raises_parsed_exception(
        self, ss_manager: StatefulSetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_pod.side_effect = ApiException(status=404)
        with pytest.raises(ResourceNotFoundError):
            ss_manager.get_pod_by_ordinal("my-ss", "default", 0)

    def test_wait_for_pod_ordinal_returns_true_when_ready(
        self, ss_manager: StatefulSetManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.status.phase = "Running"
        ready_cond = MagicMock(type="Ready", status="True")
        pod.status.conditions = [ready_cond]
        mock_core_v1.read_namespaced_pod.return_value = pod

        assert (
            ss_manager.wait_for_pod_ordinal("my-ss", "default", 0, timeout_seconds=5)
            is True
        )

    def test_wait_for_pod_ordinal_times_out(
        self, ss_manager: StatefulSetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_pod.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.workloads.statefulset.time.sleep"):
            assert (
                ss_manager.wait_for_pod_ordinal(
                    "my-ss", "default", 0, timeout_seconds=0.05
                )
                is False
            )

    def test_wait_for_pod_ordinal_not_ready_pod_keeps_polling(
        self, ss_manager: StatefulSetManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.status.phase = "Pending"
        pod.status.conditions = []
        mock_core_v1.read_namespaced_pod.return_value = pod
        with patch("kube_orchestrator.resources.workloads.statefulset.time.sleep"):
            assert (
                ss_manager.wait_for_pod_ordinal(
                    "my-ss", "default", 0, timeout_seconds=0.05
                )
                is False
            )


@pytest.mark.unit
class TestRolloutStatusAndPvcs:
    def test_get_rollout_status_fully_rolled_out(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        sts = MagicMock()
        sts.spec.replicas = 3
        sts.status.replicas = 3
        sts.status.ready_replicas = 3
        sts.status.current_replicas = 3
        sts.status.updated_replicas = 3
        sts.status.available_replicas = 3
        sts.status.observed_generation = 1
        sts.status.current_revision = "rev-1"
        sts.status.update_revision = "rev-1"
        sts.status.collision_count = 0
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts

        status = ss_manager.get_rollout_status("my-ss", "default")
        assert status["fully_rolled_out"] is True

    def test_get_rollout_status_without_status(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        sts = MagicMock(status=None)
        sts.spec.replicas = 1
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts
        status = ss_manager.get_rollout_status("my-ss", "default")
        assert status["replicas"] == 0
        assert status["fully_rolled_out"] is False

    def test_get_persistent_volume_claims(
        self, ss_manager: StatefulSetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_persistent_volume_claim.return_value.items = [
            "pvc-a"
        ]
        result = ss_manager.get_persistent_volume_claims("my-ss", "default")
        assert result == ["pvc-a"]

    def test_get_persistent_volume_claims_raises_parsed_exception(
        self, ss_manager: StatefulSetManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_persistent_volume_claim.side_effect = (
            ApiException(status=500)
        )
        with pytest.raises(APIError):
            ss_manager.get_persistent_volume_claims("my-ss", "default")


@pytest.mark.unit
class TestContainerMutationsAndRestart:
    def test_update_image_replaces_matching_container(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        container = MagicMock()
        container.name = "app"
        sts = MagicMock()
        sts.spec.template.spec.containers = [container]
        sts.to_dict.return_value = {"spec": {}}
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts

        ss_manager.update_image("my-ss", "default", "app", "postgres:16")

        assert container.image == "postgres:16"
        mock_apps_v1.replace_namespaced_stateful_set.assert_called_once()

    def test_update_image_without_template_spec(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        sts = MagicMock()
        sts.spec.template = None
        sts.to_dict.return_value = {"spec": {}}
        mock_apps_v1.read_namespaced_stateful_set.return_value = sts

        ss_manager.update_image("my-ss", "default", "app", "postgres:16")

        mock_apps_v1.replace_namespaced_stateful_set.assert_called_once()

    def test_restart(
        self, ss_manager: StatefulSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ss_manager.restart("my-ss", "default")
        call_kwargs = mock_apps_v1.patch_namespaced_stateful_set.call_args.kwargs
        annotations = call_kwargs["body"]["spec"]["template"]["metadata"]["annotations"]
        assert "kubectl.kubernetes.io/restartedAt" in annotations
