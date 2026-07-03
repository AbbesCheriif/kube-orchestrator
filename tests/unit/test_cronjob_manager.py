"""Unit tests for CronJobManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from kubernetes.client.exceptions import ApiException

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

    def test_create_cronjob_with_optional_fields(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj_manager.create_cronjob(
            "nightly-backup",
            "default",
            starting_deadline_seconds=120,
            time_zone="UTC",
            labels={"app": "backup"},
        )
        call_kwargs = mock_batch_v1.create_namespaced_cron_job.call_args.kwargs
        spec = call_kwargs["body"]["spec"]
        assert spec["startingDeadlineSeconds"] == 120
        assert spec["timeZone"] == "UTC"

    def test_get_cronjob(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_batch_v1.read_namespaced_cron_job.return_value = "cj-obj"
        assert cj_manager.get_cronjob("nightly-backup", "default") == "cj-obj"

    def test_list_cronjobs(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        mock_batch_v1.list_namespaced_cron_job.return_value.items = ["a"]
        assert cj_manager.list_cronjobs("default") == ["a"]

    def test_delete_cronjob(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj_manager.delete_cronjob("nightly-backup", "default")
        mock_batch_v1.delete_namespaced_cron_job.assert_called_once()

    def test_resume_cronjob(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj_manager.resume_cronjob("nightly-backup", "default")
        call_kwargs = mock_batch_v1.patch_namespaced_cron_job.call_args.kwargs
        assert call_kwargs["body"]["spec"]["suspend"] is False

    def test_kind_and_api_version(self, cj_manager: CronJobManager) -> None:
        assert cj_manager._kind() == "CronJob"
        assert cj_manager._api_version() == "batch/v1"
        assert cj_manager._resource_name() == "cron_job"


@pytest.mark.unit
class TestTriggerNow:
    def test_creates_manual_job_from_template(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj = MagicMock()
        cj.spec.job_template.to_dict.return_value = {
            "spec": {"template": {"spec": {"containers": []}}}
        }
        cj.metadata.uid = "uid-123"
        mock_batch_v1.read_namespaced_cron_job.return_value = cj
        mock_batch_v1.create_namespaced_job.return_value = MagicMock()

        cj_manager.trigger_now("nightly-backup", "default")

        call_kwargs = mock_batch_v1.create_namespaced_job.call_args.kwargs
        manifest = call_kwargs["body"]
        assert manifest["metadata"]["ownerReferences"][0]["name"] == "nightly-backup"
        assert manifest["metadata"]["ownerReferences"][0]["uid"] == "uid-123"

    def test_creates_job_without_job_template(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj = MagicMock()
        cj.spec.job_template = None
        mock_batch_v1.read_namespaced_cron_job.return_value = cj
        mock_batch_v1.create_namespaced_job.return_value = MagicMock()

        cj_manager.trigger_now("nightly-backup", "default")

        mock_batch_v1.create_namespaced_job.assert_called_once()

    def test_raises_parsed_exception(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj = MagicMock()
        cj.spec.job_template.to_dict.return_value = {"spec": {}}
        mock_batch_v1.read_namespaced_cron_job.return_value = cj
        mock_batch_v1.create_namespaced_job.side_effect = ApiException(status=500)
        with pytest.raises(Exception):
            cj_manager.trigger_now("nightly-backup", "default")


@pytest.mark.unit
class TestActiveJobsAndScheduleTime:
    def test_get_active_jobs(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        ref = MagicMock()
        ref.name = "nightly-backup-abc"
        cj = MagicMock()
        cj.status.active = [ref]
        mock_batch_v1.read_namespaced_cron_job.return_value = cj
        mock_batch_v1.read_namespaced_job.return_value = "job-obj"

        result = cj_manager.get_active_jobs("nightly-backup", "default")
        assert result == ["job-obj"]

    def test_get_active_jobs_skips_refs_without_name(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        ref = MagicMock()
        ref.name = None
        cj = MagicMock()
        cj.status.active = [ref]
        mock_batch_v1.read_namespaced_cron_job.return_value = cj

        result = cj_manager.get_active_jobs("nightly-backup", "default")
        assert result == []

    def test_get_active_jobs_swallows_read_errors(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        ref = MagicMock()
        ref.name = "nightly-backup-abc"
        cj = MagicMock()
        cj.status.active = [ref]
        mock_batch_v1.read_namespaced_cron_job.return_value = cj
        mock_batch_v1.read_namespaced_job.side_effect = ApiException(status=404)

        result = cj_manager.get_active_jobs("nightly-backup", "default")
        assert result == []

    def test_get_active_jobs_returns_empty_without_status(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj = MagicMock(status=None)
        mock_batch_v1.read_namespaced_cron_job.return_value = cj
        assert cj_manager.get_active_jobs("nightly-backup", "default") == []

    def test_get_last_schedule_time(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj = MagicMock()
        cj.status.last_schedule_time = "2026-01-01T00:00:00Z"
        mock_batch_v1.read_namespaced_cron_job.return_value = cj
        assert (
            cj_manager.get_last_schedule_time("nightly-backup", "default")
            == "2026-01-01T00:00:00Z"
        )

    def test_get_last_schedule_time_none_without_status(
        self, cj_manager: CronJobManager, mock_batch_v1: MagicMock
    ) -> None:
        cj = MagicMock(status=None)
        mock_batch_v1.read_namespaced_cron_job.return_value = cj
        assert cj_manager.get_last_schedule_time("nightly-backup", "default") is None
