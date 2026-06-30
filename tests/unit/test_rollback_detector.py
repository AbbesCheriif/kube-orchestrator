"""Unit tests for kube_orchestrator.rollback.detector."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.rollback.detector import RolloutDetector


def _run_and_join(action) -> None:  # noqa: ANN001 - test helper
    created: dict[str, threading.Thread] = {}
    real_thread = threading.Thread

    def _capture(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        thread = real_thread(*args, **kwargs)
        created["thread"] = thread
        return thread

    with patch("kube_orchestrator.rollback.detector.threading.Thread", side_effect=_capture):
        action()
    created["thread"].join(timeout=2)
    assert not created["thread"].is_alive()


@pytest.fixture
def detector(mock_kube_client: MagicMock) -> RolloutDetector:
    return RolloutDetector(client=mock_kube_client)


def _condition(cond_type: str, reason: str = "", status: str = "", message: str = ""):
    cond = MagicMock()
    cond.type = cond_type
    cond.reason = reason
    cond.status = status
    cond.message = message
    return cond


@pytest.mark.unit
class TestDetectFailedRollout:
    def test_true_when_progress_deadline_exceeded(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = [
            _condition("Progressing", reason="ProgressDeadlineExceeded")
        ]
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.detect_failed_rollout("web", "default") is True

    def test_true_when_unavailable_replicas_present(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = []
        deploy.spec.replicas = 3
        deploy.status.updated_replicas = 1
        deploy.status.available_replicas = 1
        deploy.status.unavailable_replicas = 2
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.detect_failed_rollout("web", "default") is True

    def test_false_when_healthy(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = []
        deploy.spec.replicas = 3
        deploy.status.updated_replicas = 3
        deploy.status.available_replicas = 3
        deploy.status.unavailable_replicas = 0
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.detect_failed_rollout("web", "default") is False

    def test_false_when_behind_but_no_unavailable(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = []
        deploy.spec.replicas = 3
        deploy.status.updated_replicas = 2
        deploy.status.available_replicas = 3
        deploy.status.unavailable_replicas = 0
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.detect_failed_rollout("web", "default") is False

    def test_false_on_api_error(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.side_effect = RuntimeError(
            "boom"
        )
        assert detector.detect_failed_rollout("web", "default") is False


@pytest.mark.unit
class TestGetFailureReason:
    def test_returns_progressing_false_message(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = [
            _condition("Progressing", status="False", message="stuck")
        ]
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.get_failure_reason("web", "default") == "stuck"

    def test_returns_available_false_message(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = [
            _condition("Available", status="False", message="no pods ready")
        ]
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.get_failure_reason("web", "default") == "no pods ready"

    def test_returns_none_when_no_matching_condition(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = [_condition("Progressing", status="True")]
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.get_failure_reason("web", "default") is None

    def test_returns_none_on_error(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.side_effect = RuntimeError(
            "boom"
        )
        assert detector.get_failure_reason("web", "default") is None


@pytest.mark.unit
class TestIsRolloutStuck:
    def test_true_on_progress_deadline_exceeded(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = [
            _condition("Progressing", reason="ProgressDeadlineExceeded")
        ]
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.is_rollout_stuck("web", "default") is True

    def test_true_when_observed_generation_behind(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = []
        deploy.status.observed_generation = 1
        deploy.metadata.generation = 2
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.is_rollout_stuck("web", "default") is True

    def test_false_when_up_to_date(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = []
        deploy.status.observed_generation = 2
        deploy.metadata.generation = 2
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.is_rollout_stuck("web", "default") is False

    def test_false_on_error(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.side_effect = RuntimeError(
            "boom"
        )
        assert detector.is_rollout_stuck("web", "default") is False


@pytest.mark.unit
class TestCheckPodErrors:
    def test_returns_empty_when_no_selector(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.spec.selector = None
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.check_pod_errors("web", "default") == []

    def test_returns_empty_when_selector_has_no_match_labels(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.spec.selector.match_labels = None
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        assert detector.check_pod_errors("web", "default") == []

    def test_collects_crash_loop_and_image_pull_errors(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.spec.selector.match_labels = {"app": "web"}
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        pod = MagicMock()
        pod.metadata.name = "web-1"
        cs = MagicMock()
        cs.name = "app"
        cs.state.waiting.reason = "CrashLoopBackOff"
        cs.state.waiting.message = "back-off restarting"
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        errors = detector.check_pod_errors("web", "default")

        assert errors == [
            {
                "pod": "web-1",
                "container": "app",
                "reason": "CrashLoopBackOff",
                "message": "back-off restarting",
            }
        ]

    def test_ignores_non_error_waiting_reasons(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.spec.selector.match_labels = {"app": "web"}
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        pod = MagicMock()
        cs = MagicMock()
        cs.state.waiting.reason = "ContainerCreating"
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        assert detector.check_pod_errors("web", "default") == []

    def test_ignores_containers_not_waiting(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.spec.selector.match_labels = {"app": "web"}
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        pod = MagicMock()
        cs = MagicMock()
        cs.state.waiting = None
        pod.status.container_statuses = [cs]
        mock_kube_client.core_v1.list_namespaced_pod.return_value.items = [pod]

        assert detector.check_pod_errors("web", "default") == []

    def test_returns_empty_on_error(
        self, detector: RolloutDetector, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.side_effect = RuntimeError(
            "boom"
        )
        assert detector.check_pod_errors("web", "default") == []


@pytest.mark.unit
class TestWatchAndDetect:
    def test_invokes_callback_on_progress_deadline_exceeded(
        self, detector: RolloutDetector
    ) -> None:
        deploy = MagicMock()
        deploy.status.conditions = [
            _condition("Progressing", reason="ProgressDeadlineExceeded")
        ]
        events = [{"type": "MODIFIED", "object": deploy}]
        received: list[tuple[str, str]] = []

        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.return_value = events
            _run_and_join(
                lambda: detector.watch_and_detect(
                    "web", "default", lambda name, ns: received.append((name, ns))
                )
            )

        assert received == [("web", "default")]
        watch_cls.return_value.stop.assert_called_once()

    def test_swallows_stream_errors(self, detector: RolloutDetector) -> None:
        with patch("kubernetes.watch.Watch") as watch_cls:
            watch_cls.return_value.stream.side_effect = RuntimeError("connection lost")
            _run_and_join(
                lambda: detector.watch_and_detect("web", "default", lambda name, ns: None)
            )
