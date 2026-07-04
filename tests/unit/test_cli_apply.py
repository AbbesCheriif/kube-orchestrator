"""Unit tests for the `apply` CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from kube_orchestrator.cli.commands.apply import app

runner = CliRunner()


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    path = tmp_path / "pod.yaml"
    path.write_text("apiVersion: v1\nkind: Pod\n")
    return path


@pytest.mark.unit
class TestApplyCommand:
    def test_missing_path_exits_1(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [str(tmp_path / "missing.yaml")])
        assert result.exit_code == 1

    def test_missing_values_file_exits_1(
        self, manifest_file: Path, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app, [str(manifest_file), "--values", str(tmp_path / "missing-values.yaml")]
        )
        assert result.exit_code == 1

    def test_applies_single_file_and_prints_results(self, manifest_file: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.applier.ManifestApplier") as applier_cls,
        ):
            applier_cls.return_value.apply_file.return_value = [
                {"action": "created", "kind": "Pod", "name": "web"}
            ]
            result = runner.invoke(app, [str(manifest_file)])

        assert result.exit_code == 0
        assert "CREATED: Pod/web" in result.stdout
        applier_cls.return_value.apply_file.assert_called_once()

    def test_applies_directory_recursively(self, tmp_path: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.applier.ManifestApplier") as applier_cls,
        ):
            applier_cls.return_value.apply_directory.return_value = []
            result = runner.invoke(app, [str(tmp_path), "--recursive"])

        assert result.exit_code == 0
        applier_cls.return_value.apply_directory.assert_called_once()
        assert (
            applier_cls.return_value.apply_directory.call_args.kwargs["recursive"]
            is True
        )

    def test_dry_run_prints_warning(self, manifest_file: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.applier.ManifestApplier") as applier_cls,
        ):
            applier_cls.return_value.apply_file.return_value = []
            result = runner.invoke(app, [str(manifest_file), "--dry-run"])

        assert "DRY-RUN" in result.stdout
        assert applier_cls.call_args.kwargs["dry_run"] is True

    def test_wait_flag_prints_waiting_message(self, manifest_file: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.applier.ManifestApplier") as applier_cls,
        ):
            applier_cls.return_value.apply_file.return_value = []
            result = runner.invoke(app, [str(manifest_file), "--wait"])

        assert "Waiting for resources" in result.stdout

    def test_values_file_is_loaded_and_passed(
        self, manifest_file: Path, tmp_path: Path
    ) -> None:
        values_path = tmp_path / "values.yaml"
        values_path.write_text("replicas: 3\n")
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.applier.ManifestApplier") as applier_cls,
        ):
            applier_cls.return_value.apply_file.return_value = []
            runner.invoke(app, [str(manifest_file), "--values", str(values_path)])

        assert applier_cls.return_value.apply_file.call_args.kwargs["values"] == {
            "replicas": 3
        }

    def test_apply_failure_exits_1(self, manifest_file: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.applier.ManifestApplier") as applier_cls,
        ):
            applier_cls.return_value.apply_file.side_effect = RuntimeError("boom")
            result = runner.invoke(app, [str(manifest_file)])

        assert result.exit_code == 1
