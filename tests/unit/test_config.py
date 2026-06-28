"""Unit tests for KubeConfig."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from kubernetes.config.config_exception import ConfigException

from kube_orchestrator.core.config import KubeConfig


@pytest.mark.unit
class TestKubeConfig:
    def test_load_default_tries_incluster_first(self) -> None:
        cfg = KubeConfig()
        with (
            patch.object(cfg, "load_from_incluster") as mock_incluster,
            patch.object(cfg, "load_from_file") as mock_file,
        ):
            cfg.load_default()
            mock_incluster.assert_called_once()
            mock_file.assert_not_called()

    def test_load_default_falls_back_to_file(self) -> None:
        cfg = KubeConfig()
        with (
            patch.object(
                cfg,
                "load_from_incluster",
                side_effect=ConfigException("not in cluster"),
            ),
            patch.object(cfg, "load_from_file") as mock_file,
        ):
            cfg.load_default()
            mock_file.assert_called_once()

    def test_list_contexts_returns_list(self) -> None:
        cfg = KubeConfig()
        cfg._config_file = "/fake/path"
        with patch(
            "kube_orchestrator.core.config.list_kube_config_contexts"
        ) as mock_list:
            mock_list.return_value = (
                [{"name": "ctx1"}, {"name": "ctx2"}],
                {"name": "ctx1"},
            )
            result = cfg.list_contexts()
            assert isinstance(result, list)
            assert len(result) == 2

    def test_switch_context_calls_load(self) -> None:
        cfg = KubeConfig()
        with patch("kube_orchestrator.core.config.load_kube_config") as mock_load:
            cfg.switch_context("my-context")
            mock_load.assert_called_once()
            assert mock_load.call_args.kwargs["context"] == "my-context"
