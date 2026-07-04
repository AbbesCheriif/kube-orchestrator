"""Unit tests for DaemonSetManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError
from kube_orchestrator.resources.workloads.daemonset import DaemonSetManager


@pytest.fixture
def ds_manager(mock_kube_client: MagicMock) -> DaemonSetManager:
    return DaemonSetManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestDaemonSetManager:
    def test_create_daemonset(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.create_namespaced_daemon_set.return_value = MagicMock()
        ds_manager.create_daemonset(
            name="fluentd",
            namespace="kube-system",
            selector={"matchLabels": {"app": "fluentd"}},
            pod_template={
                "metadata": {"labels": {"app": "fluentd"}},
                "spec": {
                    "containers": [{"name": "fluentd", "image": "fluentd:latest"}]
                },
            },
        )
        mock_apps_v1.create_namespaced_daemon_set.assert_called_once()

    def test_update_image(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        container = MagicMock()
        container.name = "fluentd"
        mock_ds = MagicMock()
        mock_ds.spec.template.spec.containers = [container]
        mock_ds.to_dict.return_value = {"spec": {}}
        mock_apps_v1.read_namespaced_daemon_set.return_value = mock_ds
        mock_apps_v1.replace_namespaced_daemon_set.return_value = mock_ds
        ds_manager.update_image("fluentd", "kube-system", "fluentd", "fluentd:v2")
        assert container.image == "fluentd:v2"
        mock_apps_v1.replace_namespaced_daemon_set.assert_called_once()

    def test_set_node_selector(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_ds = MagicMock()
        mock_apps_v1.read_namespaced_daemon_set.return_value = mock_ds
        mock_apps_v1.patch_namespaced_daemon_set.return_value = mock_ds
        ds_manager.set_node_selector("fluentd", "kube-system", {"node-role": "worker"})
        mock_apps_v1.patch_namespaced_daemon_set.assert_called_once()

    def test_create_daemonset_with_all_options(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds_manager.create_daemonset(
            "fluentd",
            "kube-system",
            update_strategy={"type": "OnDelete"},
            min_ready_seconds=5,
            revision_history_limit=3,
            labels={"app": "fluentd"},
        )
        call_kwargs = mock_apps_v1.create_namespaced_daemon_set.call_args.kwargs
        spec = call_kwargs["body"]["spec"]
        assert spec["updateStrategy"] == {"type": "OnDelete"}
        assert spec["minReadySeconds"] == 5
        assert spec["revisionHistoryLimit"] == 3

    def test_get_daemonset(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.read_namespaced_daemon_set.return_value = "ds-obj"
        assert ds_manager.get_daemonset("fluentd", "kube-system") == "ds-obj"

    def test_list_daemonsets(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.list_namespaced_daemon_set.return_value.items = ["a"]
        assert ds_manager.list_daemonsets("kube-system") == ["a"]

    def test_update_daemonset(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds_manager.update_daemonset("fluentd", "kube-system", {"spec": {}})
        mock_apps_v1.replace_namespaced_daemon_set.assert_called_once()

    def test_delete_daemonset(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds_manager.delete_daemonset("fluentd", "kube-system")
        mock_apps_v1.delete_namespaced_daemon_set.assert_called_once()

    def test_update_image_without_matching_container_or_template(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_ds = MagicMock()
        mock_ds.spec.template = None
        mock_ds.to_dict.return_value = {"spec": {}}
        mock_apps_v1.read_namespaced_daemon_set.return_value = mock_ds
        mock_apps_v1.replace_namespaced_daemon_set.return_value = mock_ds
        ds_manager.update_image("fluentd", "kube-system", "fluentd", "fluentd:v2")
        mock_apps_v1.replace_namespaced_daemon_set.assert_called_once()

    def test_kind_and_api_version(self, ds_manager: DaemonSetManager) -> None:
        assert ds_manager._kind() == "DaemonSet"
        assert ds_manager._api_version() == "apps/v1"
        assert ds_manager._resource_name() == "daemon_set"


@pytest.mark.unit
class TestUpdateStrategies:
    def test_set_rolling_update_strategy_with_max_surge(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds_manager.set_rolling_update_strategy(
            "fluentd", "kube-system", max_unavailable=2, max_surge=1
        )
        call_kwargs = mock_apps_v1.patch_namespaced_daemon_set.call_args.kwargs
        rolling = call_kwargs["body"]["spec"]["updateStrategy"]["rollingUpdate"]
        assert rolling == {"maxUnavailable": 2, "maxSurge": 1}

    def test_set_on_delete_strategy(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds_manager.set_on_delete_strategy("fluentd", "kube-system")
        call_kwargs = mock_apps_v1.patch_namespaced_daemon_set.call_args.kwargs
        assert call_kwargs["body"]["spec"]["updateStrategy"] == {"type": "OnDelete"}


@pytest.mark.unit
class TestSchedulingHelpers:
    def test_add_toleration_to_empty_list(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds = MagicMock()
        ds.spec.template.spec.tolerations = None
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds

        ds_manager.add_toleration(
            "fluentd",
            "kube-system",
            key="dedicated",
            value="infra",
            effect="NoSchedule",
            toleration_seconds=30,
        )

        call_kwargs = mock_apps_v1.patch_namespaced_daemon_set.call_args.kwargs
        tolerations = call_kwargs["body"]["spec"]["template"]["spec"]["tolerations"]
        assert tolerations[0]["key"] == "dedicated"
        assert tolerations[0]["tolerationSeconds"] == 30

    def test_add_toleration_appends_to_existing(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        existing_tol = MagicMock()
        existing_tol.to_dict.return_value = {"key": "existing", "operator": "Exists"}
        ds = MagicMock()
        ds.spec.template.spec.tolerations = [existing_tol]
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds

        ds_manager.add_toleration("fluentd", "kube-system", key="new")

        call_kwargs = mock_apps_v1.patch_namespaced_daemon_set.call_args.kwargs
        tolerations = call_kwargs["body"]["spec"]["template"]["spec"]["tolerations"]
        assert len(tolerations) == 2

    def test_add_toleration_without_template_spec(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds = MagicMock()
        ds.spec.template = None
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds

        ds_manager.add_toleration("fluentd", "kube-system", key="new")

        call_kwargs = mock_apps_v1.patch_namespaced_daemon_set.call_args.kwargs
        tolerations = call_kwargs["body"]["spec"]["template"]["spec"]["tolerations"]
        assert tolerations == [{"key": "new", "operator": "Equal"}]


@pytest.mark.unit
class TestStatusHelpers:
    def test_get_desired_scheduled(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds = MagicMock()
        ds.status.desired_number_scheduled = 5
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds
        assert ds_manager.get_desired_scheduled("fluentd", "kube-system") == 5

    def test_get_desired_scheduled_without_status(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds = MagicMock(status=None)
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds
        assert ds_manager.get_desired_scheduled("fluentd", "kube-system") == 0

    def test_get_number_ready(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds = MagicMock()
        ds.status.number_ready = 4
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds
        assert ds_manager.get_number_ready("fluentd", "kube-system") == 4

    def test_get_pods_per_node(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        ds = MagicMock()
        ds.spec.selector.match_labels = {"app": "fluentd"}
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds
        pod = MagicMock()
        pod.spec.node_name = "worker-1"
        mock_core_v1.list_namespaced_pod.return_value.items = [pod]

        result = ds_manager.get_pods_per_node("fluentd", "kube-system")
        assert result == {"worker-1": pod}

    def test_get_pods_per_node_raises_parsed_exception(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        ds = MagicMock()
        ds.spec.selector.match_labels = {"app": "fluentd"}
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds
        mock_core_v1.list_namespaced_pod.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            ds_manager.get_pods_per_node("fluentd", "kube-system")

    def test_get_rollout_status_fully_rolled_out(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds = MagicMock()
        ds.status.desired_number_scheduled = 3
        ds.status.current_number_scheduled = 3
        ds.status.number_ready = 3
        ds.status.number_available = 3
        ds.status.number_unavailable = 0
        ds.status.updated_number_scheduled = 3
        ds.status.number_misscheduled = 0
        ds.status.observed_generation = 1
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds

        status = ds_manager.get_rollout_status("fluentd", "kube-system")
        assert status["fully_rolled_out"] is True

    def test_get_rollout_status_without_status(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds = MagicMock(status=None)
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds
        status = ds_manager.get_rollout_status("fluentd", "kube-system")
        assert status["fully_rolled_out"] is False

    def test_wait_for_rollout_returns_true(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds = MagicMock()
        ds.status.desired_number_scheduled = 1
        ds.status.number_ready = 1
        ds.status.updated_number_scheduled = 1
        mock_apps_v1.read_namespaced_daemon_set.return_value = ds
        assert (
            ds_manager.wait_for_rollout("fluentd", "kube-system", timeout_seconds=5)
            is True
        )

    def test_wait_for_rollout_ignores_not_found_and_times_out(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.read_namespaced_daemon_set.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.workloads.daemonset.time.sleep"):
            assert (
                ds_manager.wait_for_rollout(
                    "fluentd", "kube-system", timeout_seconds=0.05
                )
                is False
            )

    def test_restart(
        self, ds_manager: DaemonSetManager, mock_apps_v1: MagicMock
    ) -> None:
        ds_manager.restart("fluentd", "kube-system")
        call_kwargs = mock_apps_v1.patch_namespaced_daemon_set.call_args.kwargs
        annotations = call_kwargs["body"]["spec"]["template"]["metadata"]["annotations"]
        assert "kubectl.kubernetes.io/restartedAt" in annotations
