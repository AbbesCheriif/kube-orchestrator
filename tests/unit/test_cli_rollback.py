"""Unit tests for the `rollback` CLI command."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from kube_orchestrator.cli.commands.rollback import app

runner = CliRunner()


@pytest.mark.unit
class TestRollbackCommand:
    def test_with_revision_calls_rollback_to_revision(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.rollback.auto_rollback.AutoRollback"
            ) as rollback_cls,
        ):
            result = runner.invoke(app, ["web", "--revision", "3"])

        assert result.exit_code == 0
        rollback_cls.return_value.rollback_to_revision.assert_called_once_with(
            "web", "default", 3
        )
        rollback_cls.return_value.trigger_rollback.assert_not_called()
        assert "completed" in result.stdout

    def test_without_revision_calls_trigger_rollback(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.rollback.auto_rollback.AutoRollback"
            ) as rollback_cls,
        ):
            result = runner.invoke(app, ["web"])

        assert result.exit_code == 0
        rollback_cls.return_value.trigger_rollback.assert_called_once_with(
            "web", "default", reason="CLI rollback request"
        )

    def test_dry_run_prints_warning_and_skips_success_message(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.rollback.auto_rollback.AutoRollback"),
        ):
            result = runner.invoke(app, ["web", "--dry-run"])

        assert "DRY-RUN" in result.stdout
        assert "completed" not in result.stdout

    def test_custom_namespace_is_passed_through(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.rollback.auto_rollback.AutoRollback"
            ) as rollback_cls,
        ):
            runner.invoke(app, ["web", "--namespace", "prod"])

        rollback_cls.return_value.trigger_rollback.assert_called_once_with(
            "web", "prod", reason="CLI rollback request"
        )

    def test_rollback_failure_exits_1(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch(
                "kube_orchestrator.rollback.auto_rollback.AutoRollback"
            ) as rollback_cls,
        ):
            rollback_cls.return_value.trigger_rollback.side_effect = RuntimeError(
                "boom"
            )
            result = runner.invoke(app, ["web"])

        assert result.exit_code == 1
