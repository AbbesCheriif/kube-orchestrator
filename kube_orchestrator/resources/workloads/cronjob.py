"""CronJobManager — full lifecycle management for Kubernetes CronJobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager


class CronJobManager(BaseResourceManager[client.V1CronJob]):
    """Full lifecycle manager for Kubernetes CronJobs."""

    def __init__(
        self,
        kube_client: "KubeClient | None" = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.BatchV1Api:
        return self.client.batch_v1

    def _kind(self) -> str:
        return "CronJob"

    def _api_version(self) -> str:
        return "batch/v1"

    def _resource_name(self) -> str:
        return "cron_job"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_cronjob(
        self,
        name: str,
        namespace: str | None = None,
        schedule: str = "*/1 * * * *",
        job_template: dict | None = None,
        concurrency_policy: str = "Allow",
        starting_deadline_seconds: int | None = None,
        successful_jobs_history_limit: int = 3,
        failed_jobs_history_limit: int = 1,
        suspend: bool = False,
        time_zone: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> client.V1CronJob:
        ns = namespace or self.default_namespace
        metadata: dict[str, Any] = {"name": name, "namespace": ns}
        if labels:
            metadata["labels"] = labels

        spec: dict[str, Any] = {
            "schedule": schedule,
            "jobTemplate": job_template or {},
            "concurrencyPolicy": concurrency_policy,
            "successfulJobsHistoryLimit": successful_jobs_history_limit,
            "failedJobsHistoryLimit": failed_jobs_history_limit,
            "suspend": suspend,
        }
        if starting_deadline_seconds is not None:
            spec["startingDeadlineSeconds"] = starting_deadline_seconds
        if time_zone is not None:
            spec["timeZone"] = time_zone

        manifest: dict[str, Any] = {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": metadata,
            "spec": spec,
        }
        return self.create(manifest, ns)

    def get_cronjob(
        self, name: str, namespace: str | None = None
    ) -> client.V1CronJob:
        return self.get(name, namespace)

    def list_cronjobs(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1CronJob]:
        return self.list(namespace, label_selector)

    def delete_cronjob(
        self,
        name: str,
        namespace: str | None = None,
        propagation_policy: str = "Background",
    ) -> None:
        self.delete(name, namespace, propagation_policy=propagation_policy)

    # ------------------------------------------------------------------
    # Schedule mutation
    # ------------------------------------------------------------------

    def update_schedule(
        self, name: str, namespace: str | None = None, schedule: str = ""
    ) -> client.V1CronJob:
        patch: dict[str, Any] = {"spec": {"schedule": schedule}}
        return self.patch(name, patch, namespace, "merge")

    # ------------------------------------------------------------------
    # Suspend / Resume
    # ------------------------------------------------------------------

    def suspend_cronjob(
        self, name: str, namespace: str | None = None
    ) -> client.V1CronJob:
        patch: dict[str, Any] = {"spec": {"suspend": True}}
        return self.patch(name, patch, namespace, "merge")

    def resume_cronjob(
        self, name: str, namespace: str | None = None
    ) -> client.V1CronJob:
        patch: dict[str, Any] = {"spec": {"suspend": False}}
        return self.patch(name, patch, namespace, "merge")

    # ------------------------------------------------------------------
    # Trigger / Active jobs
    # ------------------------------------------------------------------

    def trigger_now(
        self, name: str, namespace: str | None = None
    ) -> client.V1Job:
        """Manually trigger a CronJob by creating a Job from its template."""
        ns = namespace or self.default_namespace
        cj = self.get_cronjob(name, ns)

        job_template = (
            cj.spec.job_template.to_dict()
            if cj.spec and cj.spec.job_template and hasattr(cj.spec.job_template, "to_dict")
            else {}
        )
        spec = job_template.get("spec", {})

        job_name = f"{name}-manual-{uuid.uuid4().hex[:8]}"
        job_manifest: dict[str, Any] = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": ns,
                "annotations": {
                    "cronjob.kubernetes.io/instantiate": "manual",
                },
                "ownerReferences": [
                    {
                        "apiVersion": "batch/v1",
                        "kind": "CronJob",
                        "name": name,
                        "uid": cj.metadata.uid if cj.metadata else "",
                        "blockOwnerDeletion": True,
                        "controller": True,
                    }
                ],
            },
            "spec": spec,
        }

        try:
            return self.client.batch_v1.create_namespaced_job(
                namespace=ns, body=job_manifest
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def get_active_jobs(
        self, name: str, namespace: str | None = None
    ) -> list[client.V1Job]:
        ns = namespace or self.default_namespace
        cj = self.get_cronjob(name, ns)
        active_refs = (
            cj.status.active if cj.status and cj.status.active else []
        )
        jobs: list[client.V1Job] = []
        for ref in active_refs:
            try:
                job = self.client.batch_v1.read_namespaced_job(
                    name=ref.name, namespace=ns
                )
                jobs.append(job)
            except ApiException:
                pass
        return jobs

    def get_last_schedule_time(
        self, name: str, namespace: str | None = None
    ) -> str | None:
        cj = self.get_cronjob(name, namespace)
        if cj.status and cj.status.last_schedule_time:
            return str(cj.status.last_schedule_time)
        return None
