"""Unit tests for the `nodes list` CLI command output formats."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kube_orchestrator.cli.commands.nodes import app

runner = CliRunner()


def _make_node(name: str) -> MagicMock:
    node = MagicMock()
    node.metadata.name = name
    node.metadata.creation_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return node


@pytest.fixture(autouse=True)
def _mock_manager() -> object:
    with (
        patch("kube_orchestrator.core.client.KubeClient.get_instance") as get_instance,
        patch("kube_orchestrator.resources.cluster.node.NodeManager") as node_cls,
    ):
        get_instance.return_value = MagicMock()
        manager = node_cls.return_value
        manager.list_nodes.return_value = [_make_node("worker-1")]
        manager.is_ready.return_value = True
        manager.is_schedulable.return_value = True
        yield


@pytest.mark.unit
class TestNodesListOutputFormats:
    def test_table_output_is_default(self) -> None:
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "Nodes" in result.stdout
        assert "worker-1" in result.stdout

    def test_json_output_is_valid_json(self) -> None:
        result = runner.invoke(app, ["list", "--output", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["nodes"][0]["name"] == "worker-1"
        assert data["nodes"][0]["status"] == "Ready"
        assert data["nodes"][0]["schedulable"] == "Yes"

    def test_json_output_reflects_cordoned_node(self) -> None:
        with (
            patch(
                "kube_orchestrator.core.client.KubeClient.get_instance"
            ) as get_instance,
            patch("kube_orchestrator.resources.cluster.node.NodeManager") as node_cls,
        ):
            get_instance.return_value = MagicMock()
            manager = node_cls.return_value
            manager.list_nodes.return_value = [_make_node("worker-2")]
            manager.is_ready.return_value = False
            manager.is_schedulable.return_value = False

            result = runner.invoke(app, ["list", "--output", "json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["nodes"][0]["status"] == "NotReady"
            assert data["nodes"][0]["schedulable"] == "No (cordoned)"
