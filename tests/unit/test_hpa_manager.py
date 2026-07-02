"""Unit tests for HPAManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.cluster.hpa import HPAManager


@pytest.fixture
def hpa_manager(mock_kube_client: MagicMock) -> HPAManager:
    return HPAManager(kube_client=mock_kube_client)


@pytest.fixture
def autoscaling_api(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.autoscaling_v2


@pytest.mark.unit
class TestCreateHpa:
    def test_creates_with_minimal_fields(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa_manager.create_hpa(
            "web-hpa",
            "default",
            scale_target_ref={"kind": "Deployment", "name": "web"},
            max_replicas=5,
        )
        call_kwargs = (
            autoscaling_api.create_namespaced_horizontal_pod_autoscaler.call_args.kwargs
        )
        assert call_kwargs["body"]["spec"]["maxReplicas"] == 5

    def test_creates_with_min_replicas_metrics_and_behavior(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa_manager.create_hpa(
            "web-hpa",
            "default",
            min_replicas=2,
            max_replicas=10,
            metrics=[{"type": "Resource"}],
            behavior={"scaleDown": {}},
        )
        call_kwargs = (
            autoscaling_api.create_namespaced_horizontal_pod_autoscaler.call_args.kwargs
        )
        spec = call_kwargs["body"]["spec"]
        assert spec["minReplicas"] == 2
        assert spec["metrics"] == [{"type": "Resource"}]
        assert spec["behavior"] == {"scaleDown": {}}

    def test_create_cpu_hpa(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa_manager.create_cpu_hpa("web-hpa", "default", target_name="web")
        call_kwargs = (
            autoscaling_api.create_namespaced_horizontal_pod_autoscaler.call_args.kwargs
        )
        metric = call_kwargs["body"]["spec"]["metrics"][0]
        assert metric["resource"]["name"] == "cpu"

    def test_create_memory_hpa(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa_manager.create_memory_hpa("web-hpa", "default", target_name="web")
        call_kwargs = (
            autoscaling_api.create_namespaced_horizontal_pod_autoscaler.call_args.kwargs
        )
        metric = call_kwargs["body"]["spec"]["metrics"][0]
        assert metric["resource"]["name"] == "memory"


@pytest.mark.unit
class TestGetListUpdateDelete:
    def test_get_hpa(self, hpa_manager: HPAManager, autoscaling_api: MagicMock) -> None:
        autoscaling_api.read_namespaced_horizontal_pod_autoscaler.return_value = (
            "hpa-obj"
        )
        assert hpa_manager.get_hpa("web-hpa", "default") == "hpa-obj"

    def test_list_hpas(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        autoscaling_api.list_namespaced_horizontal_pod_autoscaler.return_value.items = [
            "a"
        ]
        assert hpa_manager.list_hpas("default") == ["a"]

    def test_update_hpa(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa_manager.update_hpa("web-hpa", "default", {"spec": {"maxReplicas": 8}})
        autoscaling_api.replace_namespaced_horizontal_pod_autoscaler.assert_called_once()

    def test_delete_hpa(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa_manager.delete_hpa("web-hpa", "default")
        autoscaling_api.delete_namespaced_horizontal_pod_autoscaler.assert_called_once()


@pytest.mark.unit
class TestStatusHelpers:
    def test_get_current_replicas(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa = MagicMock()
        hpa.status.current_replicas = 4
        autoscaling_api.read_namespaced_horizontal_pod_autoscaler.return_value = hpa
        assert hpa_manager.get_current_replicas("web-hpa", "default") == 4

    def test_get_current_replicas_none_without_status(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa = MagicMock(status=None)
        autoscaling_api.read_namespaced_horizontal_pod_autoscaler.return_value = hpa
        assert hpa_manager.get_current_replicas("web-hpa", "default") is None

    def test_get_conditions(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        cond = MagicMock(type="AbleToScale", status="True", reason="", message="")
        hpa = MagicMock()
        hpa.status.conditions = [cond]
        autoscaling_api.read_namespaced_horizontal_pod_autoscaler.return_value = hpa
        result = hpa_manager.get_conditions("web-hpa", "default")
        assert result[0]["type"] == "AbleToScale"

    def test_get_conditions_empty_without_status(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa = MagicMock(status=None)
        autoscaling_api.read_namespaced_horizontal_pod_autoscaler.return_value = hpa
        assert hpa_manager.get_conditions("web-hpa", "default") == []


@pytest.mark.unit
class TestPatchHelpers:
    def test_add_metric(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa = MagicMock()
        hpa.spec.metrics = []
        autoscaling_api.read_namespaced_horizontal_pod_autoscaler.return_value = hpa

        hpa_manager.add_metric("web-hpa", "default", {"type": "Pods"})

        call_kwargs = (
            autoscaling_api.patch_namespaced_horizontal_pod_autoscaler.call_args.kwargs
        )
        assert call_kwargs["body"]["spec"]["metrics"] == [{"type": "Pods"}]

    def test_set_behavior(
        self, hpa_manager: HPAManager, autoscaling_api: MagicMock
    ) -> None:
        hpa_manager.set_behavior("web-hpa", "default", {"scaleUp": {}})
        call_kwargs = (
            autoscaling_api.patch_namespaced_horizontal_pod_autoscaler.call_args.kwargs
        )
        assert call_kwargs["body"]["spec"]["behavior"] == {"scaleUp": {}}


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, hpa_manager: HPAManager) -> None:
        assert hpa_manager._kind() == "HorizontalPodAutoscaler"
        assert hpa_manager._api_version() == "autoscaling/v2"
        assert hpa_manager._resource_name() == "horizontal_pod_autoscaler"
