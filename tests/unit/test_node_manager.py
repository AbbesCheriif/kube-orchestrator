"""Unit tests for NodeManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.resources.cluster.node import (
    NodeManager,
    _parse_cpu,
    _parse_memory,
)


@pytest.fixture
def node_manager(mock_kube_client: MagicMock) -> NodeManager:
    return NodeManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestNodeManagerCordonUncordon:
    def test_cordon(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_node = MagicMock()
        mock_node.spec.unschedulable = False
        mock_core_v1.read_namespaced_node.return_value = mock_node
        mock_core_v1.patch_namespaced_node.return_value = mock_node
        node_manager.cordon("worker-1")
        mock_core_v1.patch_namespaced_node.assert_called_once()
        call_body = mock_core_v1.patch_namespaced_node.call_args.kwargs["body"]
        assert call_body["spec"]["unschedulable"] is True

    def test_uncordon(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_node = MagicMock()
        mock_node.spec.unschedulable = True
        mock_core_v1.read_namespaced_node.return_value = mock_node
        mock_core_v1.patch_namespaced_node.return_value = mock_node
        node_manager.uncordon("worker-1")
        call_body = mock_core_v1.patch_namespaced_node.call_args.kwargs["body"]
        assert call_body["spec"]["unschedulable"] is False

    def test_is_schedulable_true(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_node = MagicMock()
        mock_node.spec.unschedulable = None
        mock_core_v1.read_namespaced_node.return_value = mock_node
        assert node_manager.is_schedulable("worker-1") is True

    def test_is_schedulable_false(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_node = MagicMock()
        mock_node.spec.unschedulable = True
        mock_core_v1.read_namespaced_node.return_value = mock_node
        assert node_manager.is_schedulable("worker-1") is False


@pytest.mark.unit
class TestNodeManagerTaints:
    def test_add_taint(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_node = MagicMock()
        mock_node.spec.taints = []
        mock_core_v1.read_namespaced_node.return_value = mock_node
        mock_core_v1.patch_namespaced_node.return_value = mock_node
        node_manager.add_taint("worker-1", "dedicated", "gpu", "NoSchedule")
        mock_core_v1.patch_namespaced_node.assert_called_once()

    def test_remove_taint(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        existing_taint = MagicMock()
        existing_taint.key = "dedicated"
        existing_taint.effect = "NoSchedule"
        mock_node = MagicMock()
        mock_node.spec.taints = [existing_taint]
        mock_core_v1.read_namespaced_node.return_value = mock_node
        mock_core_v1.patch_namespaced_node.return_value = mock_node
        node_manager.remove_taint("worker-1", "dedicated")
        call_body = mock_core_v1.patch_namespaced_node.call_args.kwargs["body"]
        assert call_body["spec"]["taints"] == []

    def test_has_taint_true(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        taint = MagicMock()
        taint.key = "dedicated"
        taint.effect = "NoSchedule"
        mock_node = MagicMock()
        mock_node.spec.taints = [taint]
        mock_core_v1.read_namespaced_node.return_value = mock_node
        assert node_manager.has_taint("worker-1", "dedicated") is True

    def test_has_taint_false(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_node = MagicMock()
        mock_node.spec.taints = []
        mock_core_v1.read_namespaced_node.return_value = mock_node
        assert node_manager.has_taint("worker-1", "missing-key") is False

    def test_remove_taint_by_effect(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        t1 = MagicMock(key="dedicated", effect="NoSchedule")
        t2 = MagicMock(key="dedicated", effect="NoExecute")
        mock_node = MagicMock()
        mock_node.spec.taints = [t1, t2]
        mock_core_v1.read_namespaced_node.return_value = mock_node
        mock_core_v1.patch_namespaced_node.return_value = mock_node
        node_manager.remove_taint("worker-1", "dedicated", effect="NoSchedule")
        call_body = mock_core_v1.patch_namespaced_node.call_args.kwargs["body"]
        assert len(call_body["spec"]["taints"]) == 1
        assert call_body["spec"]["taints"][0]["effect"] == "NoExecute"

    def test_get_taints(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        taint = MagicMock(key="k", value="v", effect="NoSchedule")
        mock_node = MagicMock()
        mock_node.spec.taints = [taint]
        mock_core_v1.read_namespaced_node.return_value = mock_node
        result = node_manager.get_taints("worker-1")
        assert result == [{"key": "k", "value": "v", "effect": "NoSchedule"}]

    def test_remove_all_taints(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.patch_namespaced_node.return_value = MagicMock()
        node_manager.remove_all_taints("worker-1")
        call_body = mock_core_v1.patch_namespaced_node.call_args.kwargs["body"]
        assert call_body["spec"]["taints"] == []

    def test_list_nodes_with_taint(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        taint = MagicMock(key="dedicated", value="gpu", effect="NoSchedule")
        tainted_node = MagicMock()
        tainted_node.metadata.name = "worker-1"
        tainted_node.spec.taints = [taint]
        clean_node = MagicMock()
        clean_node.metadata.name = "worker-2"
        clean_node.spec.taints = []
        mock_core_v1.list_namespaced_node.return_value.items = [
            tainted_node,
            clean_node,
        ]
        mock_core_v1.read_namespaced_node.side_effect = [tainted_node, clean_node]

        result = node_manager.list_nodes_with_taint("dedicated")

        assert [n.metadata.name for n in result] == ["worker-1"]


@pytest.mark.unit
class TestNodeManagerListAndGet:
    def test_list_nodes(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_node.return_value.items = ["a", "b"]
        assert node_manager.list_nodes() == ["a", "b"]

    def test_get_node(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_core_v1.read_namespaced_node.return_value = "node-obj"
        assert node_manager.get_node("worker-1") == "node-obj"

    def test_get_cordoned_nodes(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        cordoned = MagicMock()
        cordoned.spec.unschedulable = True
        active = MagicMock()
        active.spec.unschedulable = False
        mock_core_v1.list_namespaced_node.return_value.items = [cordoned, active]
        assert node_manager.get_cordoned_nodes() == [cordoned]


@pytest.mark.unit
class TestNodeManagerInfo:
    def test_get_node_info(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        info = node.status.node_info
        info.architecture = "amd64"
        info.os_image = "Ubuntu 22.04"
        info.kernel_version = "5.15.0"
        info.kubelet_version = "v1.28.0"
        info.container_runtime_version = "containerd://1.6.0"
        info.machine_id = "abc"
        info.system_uuid = "def"
        info.boot_id = "ghi"
        info.operating_system = "linux"
        mock_core_v1.read_namespaced_node.return_value = node

        result = node_manager.get_node_info("worker-1")
        assert result["architecture"] == "amd64"
        assert result["operating_system"] == "linux"

    def test_get_node_info_returns_empty_without_status(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.status = None
        mock_core_v1.read_namespaced_node.return_value = node
        assert node_manager.get_node_info("worker-1") == {}

    def test_get_conditions(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        cond = MagicMock(
            type="Ready", status="True", reason="KubeletReady", message="ok"
        )
        cond.last_transition_time = "2026-01-01"
        node = MagicMock()
        node.status.conditions = [cond]
        mock_core_v1.read_namespaced_node.return_value = node
        result = node_manager.get_conditions("worker-1")
        assert result[0]["type"] == "Ready"

    def test_is_ready_true(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        cond = MagicMock(type="Ready", status="True")
        node = MagicMock()
        node.status.conditions = [cond]
        mock_core_v1.read_namespaced_node.return_value = node
        assert node_manager.is_ready("worker-1") is True

    def test_is_ready_false_without_ready_condition(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.status.conditions = []
        mock_core_v1.read_namespaced_node.return_value = node
        assert node_manager.is_ready("worker-1") is False

    def test_get_allocatable(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.status.allocatable = {"cpu": "4", "memory": "16Gi"}
        mock_core_v1.read_namespaced_node.return_value = node
        assert node_manager.get_allocatable("worker-1") == {
            "cpu": "4",
            "memory": "16Gi",
        }

    def test_get_capacity(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.status.capacity = {"cpu": "4"}
        mock_core_v1.read_namespaced_node.return_value = node
        assert node_manager.get_capacity("worker-1") == {"cpu": "4"}

    def test_get_addresses(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        internal = MagicMock(type="InternalIP", address="10.0.0.1")
        external = MagicMock(type="ExternalIP", address="1.2.3.4")
        hostname = MagicMock(type="Hostname", address="worker-1")
        node = MagicMock()
        node.status.addresses = [internal, external, hostname]
        mock_core_v1.read_namespaced_node.return_value = node
        result = node_manager.get_addresses("worker-1")
        assert result == {
            "internal_ip": "10.0.0.1",
            "external_ip": "1.2.3.4",
            "hostname": "worker-1",
        }

    def test_get_images(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        img = MagicMock(names=["nginx:latest"], size_bytes=1234)
        node = MagicMock()
        node.status.images = [img]
        mock_core_v1.read_namespaced_node.return_value = node
        result = node_manager.get_images("worker-1")
        assert result == [{"names": ["nginx:latest"], "size_bytes": 1234}]

    def test_get_labels(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.metadata.labels = {"disktype": "ssd"}
        mock_core_v1.read_namespaced_node.return_value = node
        assert node_manager.get_labels("worker-1") == {"disktype": "ssd"}

    def test_set_label(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.patch_namespaced_node.return_value = MagicMock()
        node_manager.set_label("worker-1", "disktype", "ssd")
        call_body = mock_core_v1.patch_namespaced_node.call_args.kwargs["body"]
        assert call_body["metadata"]["labels"] == {"disktype": "ssd"}

    def test_remove_label(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.patch_namespaced_node.return_value = MagicMock()
        node_manager.remove_label("worker-1", "disktype")
        call_body = mock_core_v1.patch_namespaced_node.call_args.kwargs["body"]
        assert call_body["metadata"]["labels"] == {"disktype": None}

    def test_set_annotation(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.patch_namespaced_node.return_value = MagicMock()
        node_manager.set_annotation("worker-1", "owner", "team-a")
        call_body = mock_core_v1.patch_namespaced_node.call_args.kwargs["body"]
        assert call_body["metadata"]["annotations"] == {"owner": "team-a"}


@pytest.mark.unit
class TestNodeManagerPodsAndUsage:
    def test_get_pods(self, node_manager: NodeManager, mock_core_v1: MagicMock) -> None:
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = ["pod-a"]
        assert node_manager.get_pods("worker-1") == ["pod-a"]

    def test_get_resource_usage(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        container = MagicMock()
        container.resources.requests = {"cpu": "500m", "memory": "256Mi"}
        pod = MagicMock()
        pod.spec.containers = [container]
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        result = node_manager.get_resource_usage("worker-1")
        assert result["pod_count"] == 1
        assert result["cpu_requested_millicores"] == 500
        assert result["memory_requested_bytes"] == 256 * 1024**2

    def test_get_resource_usage_ignores_containers_without_requests(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        container = MagicMock()
        container.resources = None
        pod = MagicMock()
        pod.spec.containers = [container]
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        result = node_manager.get_resource_usage("worker-1")
        assert result["cpu_requested_millicores"] == 0


@pytest.mark.unit
class TestNodeManagerDrain:
    def test_evict_pod(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node_manager.evict_pod("web-1", "default", grace_period_seconds=30)
        mock_core_v1.create_namespaced_pod_eviction.assert_called_once()
        body = mock_core_v1.create_namespaced_pod_eviction.call_args.args[2]
        assert body["deleteOptions"]["gracePeriodSeconds"] == 30

    def test_drain_evicts_non_daemonset_pods(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.spec.unschedulable = False
        mock_core_v1.read_namespaced_node.return_value = node
        mock_core_v1.patch_namespaced_node.return_value = node

        owner = MagicMock(kind="ReplicaSet")
        pod = MagicMock()
        pod.metadata.name = "web-1"
        pod.metadata.namespace = "default"
        pod.metadata.owner_references = [owner]
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        result = node_manager.drain("worker-1")

        assert result == ["default/web-1"]
        mock_core_v1.create_namespaced_pod_eviction.assert_called_once()

    def test_drain_skips_daemonset_pods_by_default(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.spec.unschedulable = False
        mock_core_v1.read_namespaced_node.return_value = node
        mock_core_v1.patch_namespaced_node.return_value = node

        owner = MagicMock(kind="DaemonSet")
        pod = MagicMock()
        pod.metadata.name = "ds-1"
        pod.metadata.namespace = "kube-system"
        pod.metadata.owner_references = [owner]
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        result = node_manager.drain("worker-1")

        assert result == []
        mock_core_v1.create_namespaced_pod_eviction.assert_not_called()

    def test_drain_skips_unowned_pods_unless_forced(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.spec.unschedulable = False
        mock_core_v1.read_namespaced_node.return_value = node
        mock_core_v1.patch_namespaced_node.return_value = node

        pod = MagicMock()
        pod.metadata.name = "standalone"
        pod.metadata.namespace = "default"
        pod.metadata.owner_references = []
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        assert node_manager.drain("worker-1") == []
        assert node_manager.drain("worker-1", force=True) == ["default/standalone"]

    def test_drain_dry_run_does_not_evict(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.spec.unschedulable = False
        mock_core_v1.read_namespaced_node.return_value = node
        mock_core_v1.patch_namespaced_node.return_value = node

        owner = MagicMock(kind="ReplicaSet")
        pod = MagicMock()
        pod.metadata.name = "web-1"
        pod.metadata.namespace = "default"
        pod.metadata.owner_references = [owner]
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        result = node_manager.drain("worker-1", dry_run=True)

        assert result == ["default/web-1"]
        mock_core_v1.create_namespaced_pod_eviction.assert_not_called()

    def test_drain_skips_pods_without_name_or_namespace(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        node = MagicMock()
        node.spec.unschedulable = False
        mock_core_v1.read_namespaced_node.return_value = node
        mock_core_v1.patch_namespaced_node.return_value = node

        pod = MagicMock()
        pod.metadata = None
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        assert node_manager.drain("worker-1") == []

    def test_wait_for_drain_returns_true_when_only_daemonsets_remain(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        owner = MagicMock(kind="DaemonSet")
        pod = MagicMock()
        pod.metadata.owner_references = [owner]
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        assert node_manager.wait_for_drain("worker-1", timeout_seconds=5) is True

    def test_wait_for_drain_times_out(
        self, node_manager: NodeManager, mock_core_v1: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.metadata.owner_references = []
        mock_core_v1.list_pod_for_all_namespaces.return_value.items = [pod]

        with patch("time.sleep"):
            assert (
                node_manager.wait_for_drain("worker-1", timeout_seconds=0.05) is False
            )


@pytest.mark.unit
class TestParseHelpers:
    def test_parse_cpu_millicores(self) -> None:
        assert _parse_cpu("500m") == 500

    def test_parse_cpu_cores(self) -> None:
        assert _parse_cpu("2") == 2000

    def test_parse_cpu_invalid_returns_zero(self) -> None:
        assert _parse_cpu("garbage") == 0

    def test_parse_memory_suffixes(self) -> None:
        assert _parse_memory("1Ki") == 1024
        assert _parse_memory("1Mi") == 1024**2
        assert _parse_memory("1Gi") == 1024**3
        assert _parse_memory("1Ti") == 1024**4

    def test_parse_memory_plain_number(self) -> None:
        assert _parse_memory("1024") == 1024

    def test_parse_memory_invalid_returns_zero(self) -> None:
        assert _parse_memory("garbage") == 0


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, node_manager: NodeManager) -> None:
        assert node_manager._kind() == "Node"
        assert node_manager._api_version() == "v1"
