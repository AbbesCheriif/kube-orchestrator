"""Unit tests for kube_orchestrator.monitoring.health."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from kube_orchestrator.monitoring.health import ClusterHealthReporter


@pytest.fixture
def reporter(mock_kube_client: MagicMock) -> ClusterHealthReporter:
    return ClusterHealthReporter(client=mock_kube_client)


def _node(name: str, ready: bool) -> MagicMock:
    node = MagicMock()
    node.metadata.name = name
    cond = MagicMock()
    cond.type = "Ready"
    cond.status = "True" if ready else "False"
    node.status.conditions = [cond]
    return node


@pytest.mark.unit
class TestCheckNodeHealth:
    def test_counts_ready_and_not_ready(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_node.return_value.items = [
            _node("a", True),
            _node("b", False),
        ]
        result = reporter.check_node_health()
        assert result["total"] == 2
        assert result["ready"] == 1
        assert result["not_ready"] == 1
        assert result["nodes"] == [
            {"name": "a", "ready": True},
            {"name": "b", "ready": False},
        ]

    def test_handles_node_without_conditions(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        node = MagicMock()
        node.metadata.name = "a"
        node.status.conditions = None
        mock_kube_client.core_v1.list_node.return_value.items = [node]
        result = reporter.check_node_health()
        assert result["not_ready"] == 1

    def test_returns_error_dict_on_exception(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_node.side_effect = RuntimeError("unreachable")
        result = reporter.check_node_health()
        assert result == {
            "error": "unreachable",
            "ready": 0,
            "not_ready": 0,
            "total": 0,
        }


@pytest.mark.unit
class TestCheckControlPlane:
    def test_all_healthy(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespace.return_value = MagicMock()
        scheduler_cs = MagicMock()
        scheduler_cs.metadata.name = "scheduler"
        healthy_cond = MagicMock(type="Healthy", status="True")
        scheduler_cs.conditions = [healthy_cond]
        controller_cs = MagicMock()
        controller_cs.metadata.name = "controller-manager"
        controller_cs.conditions = [healthy_cond]
        mock_kube_client.core_v1.list_component_status.return_value.items = [
            scheduler_cs,
            controller_cs,
        ]

        result = reporter.check_control_plane()

        assert result == {
            "api_server": True,
            "scheduler": True,
            "controller_manager": True,
        }

    def test_api_server_down(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespace.side_effect = RuntimeError("down")
        mock_kube_client.core_v1.list_component_status.side_effect = RuntimeError(
            "down"
        )
        result = reporter.check_control_plane()
        assert result["api_server"] is False
        assert result["scheduler"] is False
        assert result["controller_manager"] is False

    def test_component_unhealthy(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespace.return_value = MagicMock()
        scheduler_cs = MagicMock()
        scheduler_cs.metadata.name = "scheduler"
        unhealthy_cond = MagicMock(type="Healthy", status="False")
        scheduler_cs.conditions = [unhealthy_cond]
        mock_kube_client.core_v1.list_component_status.return_value.items = [
            scheduler_cs
        ]

        result = reporter.check_control_plane()
        assert result["scheduler"] is False

    def test_component_status_unavailable_leaves_defaults(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespace.return_value = MagicMock()
        mock_kube_client.core_v1.list_component_status.side_effect = RuntimeError(
            "not supported"
        )
        result = reporter.check_control_plane()
        assert result["api_server"] is True
        assert result["scheduler"] is False


@pytest.mark.unit
class TestGetClusterHealth:
    def test_aggregates_sections(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_node.return_value.items = [_node("a", True)]
        mock_kube_client.core_v1.list_namespace.return_value = MagicMock()
        mock_kube_client.core_v1.list_component_status.return_value.items = []

        report = reporter.get_cluster_health()

        assert report["nodes"]["total"] == 1
        assert report["workloads"] == {
            "checked": False,
            "reason": "no namespace specified",
        }
        assert report["storage"] == {
            "checked": False,
            "reason": "no namespace specified",
        }
        assert "checked_at" in report


@pytest.mark.unit
class TestComputeGlobalScore:
    def test_perfect_score(self, reporter: ClusterHealthReporter) -> None:
        score = reporter._compute_global_score(
            {"total": 3, "not_ready": 0}, {"api_server": True}
        )
        assert score == 100

    def test_penalizes_not_ready_nodes(self, reporter: ClusterHealthReporter) -> None:
        score = reporter._compute_global_score(
            {"total": 2, "not_ready": 1}, {"api_server": True}
        )
        assert score == 70

    def test_penalizes_api_server_down(self, reporter: ClusterHealthReporter) -> None:
        score = reporter._compute_global_score(
            {"total": 0, "not_ready": 0}, {"api_server": False}
        )
        assert score == 70

    def test_floors_at_worst_case_penalty(
        self, reporter: ClusterHealthReporter
    ) -> None:
        score = reporter._compute_global_score(
            {"total": 10, "not_ready": 10}, {"api_server": False}
        )
        assert score == 10


@pytest.mark.unit
class TestGetHealthScore:
    def test_full_score_when_all_ready(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_node.return_value.items = [_node("a", True)]
        assert reporter.get_health_score() == 100

    def test_penalizes_not_ready_nodes(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_node.return_value.items = [
            _node("a", True),
            _node("b", False),
        ]
        assert reporter.get_health_score() == 75

    def test_returns_full_score_when_node_check_fails_internally(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        # check_node_health() swallows exceptions and reports total=0, so the
        # ready-ratio penalty is skipped entirely (defensive, not an error path).
        mock_kube_client.core_v1.list_node.side_effect = RuntimeError("boom")
        assert reporter.get_health_score() == 100

    def test_penalizes_when_node_health_check_itself_raises(
        self, reporter: ClusterHealthReporter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise() -> dict:
            raise RuntimeError("unexpected")

        monkeypatch.setattr(reporter, "check_node_health", _raise)
        assert reporter.get_health_score() == 80

    def test_penalizes_crash_loops_and_pending_pods(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_node.return_value.items = [_node("a", True)]

        crashing_pod = MagicMock()
        crashing_pod.metadata.name = "crashy"
        cs = MagicMock()
        cs.restart_count = 5
        cs.name = "app"
        cs.last_state.terminated.reason = "Error"
        cs.last_state.terminated.message = "boom"
        crashing_pod.status.container_statuses = [cs]

        def _list_namespaced_pod(namespace: str, **kwargs: object) -> MagicMock:
            result = MagicMock()
            if kwargs.get("field_selector"):
                result.items = []
            else:
                result.items = [crashing_pod]
            return result

        mock_kube_client.core_v1.list_namespaced_pod.side_effect = _list_namespaced_pod

        score = reporter.get_health_score(namespace="default")
        assert score == 95

    def test_ignores_namespace_check_errors(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_node.return_value.items = [_node("a", True)]
        mock_kube_client.core_v1.list_namespaced_pod.side_effect = RuntimeError("boom")
        assert reporter.get_health_score(namespace="default") == 100

    def test_ignores_unexpected_namespace_check_exception(
        self,
        reporter: ClusterHealthReporter,
        mock_kube_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_kube_client.core_v1.list_node.return_value.items = []

        def _raise(_namespace: str) -> list:
            raise RuntimeError("unexpected")

        monkeypatch.setattr(reporter, "detect_crash_loops", _raise)
        assert reporter.get_health_score(namespace="default") == 100


@pytest.mark.unit
class TestGetWorkloadHealth:
    def test_counts_pod_phases_and_deployment_availability(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        running = MagicMock(status=MagicMock(phase="Running"))
        pending = MagicMock(status=MagicMock(phase="Pending"))
        failed = MagicMock(status=MagicMock(phase="Failed"))
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [
            running,
            pending,
            failed,
        ]

        available_dep = MagicMock()
        available_dep.spec.replicas = 2
        available_dep.status.available_replicas = 2
        degraded_dep = MagicMock()
        degraded_dep.spec.replicas = 3
        degraded_dep.status.available_replicas = 1
        mock_kube_client.apps_v1.list_namespaced_deployment.return_value.items = [
            available_dep,
            degraded_dep,
        ]

        result = reporter.get_workload_health("default")

        assert result["pods"] == {
            "total": 3,
            "running": 1,
            "pending": 1,
            "failed": 1,
        }
        assert result["deployments"] == {"total": 2, "available": 1, "degraded": 1}

    def test_swallows_pod_and_deployment_errors(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespaced_pod.side_effect = RuntimeError("boom")
        mock_kube_client.apps_v1.list_namespaced_deployment.side_effect = RuntimeError(
            "boom"
        )
        result = reporter.get_workload_health("default")
        assert result["pods"]["total"] == 0
        assert result["deployments"]["total"] == 0


@pytest.mark.unit
class TestAnalyzeReadiness:
    def test_splits_ready_and_not_ready_pods(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        ready_pod = MagicMock()
        ready_pod.metadata.name = "ready-1"
        ready_cond = MagicMock(type="Ready", status="True")
        ready_pod.status.conditions = [ready_cond]

        not_ready_pod = MagicMock()
        not_ready_pod.metadata.name = "not-ready-1"
        not_ready_cond = MagicMock(type="Ready", status="False")
        not_ready_pod.status.conditions = [not_ready_cond]

        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [
            ready_pod,
            not_ready_pod,
        ]

        result = reporter.analyze_readiness("default")

        assert result == {
            "ready": ["ready-1"],
            "not_ready": ["not-ready-1"],
            "total": 2,
        }

    def test_returns_empty_on_error(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespaced_pod.side_effect = RuntimeError("boom")
        result = reporter.analyze_readiness("default")
        assert result == {"ready": [], "not_ready": [], "total": 0}


@pytest.mark.unit
class TestDetectCrashLoops:
    def test_detects_containers_with_high_restart_count(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.metadata.name = "crashy"
        cs = MagicMock()
        cs.name = "app"
        cs.restart_count = 4
        cs.last_state.terminated.reason = "Error"
        cs.last_state.terminated.message = "exit 1"
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        result = reporter.detect_crash_loops("default")

        assert result == [
            {
                "pod": "crashy",
                "container": "app",
                "restart_count": 4,
                "reason": "Error",
                "last_message": "exit 1",
            }
        ]

    def test_ignores_low_restart_counts(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        pod = MagicMock()
        cs = MagicMock()
        cs.restart_count = 1
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        assert reporter.detect_crash_loops("default") == []

    def test_handles_missing_last_state(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.metadata.name = "crashy"
        cs = MagicMock()
        cs.name = "app"
        cs.restart_count = 5
        cs.last_state.terminated = None
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        result = reporter.detect_crash_loops("default")
        assert result[0]["reason"] == ""
        assert result[0]["last_message"] == ""

    def test_returns_empty_on_error(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespaced_pod.side_effect = RuntimeError("boom")
        assert reporter.detect_crash_loops("default") == []


@pytest.mark.unit
class TestGetPendingPods:
    def test_collects_pending_pod_details(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.metadata.name = "pending-1"
        pod.metadata.creation_timestamp = datetime.utcnow() - timedelta(minutes=5)
        cond = MagicMock(type="PodScheduled", status="False", reason="Unschedulable")
        pod.status.conditions = [cond]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        result = reporter.get_pending_pods("default")

        assert result[0]["pod"] == "pending-1"
        assert result[0]["reason"] == "Unschedulable"
        assert result[0]["duration"] != ""

    def test_handles_missing_creation_timestamp(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.metadata.name = "pending-1"
        pod.metadata.creation_timestamp = None
        pod.status.conditions = []
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        result = reporter.get_pending_pods("default")
        assert result[0]["duration"] == ""
        assert result[0]["reason"] == ""

    def test_returns_empty_on_error(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespaced_pod.side_effect = RuntimeError("boom")
        assert reporter.get_pending_pods("default") == []


@pytest.mark.unit
class TestGetFailedDeployments:
    def test_lists_deployments_below_desired_replicas(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.metadata.name = "web"
        deploy.spec.replicas = 3
        deploy.status.available_replicas = 1
        mock_kube_client.apps_v1.list_namespaced_deployment.return_value.items = [
            deploy
        ]

        result = reporter.get_failed_deployments("default")

        assert result == [{"name": "web", "desired": 3, "available": 1}]

    def test_excludes_healthy_deployments(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.spec.replicas = 2
        deploy.status.available_replicas = 2
        mock_kube_client.apps_v1.list_namespaced_deployment.return_value.items = [
            deploy
        ]
        assert reporter.get_failed_deployments("default") == []

    def test_returns_empty_on_error(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.list_namespaced_deployment.side_effect = RuntimeError(
            "boom"
        )
        assert reporter.get_failed_deployments("default") == []


@pytest.mark.unit
class TestGetOomKilledPods:
    def test_detects_oom_from_current_state(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.metadata.name = "oom-1"
        cs = MagicMock()
        cs.name = "app"
        cs.state.terminated.reason = "OOMKilled"
        cs.last_state.terminated = None
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        result = reporter.get_oom_killed_pods("default")
        assert result == [{"pod": "oom-1", "container": "app"}]

    def test_detects_oom_from_last_state_when_current_absent(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        pod = MagicMock()
        pod.metadata.name = "oom-2"
        cs = MagicMock()
        cs.name = "app"
        cs.state.terminated = None
        cs.last_state.terminated.reason = "OOMKilled"
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        result = reporter.get_oom_killed_pods("default")
        assert result == [{"pod": "oom-2", "container": "app"}]

    def test_ignores_non_oom_terminations(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        pod = MagicMock()
        cs = MagicMock()
        cs.state.terminated.reason = "Completed"
        cs.last_state.terminated = None
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        assert reporter.get_oom_killed_pods("default") == []

    def test_returns_empty_on_error(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.list_namespaced_pod.side_effect = RuntimeError("boom")
        assert reporter.get_oom_killed_pods("default") == []


@pytest.mark.unit
class TestGenerateHealthReport:
    def _setup_healthy_cluster(self, mock_kube_client: MagicMock) -> None:
        mock_kube_client.core_v1.list_node.return_value.items = [_node("a", True)]
        mock_kube_client.core_v1.list_namespace.return_value = MagicMock()
        mock_kube_client.core_v1.list_component_status.return_value.items = []
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = []
        mock_kube_client.apps_v1.list_namespaced_deployment.return_value.items = []

    def test_json_format_cluster_wide(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        self._setup_healthy_cluster(mock_kube_client)
        report_str = reporter.generate_health_report()
        parsed = json.loads(report_str)
        assert "cluster" in parsed
        assert "namespace" not in parsed

    def test_json_format_with_namespace_includes_details(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        self._setup_healthy_cluster(mock_kube_client)
        report_str = reporter.generate_health_report(namespace="default")
        parsed = json.loads(report_str)
        assert parsed["namespace"] == "default"
        assert "workloads" in parsed
        assert "crash_loops" in parsed
        assert "pending_pods" in parsed
        assert "failed_deployments" in parsed
        assert "oom_killed" in parsed
        assert "health_score" in parsed

    def test_markdown_format(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        self._setup_healthy_cluster(mock_kube_client)
        report_str = reporter.generate_health_report(format="markdown")
        assert report_str.startswith("# Health Report")
        assert "Cluster Score" in report_str
        assert "Nodes:" in report_str

    def test_text_format(
        self, reporter: ClusterHealthReporter, mock_kube_client: MagicMock
    ) -> None:
        self._setup_healthy_cluster(mock_kube_client)
        report_str = reporter.generate_health_report(format="text")
        assert "Health Report" in report_str
        assert "Global score" in report_str
        assert "Nodes" in report_str
