"""Unit tests for PodManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError, ResourceNotFoundError
from kube_orchestrator.resources.workloads.pod import PodManager


@pytest.fixture
def pod_manager(mock_kube_client: MagicMock) -> PodManager:
    return PodManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestPodManagerCreate:
    def test_create_pod_from_manifest(
        self,
        pod_manager: PodManager,
        mock_core_v1: MagicMock,
        sample_pod_manifest: dict,
    ) -> None:
        mock_core_v1.create_namespaced_pod.return_value = MagicMock(
            metadata=MagicMock(name="test-pod")
        )
        result = pod_manager.create_pod(
            manifest=sample_pod_manifest, namespace="default"
        )
        mock_core_v1.create_namespaced_pod.assert_called_once()
        assert result is not None

    def test_get_pod(self, pod_manager: PodManager, mock_core_v1: MagicMock) -> None:
        mock_pod = MagicMock()
        mock_core_v1.read_namespaced_pod.return_value = mock_pod
        result = pod_manager.get_pod("test-pod", "default")
        mock_core_v1.read_namespaced_pod.assert_called_once_with(
            name="test-pod", namespace="default"
        )
        assert result is mock_pod

    def test_list_pods(self, pod_manager: PodManager, mock_core_v1: MagicMock) -> None:
        mock_list = MagicMock()
        mock_list.items = [MagicMock(), MagicMock()]
        mock_core_v1.list_namespaced_pod.return_value = mock_list
        result = pod_manager.list_pods("default")
        assert len(result) == 2

    def test_delete_pod(self, pod_manager: PodManager, mock_core_v1: MagicMock) -> None:
        pod_manager.delete_pod("test-pod", "default")
        mock_core_v1.delete_namespaced_pod.assert_called_once()

    def test_get_phase(self, pod_manager: PodManager, mock_core_v1: MagicMock) -> None:
        mock_pod = MagicMock()
        mock_pod.status.phase = "Running"
        mock_core_v1.read_namespaced_pod.return_value = mock_pod
        phase = pod_manager.get_phase("test-pod", "default")
        assert phase == "Running"

    def test_is_ready_true(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_pod = MagicMock()
        condition = MagicMock()
        condition.type = "Ready"
        condition.status = "True"
        mock_pod.status.conditions = [condition]
        mock_core_v1.read_namespaced_pod.return_value = mock_pod
        assert pod_manager.is_ready("test-pod", "default") is True

    def test_is_ready_false_when_no_conditions(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_pod = MagicMock()
        mock_pod.status.conditions = []
        mock_core_v1.read_namespaced_pod.return_value = mock_pod
        assert pod_manager.is_ready("test-pod", "default") is False

    def test_create_pod_from_builder(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        from kube_orchestrator.resources.workloads._builders.pod_builder import (
            PodBuilder,
        )

        builder = PodBuilder("web").with_container("app", "nginx")
        mock_core_v1.create_namespaced_pod.return_value = MagicMock()
        pod_manager.create_pod(builder=builder, namespace="default")
        call_kwargs = mock_core_v1.create_namespaced_pod.call_args.kwargs
        assert call_kwargs["body"]["metadata"]["namespace"] == "default"

    def test_create_pod_without_builder_or_manifest_raises(
        self, pod_manager: PodManager
    ) -> None:
        with pytest.raises(ValueError, match="requires either a builder or a manifest"):
            pod_manager.create_pod()

    def test_list_pods_with_node_name_filter(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_pod.return_value.items = []
        pod_manager.list_pods("default", node_name="worker-1")
        kwargs = mock_core_v1.list_namespaced_pod.call_args.kwargs
        assert kwargs["field_selector"] == "spec.nodeName=worker-1"

    def test_list_pods_combines_field_selector_and_node_name(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_pod.return_value.items = []
        pod_manager.list_pods(
            "default", field_selector="status.phase=Running", node_name="worker-1"
        )
        kwargs = mock_core_v1.list_namespaced_pod.call_args.kwargs
        assert kwargs["field_selector"] == "status.phase=Running,spec.nodeName=worker-1"


@pytest.mark.unit
class TestPodManagerExecAndLogs:
    def test_exec_command(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        with patch("kube_orchestrator.resources.workloads.pod.stream") as fake_stream:
            fake_stream.return_value = "output"
            result = pod_manager.exec_command(
                "web", "default", container="app", command=["ls"]
            )
            assert result == "output"
            fake_stream.assert_called_once()

    def test_exec_command_raises_parsed_exception(
        self, pod_manager: PodManager
    ) -> None:
        with patch("kube_orchestrator.resources.workloads.pod.stream") as fake_stream:
            fake_stream.side_effect = ApiException(status=500)
            with pytest.raises(APIError):
                pod_manager.exec_command("web", "default", command=["ls"])

    def test_stream_logs_yields_decoded_lines(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_pod_log.return_value = [b"line1\n", b"line2\n"]
        lines = list(
            pod_manager.stream_logs(
                "web", "default", container="app", tail_lines=10, since_seconds=60
            )
        )
        assert lines == ["line1", "line2"]

    def test_stream_logs_raises_parsed_exception(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_pod_log.side_effect = ApiException(status=404)
        with pytest.raises(ResourceNotFoundError):
            list(pod_manager.stream_logs("web", "default"))


@pytest.mark.unit
class TestPodManagerContainerStatus:
    def test_get_container_status_by_name(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        cs = MagicMock(
            name="app", ready=True, restart_count=0, image="nginx", state="running"
        )
        cs.name = "app"
        pod = MagicMock()
        pod.status.container_statuses = [cs]
        mock_core_v1.read_namespaced_pod.return_value = pod

        result = pod_manager.get_container_status("web", "default", container="app")
        assert result["name"] == "app"

    def test_get_container_status_returns_first_without_filter(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        cs = MagicMock()
        cs.name = "app"
        pod = MagicMock()
        pod.status.container_statuses = [cs]
        mock_core_v1.read_namespaced_pod.return_value = pod

        result = pod_manager.get_container_status("web", "default")
        assert result["name"] == "app"

    def test_get_container_status_returns_empty_without_status(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock(status=None)
        mock_core_v1.read_namespaced_pod.return_value = pod
        assert pod_manager.get_container_status("web", "default") == {}

    def test_get_container_status_returns_empty_when_not_found(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        cs = MagicMock()
        cs.name = "other"
        pod = MagicMock()
        pod.status.container_statuses = [cs]
        mock_core_v1.read_namespaced_pod.return_value = pod
        assert pod_manager.get_container_status("web", "default", container="app") == {}


@pytest.mark.unit
class TestPodManagerWaiting:
    def test_wait_for_running_returns_true(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.status.phase = "Running"
        mock_core_v1.read_namespaced_pod.return_value = pod
        assert pod_manager.wait_for_running("web", "default", timeout_seconds=5) is True

    def test_wait_for_running_ignores_not_found_and_times_out(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_pod.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.workloads.pod.time.sleep"):
            assert (
                pod_manager.wait_for_running("web", "default", timeout_seconds=0.05)
                is False
            )

    def test_wait_for_completion_succeeded(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.status.phase = "Succeeded"
        mock_core_v1.read_namespaced_pod.return_value = pod
        assert (
            pod_manager.wait_for_completion("web", "default", timeout_seconds=5) is True
        )

    def test_wait_for_completion_failed(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.status.phase = "Failed"
        mock_core_v1.read_namespaced_pod.return_value = pod
        assert (
            pod_manager.wait_for_completion("web", "default", timeout_seconds=5)
            is False
        )

    def test_wait_for_completion_ignores_not_found_and_times_out(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_pod.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.workloads.pod.time.sleep"):
            assert (
                pod_manager.wait_for_completion("web", "default", timeout_seconds=0.05)
                is False
            )

    def test_wait_for_completion_times_out(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.status.phase = "Running"
        mock_core_v1.read_namespaced_pod.return_value = pod
        with patch("kube_orchestrator.resources.workloads.pod.time.sleep"):
            assert (
                pod_manager.wait_for_completion("web", "default", timeout_seconds=0.05)
                is False
            )


@pytest.mark.unit
class TestPodManagerWatchAndUsage:
    def test_watch_status_invokes_callback(self, pod_manager: PodManager) -> None:
        events = [{"type": "MODIFIED", "object": "pod-obj"}]
        received = []
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            pod_manager.watch_status(
                "web", "default", callback=lambda t, o: received.append((t, o))
            )
        assert received == [("MODIFIED", "pod-obj")]

    def test_get_resource_usage(
        self, pod_manager: PodManager, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.get_namespaced_custom_object.return_value = {
            "containers": []
        }
        result = pod_manager.get_resource_usage("web", "default")
        assert result == {"containers": []}

    def test_get_resource_usage_raises_parsed_exception(
        self, pod_manager: PodManager, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.get_namespaced_custom_object.side_effect = (
            ApiException(status=500)
        )
        with pytest.raises(APIError):
            pod_manager.get_resource_usage("web", "default")


@pytest.mark.unit
class TestPodManagerFilteredLists:
    def test_list_pods_by_phase(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_pod.return_value.items = ["pod-a"]
        result = pod_manager.list_pods_by_phase("Running", "default")
        assert result == ["pod-a"]
        kwargs = mock_core_v1.list_namespaced_pod.call_args.kwargs
        assert kwargs["field_selector"] == "status.phase=Running"

    def test_list_running_pods(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_pod.return_value.items = []
        pod_manager.list_running_pods("default")
        kwargs = mock_core_v1.list_namespaced_pod.call_args.kwargs
        assert kwargs["field_selector"] == "status.phase=Running"

    def test_list_failed_pods(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_pod.return_value.items = []
        pod_manager.list_failed_pods("default")
        kwargs = mock_core_v1.list_namespaced_pod.call_args.kwargs
        assert kwargs["field_selector"] == "status.phase=Failed"

    def test_list_pending_pods(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_pod.return_value.items = []
        pod_manager.list_pending_pods("default")
        kwargs = mock_core_v1.list_namespaced_pod.call_args.kwargs
        assert kwargs["field_selector"] == "status.phase=Pending"

    def test_list_pods_on_node(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_pod.return_value.items = []
        pod_manager.list_pods_on_node("worker-1", "default")
        kwargs = mock_core_v1.list_namespaced_pod.call_args.kwargs
        assert kwargs["field_selector"] == "spec.nodeName=worker-1"


@pytest.mark.unit
class TestAttachEphemeralContainer:
    def test_attaches_to_existing_pod(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.spec.ephemeral_containers = []
        pod.spec.containers = []
        mock_core_v1.read_namespaced_pod.return_value = pod
        mock_core_v1.patch_namespaced_pod_ephemeralcontainers.return_value = MagicMock()

        pod_manager.attach_ephemeral_container(
            "web", "default", container={"name": "debug", "image": "busybox"}
        )

        mock_core_v1.patch_namespaced_pod_ephemeralcontainers.assert_called_once()

    def test_raises_when_pod_spec_missing(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.spec = None
        mock_core_v1.read_namespaced_pod.return_value = pod
        with pytest.raises(ResourceNotFoundError):
            pod_manager.attach_ephemeral_container("web", "default")

    def test_raises_parsed_exception_on_patch_failure(
        self, pod_manager: PodManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.spec.ephemeral_containers = []
        pod.spec.containers = []
        mock_core_v1.read_namespaced_pod.return_value = pod
        mock_core_v1.patch_namespaced_pod_ephemeralcontainers.side_effect = (
            ApiException(status=500)
        )
        with pytest.raises(APIError):
            pod_manager.attach_ephemeral_container("web", "default")


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, pod_manager: PodManager) -> None:
        assert pod_manager._kind() == "Pod"
        assert pod_manager._api_version() == "v1"
