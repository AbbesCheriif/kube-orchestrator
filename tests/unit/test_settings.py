"""Unit tests for kube_orchestrator.core.settings."""

from __future__ import annotations

import pytest

from kube_orchestrator.core.settings import Settings, settings


@pytest.mark.unit
class TestSettings:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("KUBE_NAMESPACE", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        config = Settings(_env_file=None)
        assert config.kube_namespace == "default"
        assert config.log_level == "INFO"
        assert config.log_format == "console"
        assert config.retry_max_attempts == 3
        assert config.default_timeout == 30
        assert config.kubeconfig is None
        assert config.kube_context is None

    def test_overrides_from_constructor(self) -> None:
        config = Settings(
            kubeconfig="/tmp/kubeconfig",
            kube_context="staging",
            kube_namespace="prod",
            log_level="DEBUG",
            log_format="json",
            retry_max_attempts=5,
            default_timeout=60,
            _env_file=None,
        )
        assert config.kubeconfig == "/tmp/kubeconfig"
        assert config.kube_context == "staging"
        assert config.kube_namespace == "prod"
        assert config.log_level == "DEBUG"
        assert config.retry_max_attempts == 5
        assert config.default_timeout == 60

    def test_reads_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KUBE_NAMESPACE", "from-env")
        config = Settings(_env_file=None)
        assert config.kube_namespace == "from-env"

    def test_module_level_singleton_exists(self) -> None:
        assert isinstance(settings, Settings)
