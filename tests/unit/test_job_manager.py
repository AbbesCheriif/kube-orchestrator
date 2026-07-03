"""Unit tests for JobManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError
from kube_orchestrator.resources.workloads.job import JobManager


@pytest.fixture
def job_manager(mock_kube_client: MagicMock) -> JobManager:
    return JobManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestJobManager:
    def test_create_job(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_batch_v1.create_namespaced_job.return_value = MagicMock()
        job_manager.create_job(
            name="batch-job",
            namespace="default",
            pod_template={
                "spec": {
                    "containers": [{"name": "worker", "image": "python:3.12"}],
                    "restartPolicy": "Never",
                }
            },
            backoff_limit=3,
        )
        mock_batch_v1.create_namespaced_job.assert_called_once()

    def test_is_complete_true(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_job = MagicMock()
        mock_condition = MagicMock()
        mock_condition.type = "Complete"
        mock_condition.status = "True"
        mock_job.status.conditions = [mock_condition]
        mock_batch_v1.read_namespaced_job.return_value = mock_job
        assert job_manager.is_complete("batch-job", "default") is True

    def test_is_complete_false(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_job = MagicMock()
        mock_job.status.conditions = []
        mock_batch_v1.read_namespaced_job.return_value = mock_job
        assert job_manager.is_complete("batch-job", "default") is False

    def test_suspend_job(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_job = MagicMock()
        mock_batch_v1.read_namespaced_job.return_value = mock_job
        mock_batch_v1.patch_namespaced_job.return_value = mock_job
        job_manager.suspend_job("batch-job", "default")
        mock_batch_v1.patch_namespaced_job.assert_called_once()

    def test_create_job_with_all_optional_fields(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        job_manager.create_job(
            "batch-job",
            "default",
            completions=5,
            parallelism=2,
            active_deadline_seconds=600,
            ttl_seconds_after_finished=300,
            completion_mode="Indexed",
            suspend=True,
            manual_selector=True,
            pod_failure_policy={"rules": []},
            labels={"app": "batch"},
        )
        call_kwargs = mock_batch_v1.create_namespaced_job.call_args.kwargs
        spec = call_kwargs["body"]["spec"]
        assert spec["completions"] == 5
        assert spec["parallelism"] == 2
        assert spec["activeDeadlineSeconds"] == 600
        assert spec["ttlSecondsAfterFinished"] == 300
        assert spec["completionMode"] == "Indexed"
        assert spec["podFailurePolicy"] == {"rules": []}

    def test_get_job(self, job_manager: JobManager, mock_batch_v1: MagicMock) -> None:
        mock_batch_v1.read_namespaced_job.return_value = "job-obj"
        assert job_manager.get_job("batch-job", "default") == "job-obj"

    def test_list_jobs(self, job_manager: JobManager, mock_batch_v1: MagicMock) -> None:
        mock_batch_v1.list_namespaced_job.return_value.items = ["a"]
        assert job_manager.list_jobs("default") == ["a"]

    def test_delete_job(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        job_manager.delete_job("batch-job", "default")
        mock_batch_v1.delete_namespaced_job.assert_called_once()

    def test_resume_job(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        job_manager.resume_job("batch-job", "default")
        call_kwargs = mock_batch_v1.patch_namespaced_job.call_args.kwargs
        assert call_kwargs["body"]["spec"]["suspend"] is False

    def test_kind_and_api_version(self, job_manager: JobManager) -> None:
        assert job_manager._kind() == "Job"
        assert job_manager._api_version() == "batch/v1"


@pytest.mark.unit
class TestJobStatusHelpers:
    def test_get_status_full(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        cond = MagicMock()
        cond.to_dict.return_value = {"type": "Complete"}
        job = MagicMock()
        job.status.active = 0
        job.status.succeeded = 1
        job.status.failed = 0
        job.status.ready = 0
        job.status.start_time = "2026-01-01"
        job.status.completion_time = "2026-01-02"
        job.status.conditions = [cond]
        mock_batch_v1.read_namespaced_job.return_value = job

        status = job_manager.get_status("batch-job", "default")
        assert status["succeeded"] == 1
        assert status["conditions"] == [{"type": "Complete"}]

    def test_get_status_without_status(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        job = MagicMock(status=None)
        mock_batch_v1.read_namespaced_job.return_value = job
        status = job_manager.get_status("batch-job", "default")
        assert status == {
            "active": 0,
            "succeeded": 0,
            "failed": 0,
            "ready": 0,
            "start_time": None,
            "completion_time": None,
            "conditions": [],
        }

    def test_get_active_count(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        job = MagicMock()
        job.status.active = 2
        mock_batch_v1.read_namespaced_job.return_value = job
        assert job_manager.get_active_count("batch-job", "default") == 2

    def test_get_succeeded_count(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        job = MagicMock()
        job.status.succeeded = 3
        mock_batch_v1.read_namespaced_job.return_value = job
        assert job_manager.get_succeeded_count("batch-job", "default") == 3

    def test_get_failed_count(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        job = MagicMock()
        job.status.failed = 1
        mock_batch_v1.read_namespaced_job.return_value = job
        assert job_manager.get_failed_count("batch-job", "default") == 1

    def test_is_failed_true(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        cond = MagicMock(type="Failed", status="True")
        job = MagicMock()
        job.status.conditions = [cond]
        mock_batch_v1.read_namespaced_job.return_value = job
        assert job_manager.is_failed("batch-job", "default") is True

    def test_is_failed_false_without_conditions(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        job = MagicMock()
        job.status.conditions = []
        mock_batch_v1.read_namespaced_job.return_value = job
        assert job_manager.is_failed("batch-job", "default") is False

    def test_get_pods(
        self, job_manager: JobManager, mock_batch_v1: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        job = MagicMock()
        job.spec.selector.match_labels = {"job-name": "batch-job"}
        mock_batch_v1.read_namespaced_job.return_value = job
        mock_core_v1.list_namespaced_pod.return_value.items = ["pod-a"]

        result = job_manager.get_pods("batch-job", "default")
        assert result == ["pod-a"]

    def test_get_pods_raises_parsed_exception(
        self, job_manager: JobManager, mock_batch_v1: MagicMock, mock_core_v1: MagicMock
    ) -> None:
        job = MagicMock()
        job.spec.selector.match_labels = {"job-name": "batch-job"}
        mock_batch_v1.read_namespaced_job.return_value = job
        mock_core_v1.list_namespaced_pod.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            job_manager.get_pods("batch-job", "default")


@pytest.mark.unit
class TestWaitForCompletion:
    def test_returns_true_when_complete(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        cond = MagicMock(type="Complete", status="True")
        job = MagicMock()
        job.status.conditions = [cond]
        mock_batch_v1.read_namespaced_job.return_value = job
        assert (
            job_manager.wait_for_completion("batch-job", "default", timeout_seconds=5)
            is True
        )

    def test_returns_false_when_failed(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        cond = MagicMock(type="Failed", status="True")
        job = MagicMock()
        job.status.conditions = [cond]
        mock_batch_v1.read_namespaced_job.return_value = job
        assert (
            job_manager.wait_for_completion("batch-job", "default", timeout_seconds=5)
            is False
        )

    def test_ignores_not_found_and_times_out(
        self, job_manager: JobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_batch_v1.read_namespaced_job.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.workloads.job.time.sleep"):
            assert (
                job_manager.wait_for_completion(
                    "batch-job", "default", timeout_seconds=0.05
                )
                is False
            )
