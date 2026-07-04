"""Unit tests for LimitRangeManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.cluster.limit_range import LimitRangeManager


@pytest.fixture
def lr_manager(mock_kube_client: MagicMock) -> LimitRangeManager:
    return LimitRangeManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestCreateLimitRange:
    def test_creates_with_given_limits(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        lr_manager.create_limit_range(
            "defaults", "default", limits=[{"type": "Container"}]
        )
        call_kwargs = mock_core_v1.create_namespaced_limit_range.call_args.kwargs
        assert call_kwargs["body"]["spec"]["limits"] == [{"type": "Container"}]


@pytest.mark.unit
class TestAddContainerLimits:
    def test_appends_full_container_limit_item(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        lr = MagicMock()
        lr.spec.limits = []
        mock_core_v1.read_namespaced_limit_range.return_value = lr

        lr_manager.add_container_limits(
            "defaults",
            "default",
            max_cpu="1",
            max_memory="1Gi",
            min_cpu="100m",
            min_memory="128Mi",
            default_cpu_limit="500m",
            default_memory_limit="512Mi",
            default_cpu_request="200m",
            default_memory_request="256Mi",
            max_limit_request_ratio_cpu="4",
        )

        call_kwargs = mock_core_v1.patch_namespaced_limit_range.call_args.kwargs
        item = call_kwargs["body"]["spec"]["limits"][0]
        assert item["type"] == "Container"
        assert item["max"] == {"cpu": "1", "memory": "1Gi"}
        assert item["min"] == {"cpu": "100m", "memory": "128Mi"}
        assert item["default"] == {"cpu": "500m", "memory": "512Mi"}
        assert item["defaultRequest"] == {"cpu": "200m", "memory": "256Mi"}
        assert item["maxLimitRequestRatio"] == {"cpu": "4"}

    def test_appends_minimal_container_limit_item(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        lr = MagicMock()
        lr.spec = None
        mock_core_v1.read_namespaced_limit_range.return_value = lr

        lr_manager.add_container_limits("defaults", "default")

        call_kwargs = mock_core_v1.patch_namespaced_limit_range.call_args.kwargs
        item = call_kwargs["body"]["spec"]["limits"][0]
        assert item == {"type": "Container"}


@pytest.mark.unit
class TestAddPodLimits:
    def test_appends_pod_limit_item(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        lr = MagicMock()
        lr.spec.limits = []
        mock_core_v1.read_namespaced_limit_range.return_value = lr

        lr_manager.add_pod_limits("defaults", "default", max_cpu="2", min_cpu="10m")

        call_kwargs = mock_core_v1.patch_namespaced_limit_range.call_args.kwargs
        item = call_kwargs["body"]["spec"]["limits"][0]
        assert item["type"] == "Pod"
        assert item["max"] == {"cpu": "2"}
        assert item["min"] == {"cpu": "10m"}


@pytest.mark.unit
class TestAddPvcLimits:
    def test_appends_pvc_limit_item(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        lr = MagicMock()
        lr.spec.limits = []
        mock_core_v1.read_namespaced_limit_range.return_value = lr

        lr_manager.add_pvc_limits(
            "defaults", "default", max_storage="100Gi", min_storage="1Gi"
        )

        call_kwargs = mock_core_v1.patch_namespaced_limit_range.call_args.kwargs
        item = call_kwargs["body"]["spec"]["limits"][0]
        assert item["type"] == "PersistentVolumeClaim"
        assert item["max"] == {"storage": "100Gi"}
        assert item["min"] == {"storage": "1Gi"}

    def test_appends_pvc_limit_item_without_values(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        lr = MagicMock()
        lr.spec.limits = []
        mock_core_v1.read_namespaced_limit_range.return_value = lr

        lr_manager.add_pvc_limits("defaults", "default")

        call_kwargs = mock_core_v1.patch_namespaced_limit_range.call_args.kwargs
        item = call_kwargs["body"]["spec"]["limits"][0]
        assert "max" not in item
        assert "min" not in item


@pytest.mark.unit
class TestGetListDelete:
    def test_get_limit_range(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_limit_range.return_value = "lr-obj"
        assert lr_manager.get_limit_range("defaults", "default") == "lr-obj"

    def test_list_limit_ranges(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_limit_range.return_value.items = ["a"]
        assert lr_manager.list_limit_ranges("default") == ["a"]

    def test_delete_limit_range(
        self, lr_manager: LimitRangeManager, mock_core_v1: MagicMock
    ) -> None:
        lr_manager.delete_limit_range("defaults", "default")
        mock_core_v1.delete_namespaced_limit_range.assert_called_once()


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, lr_manager: LimitRangeManager) -> None:
        assert lr_manager._kind() == "LimitRange"
        assert lr_manager._api_version() == "v1"
        assert lr_manager._resource_name() == "limit_range"
