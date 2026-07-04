"""Unit tests for kube_orchestrator.core.context."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.core import context as context_module
from kube_orchestrator.core.context import (
    ExecutionContext,
    get_active_context,
    use_context,
    use_dry_run,
    use_namespace,
)


@pytest.fixture(autouse=True)
def reset_active_context():
    original = context_module._active
    context_module._active = ExecutionContext()
    yield
    context_module._active = original


@pytest.mark.unit
class TestExecutionContext:
    def test_defaults(self) -> None:
        ctx = ExecutionContext()
        assert ctx.namespace == "default"
        assert ctx.context is None
        assert ctx.dry_run is False
        assert ctx.timeout == 30

    def test_get_active_context_returns_singleton(self) -> None:
        assert get_active_context() is context_module._active


@pytest.mark.unit
class TestUseNamespace:
    def test_overrides_namespace_within_block(self) -> None:
        with use_namespace("prod") as ctx:
            assert ctx.namespace == "prod"
            assert get_active_context().namespace == "prod"
        assert get_active_context().namespace == "default"

    def test_restores_namespace_after_exception(self) -> None:
        with pytest.raises(ValueError), use_namespace("prod"):
            raise ValueError("boom")
        assert get_active_context().namespace == "default"

    def test_nested_namespace_overrides(self) -> None:
        with use_namespace("prod"):
            with use_namespace("staging"):
                assert get_active_context().namespace == "staging"
            assert get_active_context().namespace == "prod"


@pytest.mark.unit
class TestUseDryRun:
    def test_enables_dry_run_within_block(self) -> None:
        with use_dry_run() as ctx:
            assert ctx.dry_run is True
        assert get_active_context().dry_run is False

    def test_restores_dry_run_after_exception(self) -> None:
        with pytest.raises(ValueError), use_dry_run():
            raise ValueError("boom")
        assert get_active_context().dry_run is False


@pytest.mark.unit
class TestUseContext:
    def test_switches_context_and_restores(self) -> None:
        mock_client = MagicMock()
        original_config = MagicMock()
        mock_client._api_client.configuration = original_config

        with (
            patch(
                "kube_orchestrator.core.client.KubeClient.get_instance",
                return_value=mock_client,
            ),
            patch("kube_orchestrator.core.config.KubeConfig") as mock_config_cls,
        ):
            new_config = MagicMock()
            mock_config_cls.return_value.configuration = new_config

            with use_context("staging") as ctx:
                assert ctx.context == "staging"
                assert mock_client._api_client.configuration is new_config
                mock_config_cls.return_value.switch_context.assert_called_once_with(
                    "staging"
                )

            assert mock_client._api_client.configuration is original_config
        assert get_active_context().context is None

    def test_restores_context_after_exception(self) -> None:
        mock_client = MagicMock()
        original_config = MagicMock()
        mock_client._api_client.configuration = original_config

        with (
            patch(
                "kube_orchestrator.core.client.KubeClient.get_instance",
                return_value=mock_client,
            ),
            patch("kube_orchestrator.core.config.KubeConfig") as mock_config_cls,
        ):
            mock_config_cls.return_value.configuration = MagicMock()
            with pytest.raises(ValueError), use_context("staging"):
                raise ValueError("boom")

        assert mock_client._api_client.configuration is original_config
        assert get_active_context().context is None
