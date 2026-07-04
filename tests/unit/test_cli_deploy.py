"""Unit tests for the `deploy` CLI command."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from kube_orchestrator.cli.commands.deploy import app

runner = CliRunner()


@pytest.mark.unit
class TestDeployCommand:
    def test_deploys_with_defaults(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.resources.workloads.deployment.DeploymentManager"
            ) as dep_cls,
        ):
            result = runner.invoke(app, ["nginx:latest"])

        assert result.exit_code == 0
        assert "nginx" in result.stdout
        dep_cls.return_value.create_deployment.assert_called_once()

    def test_deployment_name_defaults_from_image(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.resources.workloads.deployment.DeploymentManager"
            ),
        ):
            result = runner.invoke(app, ["registry.io/team/api-server:1.2.3"])

        assert "api-server" in result.stdout

    def test_explicit_name_overrides_image_derived_name(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.resources.workloads.deployment.DeploymentManager"
            ),
        ):
            result = runner.invoke(app, ["nginx:latest", "--name", "my-web"])

        assert "my-web" in result.stdout

    def test_env_vars_are_parsed_and_applied(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.resources.workloads.deployment.DeploymentManager"
            ) as dep_cls,
        ):
            result = runner.invoke(
                app, ["nginx:latest", "--env", "FOO=bar", "--env", "malformed"]
            )

        assert result.exit_code == 0
        dep_cls.return_value.create_deployment.assert_called_once()

    def test_port_and_resource_requests_applied(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.resources.workloads.deployment.DeploymentManager"
            ) as dep_cls,
        ):
            result = runner.invoke(
                app,
                [
                    "nginx:latest",
                    "--port",
                    "8080",
                    "--cpu-request",
                    "100m",
                    "--memory-request",
                    "128Mi",
                ],
            )

        assert result.exit_code == 0
        dep_cls.return_value.create_deployment.assert_called_once()

    def test_dry_run_prints_info_message(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.resources.workloads.deployment.DeploymentManager"
            ),
        ):
            result = runner.invoke(app, ["nginx:latest", "--dry-run"])

        assert "Dry-run manifest generated successfully" in result.stdout

    def test_deploy_failure_exits_1(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.resources.workloads.deployment.DeploymentManager"
            ) as dep_cls,
        ):
            dep_cls.return_value.create_deployment.side_effect = RuntimeError("boom")
            result = runner.invoke(app, ["nginx:latest"])

        assert result.exit_code == 1
