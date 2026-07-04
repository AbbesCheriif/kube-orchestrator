"""Unit tests for the `status` CLI command output formats."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from kube_orchestrator.cli.commands.status import app

runner = CliRunner()


def _make_deployment() -> MagicMock:
    dep = MagicMock()
    dep.metadata.namespace = "default"
    dep.metadata.name = "web"
    dep.spec.replicas = 3
    dep.status.ready_replicas = 3
    dep.status.available_replicas = 3
    dep.metadata.creation_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return dep


def _make_pod() -> MagicMock:
    pod = MagicMock()
    pod.metadata.namespace = "default"
    pod.metadata.name = "web-abc123"
    pod.status.phase = "Running"
    pod.metadata.creation_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return pod


@pytest.fixture(autouse=True)
def _mock_managers() -> object:
    with (
        patch("kube_orchestrator.core.client.KubeClient.get_instance") as get_instance,
        patch(
            "kube_orchestrator.resources.workloads.deployment.DeploymentManager"
        ) as dep_cls,
        patch("kube_orchestrator.resources.workloads.pod.PodManager") as pod_cls,
    ):
        get_instance.return_value = MagicMock()
        dep_cls.return_value.list_deployments.return_value = [_make_deployment()]
        pod_cls.return_value.list_pods.return_value = [_make_pod()]
        yield


@pytest.mark.unit
class TestStatusOutputFormats:
    def test_table_output_is_default(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Deployments" in result.stdout
        assert "web" in result.stdout

    def test_json_output_is_valid_json(self) -> None:
        result = runner.invoke(app, ["--output", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["deployments"][0]["name"] == "web"
        assert data["pods"][0]["name"] == "web-abc123"

    def test_yaml_output_is_valid_yaml(self) -> None:
        result = runner.invoke(app, ["--output", "yaml"])
        assert result.exit_code == 0
        data = yaml.safe_load(result.stdout)
        assert data["deployments"][0]["status"] == "Available"
        assert data["pods"][0]["phase"] == "Running"

    def test_json_output_has_no_extra_banner_text(self) -> None:
        result = runner.invoke(app, ["--output", "json"])
        assert result.exit_code == 0
        assert "Fetching status" not in result.stdout
