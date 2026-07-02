"""Unit tests for PriorityClassManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError
from kube_orchestrator.resources.cluster.priority_class import PriorityClassManager


@pytest.fixture
def pc_manager(mock_kube_client: MagicMock) -> PriorityClassManager:
    return PriorityClassManager(kube_client=mock_kube_client)


@pytest.fixture
def scheduling_api(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.scheduling_v1


@pytest.mark.unit
class TestCreatePriorityClass:
    def test_creates_with_defaults(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        pc_manager.create_priority_class("high", 1000)
        call_kwargs = scheduling_api.create_priority_class.call_args.kwargs
        assert call_kwargs["body"]["value"] == 1000
        assert call_kwargs["body"]["globalDefault"] is False
        assert "description" not in call_kwargs["body"]

    def test_creates_with_description_and_global_default(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        pc_manager.create_priority_class(
            "high", 1000, global_default=True, description="critical workloads"
        )
        call_kwargs = scheduling_api.create_priority_class.call_args.kwargs
        assert call_kwargs["body"]["globalDefault"] is True
        assert call_kwargs["body"]["description"] == "critical workloads"

    def test_raises_parsed_exception(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        scheduling_api.create_priority_class.side_effect = ApiException(status=409)
        with pytest.raises(Exception):
            pc_manager.create_priority_class("high", 1000)


@pytest.mark.unit
class TestGetListDelete:
    def test_get_priority_class(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        scheduling_api.read_priority_class.return_value = "pc-obj"
        assert pc_manager.get_priority_class("high") == "pc-obj"

    def test_get_priority_class_raises_parsed_exception(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        scheduling_api.read_priority_class.side_effect = ApiException(status=404)
        with pytest.raises(Exception):
            pc_manager.get_priority_class("missing")

    def test_list_priority_classes(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        scheduling_api.list_priority_class.return_value.items = ["a"]
        assert pc_manager.list_priority_classes() == ["a"]

    def test_list_priority_classes_raises_parsed_exception(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        scheduling_api.list_priority_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            pc_manager.list_priority_classes()

    def test_delete_priority_class(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        pc_manager.delete_priority_class("high")
        scheduling_api.delete_priority_class.assert_called_once()

    def test_delete_priority_class_raises_parsed_exception(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        scheduling_api.delete_priority_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            pc_manager.delete_priority_class("high")


@pytest.mark.unit
class TestGlobalDefault:
    def test_set_global_default(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        pc_manager.set_global_default("high")
        call_kwargs = scheduling_api.patch_priority_class.call_args.kwargs
        assert call_kwargs["body"]["globalDefault"] is True

    def test_unset_global_default(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        pc_manager.unset_global_default("high")
        call_kwargs = scheduling_api.patch_priority_class.call_args.kwargs
        assert call_kwargs["body"]["globalDefault"] is False

    def test_set_global_default_raises_parsed_exception(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        scheduling_api.patch_priority_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            pc_manager.set_global_default("high")

    def test_unset_global_default_raises_parsed_exception(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        scheduling_api.patch_priority_class.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            pc_manager.unset_global_default("high")

    def test_get_global_default_found(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        default_pc = MagicMock(global_default=True)
        other_pc = MagicMock(global_default=False)
        scheduling_api.list_priority_class.return_value.items = [other_pc, default_pc]
        assert pc_manager.get_global_default() is default_pc

    def test_get_global_default_none(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        other_pc = MagicMock(global_default=False)
        scheduling_api.list_priority_class.return_value.items = [other_pc]
        assert pc_manager.get_global_default() is None


@pytest.mark.unit
class TestPodSpecAndWorkloads:
    def test_assign_to_pod_spec(self, pc_manager: PriorityClassManager) -> None:
        pod_spec = pc_manager.assign_to_pod_spec({}, "high")
        assert pod_spec["priorityClassName"] == "high"

    def test_get_workloads_using_matches_pods(
        self, pc_manager: PriorityClassManager, mock_kube_client: MagicMock
    ) -> None:
        matching_pod = MagicMock()
        matching_pod.spec.priority_class_name = "high"
        matching_pod.metadata.name = "web-1"
        matching_pod.metadata.namespace = "default"
        other_pod = MagicMock()
        other_pod.spec.priority_class_name = "low"
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [
            matching_pod,
            other_pod,
        ]

        result = pc_manager.get_workloads_using("high", "default")

        assert result == [{"kind": "Pod", "name": "web-1", "namespace": "default"}]

    def test_get_workloads_using_raises_parsed_exception(
        self, pc_manager: PriorityClassManager, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespaced_pod.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            pc_manager.get_workloads_using("high", "default")


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, pc_manager: PriorityClassManager) -> None:
        assert pc_manager._kind() == "PriorityClass"
        assert pc_manager._api_version() == "scheduling.k8s.io/v1"
        assert pc_manager._resource_name() == "priority_class"

    def test_get_api_returns_scheduling_v1(
        self, pc_manager: PriorityClassManager, scheduling_api: MagicMock
    ) -> None:
        assert pc_manager._get_api() is scheduling_api
