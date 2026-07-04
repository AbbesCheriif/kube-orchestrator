"""Unit tests for kube_orchestrator.core.middleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.middleware import (
    RateLimitHandler,
    RetryConfig,
    TimeoutManager,
    with_retry,
)


@pytest.mark.unit
class TestRetryConfig:
    def test_defaults(self) -> None:
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.retry_on_exceptions == (ApiException,)


@pytest.mark.unit
class TestWithRetry:
    def test_succeeds_on_first_attempt(self) -> None:
        func = MagicMock(return_value="ok")
        wrapped = with_retry(func)
        assert wrapped(1, key="value") == "ok"
        func.assert_called_once_with(1, key="value")

    def test_retries_on_transient_api_error_then_succeeds(self) -> None:
        func = MagicMock(
            side_effect=[ApiException(status=503), "ok"]
        )
        cfg = RetryConfig(max_attempts=3, wait_fixed=0, wait_exponential_multiplier=0)
        with patch("kube_orchestrator.core.middleware.time.sleep"):
            wrapped = with_retry(func, cfg)
            assert wrapped() == "ok"
        assert func.call_count == 2

    def test_raises_immediately_on_non_retryable_status(self) -> None:
        func = MagicMock(side_effect=ApiException(status=404))
        wrapped = with_retry(func)
        with pytest.raises(ApiException):
            wrapped()
        assert func.call_count == 1

    def test_raises_after_exhausting_max_attempts(self) -> None:
        func = MagicMock(side_effect=ApiException(status=500))
        cfg = RetryConfig(max_attempts=2, wait_fixed=0, wait_exponential_multiplier=0)
        with patch("kube_orchestrator.core.middleware.time.sleep"):
            wrapped = with_retry(func, cfg)
            with pytest.raises(ApiException):
                wrapped()
        assert func.call_count == 2

    def test_retries_on_429(self) -> None:
        func = MagicMock(side_effect=[ApiException(status=429), "ok"])
        cfg = RetryConfig(max_attempts=3, wait_fixed=0, wait_exponential_multiplier=0)
        with patch("kube_orchestrator.core.middleware.time.sleep"):
            wrapped = with_retry(func, cfg)
            assert wrapped() == "ok"

    def test_retries_on_custom_exception_type(self) -> None:
        cfg = RetryConfig(
            max_attempts=2,
            wait_fixed=0,
            wait_exponential_multiplier=0,
            retry_on_exceptions=(ValueError,),
        )
        func = MagicMock(side_effect=[ValueError("transient"), "ok"])
        with patch("kube_orchestrator.core.middleware.time.sleep"):
            wrapped = with_retry(func, cfg)
            assert wrapped() == "ok"

    def test_delay_capped_at_exponential_max(self) -> None:
        cfg = RetryConfig(
            max_attempts=2,
            wait_fixed=100,
            wait_exponential_multiplier=100,
            wait_exponential_max=1,
        )
        func = MagicMock(side_effect=[ApiException(status=500), "ok"])
        with patch("kube_orchestrator.core.middleware.time.sleep") as mock_sleep:
            wrapped = with_retry(func, cfg)
            wrapped()
        mock_sleep.assert_called_once_with(1)


@pytest.mark.unit
class TestTimeoutManager:
    def test_active_timeout_defaults(self) -> None:
        mgr = TimeoutManager(default_timeout=30, watch_timeout=300)
        assert mgr.active_timeout == 30
        assert mgr.watch_timeout == 300

    def test_apply_timeout_overrides_within_block(self) -> None:
        mgr = TimeoutManager(default_timeout=30)
        with mgr.apply_timeout(120):
            assert mgr.active_timeout == 120
        assert mgr.active_timeout == 30

    def test_apply_timeout_restores_after_exception(self) -> None:
        mgr = TimeoutManager(default_timeout=30)
        with pytest.raises(ValueError):
            with mgr.apply_timeout(120):
                raise ValueError("boom")
        assert mgr.active_timeout == 30

    def test_nested_apply_timeout(self) -> None:
        mgr = TimeoutManager(default_timeout=30)
        with mgr.apply_timeout(60):
            with mgr.apply_timeout(90):
                assert mgr.active_timeout == 90
            assert mgr.active_timeout == 60
        assert mgr.active_timeout == 30


@pytest.mark.unit
class TestRateLimitHandler:
    def test_sleeps_for_retry_after_header(self) -> None:
        handler = RateLimitHandler()
        response = MagicMock()
        response.headers = {"Retry-After": "2"}
        with patch("kube_orchestrator.core.middleware.time.sleep") as mock_sleep:
            handler.handle_429(response)
        mock_sleep.assert_called_once_with(2)

    def test_defaults_to_five_seconds_without_headers(self) -> None:
        handler = RateLimitHandler()
        response = MagicMock()
        response.headers = None
        with patch("kube_orchestrator.core.middleware.time.sleep") as mock_sleep:
            handler.handle_429(response)
        mock_sleep.assert_called_once_with(5)

    def test_defaults_to_five_seconds_on_invalid_header(self) -> None:
        handler = RateLimitHandler()
        response = MagicMock()
        response.headers = {"Retry-After": "not-a-number"}
        with patch("kube_orchestrator.core.middleware.time.sleep") as mock_sleep:
            handler.handle_429(response)
        mock_sleep.assert_called_once_with(5)
