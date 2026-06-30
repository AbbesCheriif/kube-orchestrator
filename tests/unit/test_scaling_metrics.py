"""Unit tests for kube_orchestrator.scaling.metrics."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.scaling.metrics import MetricsClient


@pytest.fixture
def metrics_client(mock_kube_client: MagicMock) -> MetricsClient:
    return MetricsClient(client=mock_kube_client)


def _raw_pod_metric(name: str = "web-1", namespace: str = "default") -> dict:
    return {
        "metadata": {"name": name, "namespace": namespace},
        "containers": [
            {"usage": {"cpu": "250m", "memory": "128Mi"}},
            {"usage": {"cpu": "100m", "memory": "64Mi"}},
        ],
    }


def _raw_node_metric(name: str = "worker-1") -> dict:
    return {"metadata": {"name": name}, "usage": {"cpu": "500m", "memory": "1Gi"}}


@pytest.mark.unit
class TestGetMetrics:
    def test_get_pod_metrics_parses_result(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.get_namespaced_custom_object.return_value = (
            _raw_pod_metric()
        )
        result = metrics_client.get_pod_metrics("web-1", "default")
        assert result["name"] == "web-1"
        assert result["namespace"] == "default"
        assert result["containers"] == 2
        assert result["cpu_cores"] == pytest.approx(0.35)
        assert result["memory_bytes"] == 128 * 1024**2 + 64 * 1024**2

    def test_get_pod_metrics_returns_empty_on_error(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.get_namespaced_custom_object.side_effect = (
            RuntimeError("not found")
        )
        assert metrics_client.get_pod_metrics("missing", "default") == {}

    def test_get_node_metrics_parses_result(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.get_cluster_custom_object.return_value = (
            _raw_node_metric()
        )
        result = metrics_client.get_node_metrics("worker-1")
        assert result["name"] == "worker-1"
        assert result["cpu_cores"] == 0.5
        assert result["memory_bytes"] == 1024**3

    def test_get_node_metrics_returns_empty_on_error(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.get_cluster_custom_object.side_effect = (
            RuntimeError("boom")
        )
        assert metrics_client.get_node_metrics("worker-1") == {}


@pytest.mark.unit
class TestListMetrics:
    def test_list_pod_metrics_without_selector(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.list_namespaced_custom_object.return_value = {
            "items": [_raw_pod_metric("a"), _raw_pod_metric("b")]
        }
        result = metrics_client.list_pod_metrics("default")
        assert [m["name"] for m in result] == ["a", "b"]
        kwargs = mock_kube_client.custom_objects.list_namespaced_custom_object.call_args.kwargs
        assert "label_selector" not in kwargs

    def test_list_pod_metrics_with_selector(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.list_namespaced_custom_object.return_value = {
            "items": []
        }
        metrics_client.list_pod_metrics("default", label_selector="app=web")
        kwargs = mock_kube_client.custom_objects.list_namespaced_custom_object.call_args.kwargs
        assert kwargs["label_selector"] == "app=web"

    def test_list_pod_metrics_returns_empty_on_error(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.list_namespaced_custom_object.side_effect = (
            RuntimeError("boom")
        )
        assert metrics_client.list_pod_metrics("default") == []

    def test_list_node_metrics(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.list_cluster_custom_object.return_value = {
            "items": [_raw_node_metric("worker-1")]
        }
        result = metrics_client.list_node_metrics()
        assert result[0]["name"] == "worker-1"

    def test_list_node_metrics_returns_empty_on_error(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.list_cluster_custom_object.side_effect = (
            RuntimeError("boom")
        )
        assert metrics_client.list_node_metrics() == []


@pytest.mark.unit
class TestTopMetrics:
    def test_get_top_pods_sorts_by_cpu_descending(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {"name": "low"},
                    "containers": [{"usage": {"cpu": "10m", "memory": "1Mi"}}],
                },
                {
                    "metadata": {"name": "high"},
                    "containers": [{"usage": {"cpu": "900m", "memory": "1Mi"}}],
                },
            ]
        }
        top = metrics_client.get_top_pods("default", top=1)
        assert len(top) == 1
        assert top[0]["name"] == "high"

    def test_get_top_nodes_sorts_by_cpu_descending(
        self, metrics_client: MetricsClient, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.custom_objects.list_cluster_custom_object.return_value = {
            "items": [
                {"metadata": {"name": "low"}, "usage": {"cpu": "10m", "memory": "1Mi"}},
                {
                    "metadata": {"name": "high"},
                    "usage": {"cpu": "900m", "memory": "1Mi"},
                },
            ]
        }
        top = metrics_client.get_top_nodes(top=1)
        assert top[0]["name"] == "high"


@pytest.mark.unit
class TestParseHelpers:
    def test_parse_cpu_nanocores(self, metrics_client: MetricsClient) -> None:
        assert metrics_client._parse_cpu("500000000n") == pytest.approx(0.5)

    def test_parse_cpu_millicores(self, metrics_client: MetricsClient) -> None:
        assert metrics_client._parse_cpu("250m") == 0.25

    def test_parse_cpu_plain_cores(self, metrics_client: MetricsClient) -> None:
        assert metrics_client._parse_cpu("2") == 2.0

    def test_parse_cpu_invalid_returns_zero(self, metrics_client: MetricsClient) -> None:
        assert metrics_client._parse_cpu("garbage") == 0.0

    def test_parse_memory_suffixes(self, metrics_client: MetricsClient) -> None:
        assert metrics_client._parse_memory("1Ki") == 1024
        assert metrics_client._parse_memory("1Mi") == 1024**2
        assert metrics_client._parse_memory("1Gi") == 1024**3
        assert metrics_client._parse_memory("1Ti") == 1024**4
        assert metrics_client._parse_memory("1k") == 1000
        assert metrics_client._parse_memory("1M") == 1000**2
        assert metrics_client._parse_memory("1G") == 1000**3

    def test_parse_memory_plain_number(self, metrics_client: MetricsClient) -> None:
        assert metrics_client._parse_memory("1024") == 1024

    def test_parse_memory_invalid_returns_zero(
        self, metrics_client: MetricsClient
    ) -> None:
        assert metrics_client._parse_memory("garbage") == 0
