"""Unit tests for kube_orchestrator.core.logging."""

from __future__ import annotations

import pytest
import structlog

from kube_orchestrator.core.logging import configure_logging, get_logger


@pytest.mark.unit
class TestConfigureLogging:
    def test_json_format_configures_json_renderer(self) -> None:
        configure_logging(level="DEBUG", format="json")
        config = structlog.get_config()
        assert any(
            isinstance(p, structlog.processors.JSONRenderer)
            for p in config["processors"]
        )

    def test_console_format_configures_console_renderer(self) -> None:
        configure_logging(level="INFO", format="console")
        config = structlog.get_config()
        assert any(
            isinstance(p, structlog.dev.ConsoleRenderer) for p in config["processors"]
        )

    def test_unknown_level_falls_back_to_info(self) -> None:
        configure_logging(level="NOT_A_LEVEL", format="console")
        # Should not raise; falling back to INFO internally.

    def test_default_arguments(self) -> None:
        configure_logging()
        config = structlog.get_config()
        assert any(
            isinstance(p, structlog.dev.ConsoleRenderer) for p in config["processors"]
        )


@pytest.mark.unit
class TestGetLogger:
    def test_returns_bound_logger(self) -> None:
        logger = get_logger("my.module")
        assert logger is not None
        # Should support standard structlog logging calls without raising.
        logger.info("test_event", key="value")
