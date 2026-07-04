"""Unit tests for DeploymentManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError, ResourceNotFoundError
from kube_orchestrator.resources.workloads.deployment import DeploymentManager


@pytest.fixture
def dep_manager(mock_kube_client: MagicMock) -> DeploymentManager:
    return DeploymentManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestDeploymentManagerCreate:
    def test_create_from_manifest(
        self,
        dep_manager: DeploymentManager,
        mock_apps_v1: MagicMock,
        sample_deployment_manifest: dict,
    ) -> None:
        mock_apps_v1.create_namespaced_deployment.return_value = MagicMock()
        dep_manager.create_deployment(
            manifest=sample_deployment_manifest, namespace="default"
        )
        mock_apps_v1.create_namespaced_deployment.assert_called_once()

    def test_get_deployment(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_dep = MagicMock()
        mock_apps_v1.read_namespaced_deployment.return_value = mock_dep
        result = dep_manager.get_deployment("test-deploy", "default")
        assert result is mock_dep

    def test_list_deployments(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_list = MagicMock()
        mock_list.items = [MagicMock(), MagicMock(), MagicMock()]
        mock_apps_v1.list_namespaced_deployment.return_value = mock_list
        result = dep_manager.list_deployments("default")
        assert len(result) == 3

    def test_scale(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_scale = MagicMock()
        mock_apps_v1.patch_namespaced_deployment_scale.return_value = mock_scale
        dep_manager.scale("test-deploy", "default", replicas=5)
        mock_apps_v1.patch_namespaced_deployment_scale.assert_called_once()

    def test_delete_deployment(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep_manager.delete_deployment("test-deploy", "default")
        mock_apps_v1.delete_namespaced_deployment.assert_called_once()

    def test_is_available_true(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_dep = MagicMock()
        mock_condition = MagicMock()
        mock_condition.type = "Available"
        mock_condition.status = "True"
        mock_dep.status.conditions = [mock_condition]
        mock_apps_v1.read_namespaced_deployment.return_value = mock_dep
        assert dep_manager.is_available("test-deploy", "default") is True

    def test_is_available_false(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_dep = MagicMock()
        mock_dep.status.conditions = []
        mock_apps_v1.read_namespaced_deployment.return_value = mock_dep
        assert dep_manager.is_available("test-deploy", "default") is False

    def test_pause_rollout(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_dep = MagicMock()
        mock_dep.spec.paused = False
        mock_apps_v1.read_namespaced_deployment.return_value = mock_dep
        mock_apps_v1.patch_namespaced_deployment.return_value = mock_dep
        dep_manager.pause_rollout("test-deploy", "default")
        mock_apps_v1.patch_namespaced_deployment.assert_called_once()

    def test_create_from_builder(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        from kube_orchestrator.resources.workloads._builders.deployment_builder import (
            DeploymentBuilder,
        )

        builder = DeploymentBuilder("web").with_replicas(2)
        mock_apps_v1.create_namespaced_deployment.return_value = MagicMock()
        dep_manager.create_deployment(builder=builder, namespace="default")
        mock_apps_v1.create_namespaced_deployment.assert_called_once()

    def test_create_without_builder_or_manifest_raises(
        self, dep_manager: DeploymentManager
    ) -> None:
        with pytest.raises(ValueError, match="requires either a builder or a manifest"):
            dep_manager.create_deployment()

    def test_update_deployment(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep_manager.update_deployment("test-deploy", "default", {"spec": {}})
        mock_apps_v1.replace_namespaced_deployment.assert_called_once()

    def test_patch_deployment(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep_manager.patch_deployment("test-deploy", "default", {"spec": {}})
        mock_apps_v1.patch_namespaced_deployment.assert_called_once()

    def test_scale_raises_parsed_exception(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.patch_namespaced_deployment_scale.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            dep_manager.scale("test-deploy", "default", replicas=3)


@pytest.mark.unit
class TestContainerMutations:
    def test_update_image(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep_manager.update_image("test-deploy", "default", "app", "nginx:1.25")
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args.kwargs
        container = call_kwargs["body"]["spec"]["template"]["spec"]["containers"][0]
        assert container["image"] == "nginx:1.25"

    def test_set_env_var(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep_manager.set_env_var("test-deploy", "default", "app", "FOO", "bar")
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args.kwargs
        container = call_kwargs["body"]["spec"]["template"]["spec"]["containers"][0]
        assert container["env"] == [{"name": "FOO", "value": "bar"}]

    def test_set_resource_limits(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep_manager.set_resource_limits(
            "test-deploy", "default", "app", cpu_limit="1", memory_limit="1Gi"
        )
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args.kwargs
        container = call_kwargs["body"]["spec"]["template"]["spec"]["containers"][0]
        assert container["resources"]["limits"] == {"cpu": "1", "memory": "1Gi"}


@pytest.mark.unit
class TestRolloutManagement:
    def test_get_rollout_status(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep = MagicMock()
        dep.status.replicas = 3
        dep.status.ready_replicas = 3
        dep.status.available_replicas = 3
        dep.status.updated_replicas = 3
        dep.status.observed_generation = 1
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        status = dep_manager.get_rollout_status("test-deploy", "default")
        assert status["replicas"] == 3
        assert status["observed_generation"] == 1

    def test_get_rollout_status_without_status(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep = MagicMock(status=None)
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        status = dep_manager.get_rollout_status("test-deploy", "default")
        assert status["replicas"] == 0

    def test_wait_for_rollout_returns_true(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep = MagicMock()
        dep.spec.replicas = 3
        dep.status.updated_replicas = 3
        dep.status.ready_replicas = 3
        dep.status.available_replicas = 3
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        assert (
            dep_manager.wait_for_rollout("test-deploy", "default", timeout_seconds=5)
            is True
        )

    def test_wait_for_rollout_ignores_not_found_and_times_out(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.read_namespaced_deployment.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.workloads.deployment.time.sleep"):
            assert (
                dep_manager.wait_for_rollout(
                    "test-deploy", "default", timeout_seconds=0.05
                )
                is False
            )

    def test_resume_rollout(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep_manager.resume_rollout("test-deploy", "default")
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args.kwargs
        assert call_kwargs["body"]["spec"]["paused"] is False

    def test_restart_rollout(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep_manager.restart_rollout("test-deploy", "default")
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args.kwargs
        annotations = call_kwargs["body"]["spec"]["template"]["metadata"]["annotations"]
        assert "kubectl.kubernetes.io/restartedAt" in annotations


@pytest.mark.unit
class TestRolloutHistoryAndRollback:
    def _make_replicaset(
        self, name: str, revision: str, deployment_name: str
    ) -> MagicMock:
        ref = MagicMock(kind="Deployment", name=deployment_name)
        ref.name = deployment_name
        rs = MagicMock()
        rs.metadata.name = name
        rs.metadata.owner_references = [ref]
        rs.metadata.annotations = {"deployment.kubernetes.io/revision": revision}
        rs.status.replicas = 1
        rs.status.ready_replicas = 1
        return rs

    def test_get_rollout_history_sorted_by_revision(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        rs2 = self._make_replicaset("web-2", "2", "test-deploy")
        rs1 = self._make_replicaset("web-1", "1", "test-deploy")
        unrelated = MagicMock()
        unrelated.metadata.owner_references = []
        mock_apps_v1.list_namespaced_replica_set.return_value.items = [
            rs2,
            rs1,
            unrelated,
        ]

        history = dep_manager.get_rollout_history("test-deploy", "default")

        assert [h["revision"] for h in history] == ["1", "2"]

    def test_get_rollout_history_raises_parsed_exception(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.list_namespaced_replica_set.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            dep_manager.get_rollout_history("test-deploy", "default")

    def test_rollback_to_revision(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = self._make_replicaset("web-1", "1", "test-deploy")
        rs.spec.template.to_dict.return_value = {"metadata": {}, "spec": {}}
        unowned = MagicMock()
        unowned.metadata.owner_references = None
        mock_apps_v1.list_namespaced_replica_set.return_value.items = [unowned, rs]
        mock_apps_v1.patch_namespaced_deployment.return_value = MagicMock()

        dep_manager.rollback_to_revision("test-deploy", "default", revision=1)

        mock_apps_v1.patch_namespaced_deployment.assert_called_once()

    def test_rollback_to_revision_not_found_raises(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.list_namespaced_replica_set.return_value.items = []
        with pytest.raises(ResourceNotFoundError):
            dep_manager.rollback_to_revision("test-deploy", "default", revision=99)

    def test_rollback_to_revision_raises_parsed_exception(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.list_namespaced_replica_set.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            dep_manager.rollback_to_revision("test-deploy", "default", revision=1)


@pytest.mark.unit
class TestRelatedResources:
    def test_get_pods(
        self,
        dep_manager: DeploymentManager,
        mock_apps_v1: MagicMock,
        mock_core_v1: MagicMock,
    ) -> None:
        dep = MagicMock()
        dep.spec.selector.match_labels = {"app": "web"}
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        mock_core_v1.list_namespaced_pod.return_value.items = ["pod-a"]

        result = dep_manager.get_pods("test-deploy", "default")
        assert result == ["pod-a"]

    def test_get_pods_raises_parsed_exception(
        self,
        dep_manager: DeploymentManager,
        mock_apps_v1: MagicMock,
        mock_core_v1: MagicMock,
    ) -> None:
        dep = MagicMock()
        dep.spec.selector.match_labels = {"app": "web"}
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        mock_core_v1.list_namespaced_pod.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            dep_manager.get_pods("test-deploy", "default")

    def test_get_replica_sets(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        matching = self._make_replicaset("web-1", "1", "test-deploy")
        other = self._make_replicaset("other-1", "1", "other-deploy")
        mock_apps_v1.list_namespaced_replica_set.return_value.items = [matching, other]

        result = dep_manager.get_replica_sets("test-deploy", "default")
        assert result == [matching]

    def test_get_replica_sets_raises_parsed_exception(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.list_namespaced_replica_set.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            dep_manager.get_replica_sets("test-deploy", "default")

    def _make_replicaset(
        self, name: str, revision: str, deployment_name: str
    ) -> MagicMock:
        ref = MagicMock(kind="Deployment", name=deployment_name)
        ref.name = deployment_name
        rs = MagicMock()
        rs.metadata.name = name
        rs.metadata.owner_references = [ref]
        rs.metadata.annotations = {"deployment.kubernetes.io/revision": revision}
        return rs


@pytest.mark.unit
class TestStatusHelpers:
    def test_get_conditions(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        cond = MagicMock(
            type="Progressing",
            status="True",
            reason="NewReplicaSetAvailable",
            message="ok",
        )
        dep = MagicMock()
        dep.status.conditions = [cond]
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        result = dep_manager.get_conditions("test-deploy", "default")
        assert result[0]["type"] == "Progressing"

    def test_get_conditions_empty_without_status(
        self, dep_manager: DeploymentManager, mock_apps_v1: MagicMock
    ) -> None:
        dep = MagicMock(status=None)
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        assert dep_manager.get_conditions("test-deploy", "default") == []

    def test_kind_and_api_version(self, dep_manager: DeploymentManager) -> None:
        assert dep_manager._kind() == "Deployment"
        assert dep_manager._api_version() == "apps/v1"
