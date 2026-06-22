"""Unit tests for JobManager."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.workloads.job import JobManager


@pytest.fixture
def job_manager(mock_kube_client: MagicMock) -> JobManager:
    return JobManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestJobManager:
    def test_create_job(self, job_manager: JobManager, mock_batch_v1: MagicMock) -> None:
        mock_batch_v1.create_namespaced_job.return_value = MagicMock()
        job_manager.create_job(
            name="batch-job",
            namespace="default",
            pod_template={
                "spec": {"containers": [{"name": "worker", "image": "python:3.12"}], "restartPolicy": "Never"}
            },
            backoff_limit=3,
        )
        mock_batch_v1.create_namespaced_job.assert_called_once()

    def test_is_complete_true(self, job_manager: JobManager, mock_batch_v1: MagicMock) -> None:
        mock_job = MagicMock()
        mock_condition = MagicMock()
        mock_condition.type = "Complete"
        mock_condition.status = "True"
        mock_job.status.conditions = [mock_condition]
        mock_batch_v1.read_namespaced_job.return_value = mock_job
        assert job_manager.is_complete("batch-job", "default") is True

    def test_is_complete_false(self, job_manager: JobManager, mock_batch_v1: MagicMock) -> None:
        mock_job = MagicMock()
        mock_job.status.conditions = []
        mock_batch_v1.read_namespaced_job.return_value = mock_job
        assert job_manager.is_complete("batch-job", "default") is False

    def test_suspend_job(self, job_manager: JobManager, mock_batch_v1: MagicMock) -> None:
        mock_job = MagicMock()
        mock_batch_v1.read_namespaced_job.return_value = mock_job
        mock_batch_v1.patch_namespaced_job.return_value = mock_job
        job_manager.suspend_job("batch-job", "default")
        mock_batch_v1.patch_namespaced_job.assert_called_once()
