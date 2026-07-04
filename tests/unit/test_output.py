"""Unit tests for kube_orchestrator.cli.output."""

from __future__ import annotations

import io

import pytest
from rich.console import Console

from kube_orchestrator.cli import output


@pytest.fixture
def captured_console(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    buffer = io.StringIO()
    monkeypatch.setattr(
        output, "_console", Console(file=buffer, force_terminal=False, width=120)
    )
    return buffer


@pytest.mark.unit
class TestPrintHealthReport:
    def test_healthy_report_shows_real_values_not_unknown(
        self, captured_console: io.StringIO
    ) -> None:
        report = {
            "score": 100,
            "nodes": {"total": 3, "ready": 3, "not_ready": 0, "nodes": []},
            "control_plane": {
                "api_server": True,
                "scheduler": True,
                "controller_manager": True,
            },
            "workloads": {"checked": False, "reason": "no namespace specified"},
            "storage": {"checked": False, "reason": "no namespace specified"},
            "networking": {"checked": False, "reason": "no namespace specified"},
            "checked_at": "2026-06-29T10:00:00Z",
        }

        output.print_health_report(report)
        text = captured_console.getvalue()

        assert "unknown" not in text
        assert "3/3 ready" in text
        assert "api_server=up" in text
        assert "scheduler=up" in text
        assert "controller_manager=up" in text
        assert "no namespace specified" in text

    def test_degraded_nodes_section_shows_ratio(
        self, captured_console: io.StringIO
    ) -> None:
        report = {
            "score": 40,
            "nodes": {"total": 4, "ready": 2, "not_ready": 2, "nodes": []},
            "control_plane": {
                "api_server": True,
                "scheduler": False,
                "controller_manager": True,
            },
        }

        output.print_health_report(report)
        text = captured_console.getvalue()

        assert "2/4 ready" in text
        assert "scheduler=down" in text

    def test_node_health_error_is_surfaced(self, captured_console: io.StringIO) -> None:
        report = {
            "score": 0,
            "nodes": {"error": "connection refused", "ready": 0, "not_ready": 0, "total": 0},
            "control_plane": {
                "api_server": False,
                "scheduler": False,
                "controller_manager": False,
            },
        }

        output.print_health_report(report)
        text = captured_console.getvalue()

        assert "connection refused" in text

    def test_workload_section_with_data_is_rendered(
        self, captured_console: io.StringIO
    ) -> None:
        report = {
            "score": 90,
            "nodes": {"total": 1, "ready": 1, "not_ready": 0, "nodes": []},
            "control_plane": {
                "api_server": True,
                "scheduler": True,
                "controller_manager": True,
            },
            "workloads": {"namespace": "default", "pods": {"total": 2, "running": 2}},
        }

        output.print_health_report(report)
        text = captured_console.getvalue()

        assert "unknown" not in text
        assert "pods=" in text


@pytest.mark.unit
class TestPrintJsonYaml:
    def test_print_json_produces_parseable_output(
        self, captured_console: io.StringIO
    ) -> None:
        import json

        output.print_json({"nodes": [{"name": "worker-1", "status": "Ready"}]})
        data = json.loads(captured_console.getvalue())
        assert data == {"nodes": [{"name": "worker-1", "status": "Ready"}]}

    def test_print_yaml_produces_parseable_output(
        self, captured_console: io.StringIO
    ) -> None:
        import yaml

        output.print_yaml({"nodes": [{"name": "worker-1", "status": "Ready"}]})
        data = yaml.safe_load(captured_console.getvalue())
        assert data == {"nodes": [{"name": "worker-1", "status": "Ready"}]}
