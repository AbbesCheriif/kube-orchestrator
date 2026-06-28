"""Unit tests for CronJobManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.workloads.cronjob import CronJobManager


@pytest.fixture
def cj_manager(mock_kube_client: MagicMock) -> CronJobManager:
    return CronJobManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestCronJobManager:
    def test_create_cronjob(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_batch_v1.create_namespaced_cron_job.return_value = MagicMock()
        cj_manager.create_cronjob(
            name="nightly-backup",
            namespace="default",
            schedule="0 2 * * *",
            job_template={
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [{"name": "backup", "image": "alpine"}],
                            "restartPolicy": "OnFailure",
                        }
                    }
                }
            },
            concurrency_policy="Forbid",
            successful_jobs_history_limit=3,
            failed_jobs_history_limit=1,
            suspend=False,
        )
        mock_batch_v1.create_namespaced_cron_job.assert_called_once()

    def test_update_schedule(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_cj = MagicMock()
        mock_batch_v1.read_namespaced_cron_job.return_value = mock_cj
        mock_batch_v1.patch_namespaced_cron_job.return_value = mock_cj
        cj_manager.update_schedule("nightly-backup", "default", "0 3 * * *")
        mock_batch_v1.patch_namespaced_cron_job.assert_called_once()

    def test_suspend_cronjob(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_cj = MagicMock()
        mock_batch_v1.read_namespaced_cron_job.return_value = mock_cj
        mock_batch_v1.patch_namespaced_cron_job.return_value = mock_cj
        cj_manager.suspend_cronjob("nightly-backup", "default")
        mock_batch_v1.patch_namespaced_cron_job.assert_called_once()
