"""Unit tests for the `delete` CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from kube_orchestrator.cli.commands.delete import app

runner = CliRunner()


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    path = tmp_path / "pod.yaml"
    path.write_text("apiVersion: v1\nkind: Pod\n")
    return path


@pytest.mark.unit
class TestDeleteCommand:
    def test_missing_path_exits_1(self, tmp_path: Path) -> None:
        result = runner.invoke(app, [str(tmp_path / "missing.yaml")])
        assert result.exit_code == 1

    def test_dry_run_lists_would_delete(self, manifest_file: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.deleter.ManifestDeleter") as deleter_cls,
        ):
            deleter_cls.return_value.dry_run_delete.return_value = [
                {"kind": "Pod", "name": "web"}
            ]
            result = runner.invoke(app, [str(manifest_file), "--dry-run"])

        assert result.exit_code == 0
        assert "WOULD DELETE: Pod/web" in result.stdout
        deleter_cls.return_value.delete_file.assert_not_called()

    def test_deletes_single_file(self, manifest_file: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.deleter.ManifestDeleter") as deleter_cls,
        ):
            deleter_cls.return_value.delete_file.return_value = ["web"]
            result = runner.invoke(app, [str(manifest_file)])

        assert result.exit_code == 0
        assert "DELETED: web" in result.stdout

    def test_deletes_directory(self, tmp_path: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.deleter.ManifestDeleter") as deleter_cls,
        ):
            deleter_cls.return_value.delete_directory.return_value = []
            result = runner.invoke(app, [str(tmp_path)])

        assert result.exit_code == 0
        deleter_cls.return_value.delete_directory.assert_called_once()

    def test_force_overrides_grace_period_to_zero(self, manifest_file: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.deleter.ManifestDeleter") as deleter_cls,
        ):
            deleter_cls.return_value.delete_file.return_value = []
            runner.invoke(app, [str(manifest_file), "--force", "--grace-period", "30"])

        assert (
            deleter_cls.return_value.delete_file.call_args.kwargs["grace_period"] == 0
        )

    def test_delete_failure_exits_1(self, manifest_file: Path) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeClient.get_instance"),
            patch("kube_orchestrator.manifest.deleter.ManifestDeleter") as deleter_cls,
        ):
            deleter_cls.return_value.delete_file.side_effect = RuntimeError("boom")
            result = runner.invoke(app, [str(manifest_file)])

        assert result.exit_code == 1
