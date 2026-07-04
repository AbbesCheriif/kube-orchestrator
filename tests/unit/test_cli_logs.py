"""Unit tests for the `logs` CLI command."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from kube_orchestrator.cli.commands.logs import app

runner = CliRunner()


@pytest.mark.unit
class TestLogsCommand:
    def test_streams_and_echoes_log_lines(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.resources.workloads.pod.PodManager") as pod_cls,
        ):
            pod_cls.return_value.stream_logs.return_value = iter(
                ["line one\n", "line two\n"]
            )
            result = runner.invoke(app, ["web-1"])

        assert result.exit_code == 0
        assert "line one" in result.stdout
        assert "line two" in result.stdout

    def test_passes_options_through_to_stream_logs(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.resources.workloads.pod.PodManager") as pod_cls,
        ):
            pod_cls.return_value.stream_logs.return_value = iter([])
            runner.invoke(
                app,
                [
                    "web-1",
                    "--namespace",
                    "prod",
                    "--container",
                    "app",
                    "--tail",
                    "50",
                    "--since",
                    "60",
                    "--timestamps",
                ],
            )

        kwargs = pod_cls.return_value.stream_logs.call_args.kwargs
        assert kwargs["container"] == "app"
        assert kwargs["tail_lines"] == 50
        assert kwargs["since_seconds"] == 60
        assert kwargs["timestamps"] is True

    def test_keyboard_interrupt_is_silently_handled(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.resources.workloads.pod.PodManager") as pod_cls,
        ):
            pod_cls.return_value.stream_logs.side_effect = KeyboardInterrupt()
            result = runner.invoke(app, ["web-1"])

        assert result.exit_code == 0

    def test_stream_failure_exits_1(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.resources.workloads.pod.PodManager") as pod_cls,
        ):
            pod_cls.return_value.stream_logs.side_effect = RuntimeError("not found")
            result = runner.invoke(app, ["web-1"])

        assert result.exit_code == 1
