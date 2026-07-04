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

    def test_load_from_file_sets_active_context(self) -> None:
        cfg = KubeConfig()
        with (
            patch("kube_orchestrator.core.config.load_kube_config") as mock_load,
            patch(
                "kube_orchestrator.core.config.list_kube_config_contexts"
            ) as mock_list,
        ):
            mock_list.return_value = ([{"name": "ctx1"}], {"name": "ctx1"})
            cfg.load_from_file("/path/to/kubeconfig")
        mock_load.assert_called_once()
        assert cfg._config_file == "/path/to/kubeconfig"
        assert cfg._active_context == "ctx1"

    def test_load_from_file_uses_default_path_when_none_given(self) -> None:
        cfg = KubeConfig()
        with (
            patch("kube_orchestrator.core.config.load_kube_config"),
            patch(
                "kube_orchestrator.core.config.list_kube_config_contexts"
            ) as mock_list,
        ):
            mock_list.return_value = ([], None)
            cfg.load_from_file()
        assert cfg._active_context is None

    def test_load_from_incluster_sets_context(self) -> None:
        cfg = KubeConfig()
        with patch(
            "kube_orchestrator.core.config.load_incluster_config"
        ) as mock_load:
            cfg.load_from_incluster()
        mock_load.assert_called_once()
        assert cfg._active_context == "in-cluster"
        assert cfg._config_file is None

    def test_get_current_context_returns_active(self) -> None:
        cfg = KubeConfig()
        cfg._active_context = "ctx1"
        assert cfg.get_current_context() == "ctx1"

    def test_get_current_context_raises_when_unset(self) -> None:
        cfg = KubeConfig()
        with pytest.raises(RuntimeError, match="No kubeconfig loaded"):
            cfg.get_current_context()

    def test_list_contexts_without_config_file_returns_active_only(self) -> None:
        cfg = KubeConfig()
        cfg._active_context = "ctx1"
        assert cfg.list_contexts() == ["ctx1"]

    def test_list_contexts_without_config_file_or_active_returns_empty(self) -> None:
        cfg = KubeConfig()
        assert cfg.list_contexts() == []

    def test_get_namespace_for_context_found(self) -> None:
        cfg = KubeConfig()
        cfg._config_file = "/fake/path"
        with patch(
            "kube_orchestrator.core.config.list_kube_config_contexts"
        ) as mock_list:
            mock_list.return_value = (
                [{"name": "ctx1", "context": {"namespace": "prod"}}],
                None,
            )
            assert cfg.get_namespace_for_context("ctx1") == "prod"

    def test_get_namespace_for_context_defaults_when_not_specified(self) -> None:
        cfg = KubeConfig()
        cfg._config_file = "/fake/path"
        with patch(
            "kube_orchestrator.core.config.list_kube_config_contexts"
        ) as mock_list:
            mock_list.return_value = ([{"name": "ctx1", "context": {}}], None)
            assert cfg.get_namespace_for_context("ctx1") == "default"

    def test_get_namespace_for_context_unknown_context(self) -> None:
        cfg = KubeConfig()
        with patch(
            "kube_orchestrator.core.config.list_kube_config_contexts"
        ) as mock_list:
            mock_list.return_value = ([{"name": "other"}], None)
            assert cfg.get_namespace_for_context("missing") == "default"

    def test_merge_kubeconfigs(self, tmp_path) -> None:
        cfg = KubeConfig()
        file_a = tmp_path / "a.yaml"
        file_a.write_text(
            "apiVersion: v1\nkind: Config\n"
            "clusters: [{name: c1}]\ncontexts: [{name: ctx1}]\n"
            "users: [{name: u1}]\ncurrent-context: ctx1\n"
        )
        file_b = tmp_path / "b.yaml"
        file_b.write_text(
            "apiVersion: v1\nkind: Config\n"
            "clusters: [{name: c2}]\ncontexts: [{name: ctx2}]\nusers: [{name: u2}]\n"
        )

        # list_kube_config_contexts.__wrapped__ is called directly with the
        # merged dict; patch that attribute explicitly on the imported name.
        with (
            patch("kube_orchestrator.core.config.load_kube_config_from_dict"),
            patch(
                "kube_orchestrator.core.config.list_kube_config_contexts"
            ) as mock_list,
        ):
            mock_list.__wrapped__ = lambda merged: (
                [{"name": "ctx1"}, {"name": "ctx2"}],
                {"name": "ctx1"},
            )
            cfg.merge_kubeconfigs([str(file_a), str(file_b)])

        assert cfg._config_file is None
        assert cfg._active_context == "ctx1"

    def test_configuration_property(self) -> None:
        cfg = KubeConfig()
        assert cfg.configuration is cfg._configuration
