"""Unit tests for the `doctor` CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kube_orchestrator.cli.commands.doctor import app

runner = CliRunner()


def _healthy_report() -> dict:
    return {
        "score": 95,
        "nodes": {"total": 3, "ready": 3, "not_ready": 0, "nodes": []},
        "control_plane": {
            "api_server": True,
            "scheduler": True,
            "controller_manager": True,
        },
        "workloads": {"checked": False, "reason": "no namespace specified"},
        "storage": {"checked": False, "reason": "no namespace specified"},
        "networking": {"checked": False, "reason": "no namespace specified"},
    }


@pytest.mark.unit
class TestDoctorCommand:
    def test_healthy_cluster_prints_success(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.monitoring.health.ClusterHealthReporter"
            ) as reporter_cls,
        ):
            reporter_cls.return_value.get_cluster_health.return_value = (
                _healthy_report()
            )
            result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "cluster is healthy" in result.stdout

    def test_degraded_cluster_prints_warning_without_exit(self) -> None:
        report = _healthy_report()
        report["score"] = 65
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.monitoring.health.ClusterHealthReporter"
            ) as reporter_cls,
        ):
            reporter_cls.return_value.get_cluster_health.return_value = report
            result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "some issues detected" in result.stdout

    def test_critical_cluster_exits_with_code_2(self) -> None:
        report = _healthy_report()
        report["score"] = 20
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.monitoring.health.ClusterHealthReporter"
            ) as reporter_cls,
        ):
            reporter_cls.return_value.get_cluster_health.return_value = report
            result = runner.invoke(app, [])

        assert result.exit_code == 2
        assert "critical issues detected" in result.stdout

    def test_namespace_flag_adds_workload_detail(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.monitoring.health.ClusterHealthReporter"
            ) as reporter_cls,
        ):
            reporter_cls.return_value.get_cluster_health.return_value = (
                _healthy_report()
            )
            reporter_cls.return_value.get_workload_health.return_value = {
                "namespace": "default",
                "pods": {"total": 2},
            }
            result = runner.invoke(app, ["--namespace", "default"])

        assert result.exit_code == 0
        reporter_cls.return_value.get_workload_health.assert_called_once_with(
            "default"
        )

    def test_fix_flag_prints_warning(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.monitoring.health.ClusterHealthReporter"
            ) as reporter_cls,
        ):
            reporter_cls.return_value.get_cluster_health.return_value = (
                _healthy_report()
            )
            result = runner.invoke(app, ["--fix"])

        assert "Auto-fix mode enabled" in result.stdout

    def test_health_check_failure_exits_1(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.monitoring.health.ClusterHealthReporter"
            ) as reporter_cls,
        ):
            reporter_cls.return_value.get_cluster_health.side_effect = RuntimeError(
                "unreachable"
            )
            result = runner.invoke(app, [])

        assert result.exit_code == 1
