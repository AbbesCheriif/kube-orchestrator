"""Unit tests for kube_orchestrator.scaling.engine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.scaling.engine import (
    CPUScalingStrategy,
    CustomMetricStrategy,
    MemoryScalingStrategy,
    ScalingEngine,
)


@pytest.mark.unit
class TestCPUScalingStrategy:
    def test_should_scale_up(self) -> None:
        strategy = CPUScalingStrategy(target_cpu_utilization=70)
        assert strategy.should_scale_up({"cpu_utilization": 90}) is True
        assert strategy.should_scale_up({"cpu_utilization": 50}) is False

    def test_should_scale_down(self) -> None:
        strategy = CPUScalingStrategy(target_cpu_utilization=70)
        assert strategy.should_scale_down({"cpu_utilization": 10}) is True
        assert strategy.should_scale_down({"cpu_utilization": 50}) is False

    def test_get_desired_replicas_scales_with_ratio(self) -> None:
        strategy = CPUScalingStrategy(target_cpu_utilization=50)
        assert strategy.get_desired_replicas(2, {"cpu_utilization": 100}) == 4

    def test_get_desired_replicas_zero_utilization_scales_down(self) -> None:
        strategy = CPUScalingStrategy(target_cpu_utilization=50)
        assert strategy.get_desired_replicas(3, {"cpu_utilization": 0}) == 2

    def test_get_desired_replicas_never_below_one(self) -> None:
        strategy = CPUScalingStrategy(target_cpu_utilization=50)
        assert strategy.get_desired_replicas(1, {"cpu_utilization": 0}) == 1


@pytest.mark.unit
class TestMemoryScalingStrategy:
    def test_parses_memory_suffixes(self) -> None:
        strategy = MemoryScalingStrategy(target_memory_average="1Gi")
        assert strategy._target_bytes == 1024**3

    def test_parses_plain_number(self) -> None:
        strategy = MemoryScalingStrategy(target_memory_average="1024")
        assert strategy._target_bytes == 1024

    def test_should_scale_up(self) -> None:
        strategy = MemoryScalingStrategy(target_memory_average="1000")
        assert strategy.should_scale_up({"memory_bytes": 950}) is True
        assert strategy.should_scale_up({"memory_bytes": 100}) is False

    def test_should_scale_down(self) -> None:
        strategy = MemoryScalingStrategy(target_memory_average="1000")
        assert strategy.should_scale_down({"memory_bytes": 100}) is True
        assert strategy.should_scale_down({"memory_bytes": 900}) is False

    def test_get_desired_replicas_zero_bytes_scales_down(self) -> None:
        strategy = MemoryScalingStrategy(target_memory_average="1000")
        assert strategy.get_desired_replicas(3, {"memory_bytes": 0}) == 2

    def test_get_desired_replicas_scales_with_ratio(self) -> None:
        strategy = MemoryScalingStrategy(target_memory_average="1000")
        assert strategy.get_desired_replicas(2, {"memory_bytes": 2000}) == 4


@pytest.mark.unit
class TestCustomMetricStrategy:
    def test_should_scale_up(self) -> None:
        strategy = CustomMetricStrategy("queue_depth", 100)
        assert strategy.should_scale_up({"queue_depth": 150}) is True
        assert strategy.should_scale_up({"queue_depth": 10}) is False

    def test_should_scale_down(self) -> None:
        strategy = CustomMetricStrategy("queue_depth", 100)
        assert strategy.should_scale_down({"queue_depth": 10}) is True

    def test_get_desired_replicas_zero_value_scales_down(self) -> None:
        strategy = CustomMetricStrategy("queue_depth", 100)
        assert strategy.get_desired_replicas(3, {"queue_depth": 0}) == 2

    def test_get_desired_replicas_scales_with_ratio(self) -> None:
        strategy = CustomMetricStrategy("queue_depth", 100)
        assert strategy.get_desired_replicas(2, {"queue_depth": 200}) == 4


@pytest.fixture
def engine(mock_kube_client: MagicMock) -> ScalingEngine:
    return ScalingEngine(client=mock_kube_client)


@pytest.mark.unit
class TestScalingEngineGetSetReplicas:
    def test_get_replicas_deployment(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value.spec.replicas = (
            3
        )
        assert engine._get_replicas("web", "default", "Deployment") == 3

    def test_get_replicas_statefulset(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        obj = mock_kube_client.apps_v1.read_namespaced_stateful_set.return_value
        obj.spec.replicas = 5
        assert engine._get_replicas("db", "default", "StatefulSet") == 5

    def test_get_replicas_replicaset(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        obj = mock_kube_client.apps_v1.read_namespaced_replica_set.return_value
        obj.spec.replicas = 2
        assert engine._get_replicas("rs", "default", "ReplicaSet") == 2

    def test_get_replicas_defaults_to_one_when_none(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value.spec.replicas = (
            None
        )
        assert engine._get_replicas("web", "default", "Deployment") == 1

    def test_get_replicas_unsupported_kind_raises(self, engine: ScalingEngine) -> None:
        with pytest.raises(ValueError, match="Unsupported kind"):
            engine._get_replicas("x", "default", "Bogus")

    def test_set_replicas_deployment(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        engine.set_replicas("web", "default", "Deployment", 4)
        mock_kube_client.apps_v1.patch_namespaced_deployment.assert_called_once_with(
            "web", "default", {"spec": {"replicas": 4}}
        )

    def test_set_replicas_statefulset(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        engine.set_replicas("db", "default", "StatefulSet", 4)
        mock_kube_client.apps_v1.patch_namespaced_stateful_set.assert_called_once()

    def test_set_replicas_replicaset(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        engine.set_replicas("rs", "default", "ReplicaSet", 4)
        mock_kube_client.apps_v1.patch_namespaced_replica_set.assert_called_once()

    def test_set_replicas_unsupported_kind_raises(self, engine: ScalingEngine) -> None:
        with pytest.raises(ValueError, match="Unsupported kind for scaling"):
            engine.set_replicas("x", "default", "Bogus", 2)


@pytest.mark.unit
class TestScalingEngineScaleWithStrategy:
    def test_scales_when_desired_differs_from_current(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value.spec.replicas = (
            2
        )
        strategy = CPUScalingStrategy(target_cpu_utilization=50)
        engine.scale_with_strategy(
            "web", "default", "Deployment", strategy, {"cpu_utilization": 100}
        )
        mock_kube_client.apps_v1.patch_namespaced_deployment.assert_called_once_with(
            "web", "default", {"spec": {"replicas": 4}}
        )

    def test_does_not_scale_when_desired_equals_current(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value.spec.replicas = (
            2
        )
        strategy = CPUScalingStrategy(target_cpu_utilization=50)
        engine.scale_with_strategy(
            "web", "default", "Deployment", strategy, {"cpu_utilization": 50}
        )
        mock_kube_client.apps_v1.patch_namespaced_deployment.assert_not_called()

    def test_defaults_metrics_to_empty_dict_without_crashing(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value.spec.replicas = (
            4
        )
        strategy = CPUScalingStrategy(target_cpu_utilization=70)
        engine.scale_with_strategy("web", "default", "Deployment", strategy)
        mock_kube_client.apps_v1.read_namespaced_deployment.assert_called_once()
        mock_kube_client.apps_v1.patch_namespaced_deployment.assert_not_called()

    def test_reraises_and_logs_on_failure(
        self, engine: ScalingEngine, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.side_effect = RuntimeError(
            "boom"
        )
        strategy = CPUScalingStrategy(target_cpu_utilization=70)
        with pytest.raises(RuntimeError, match="boom"):
            engine.scale_with_strategy("web", "default", "Deployment", strategy)
