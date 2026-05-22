"""JobManager — full lifecycle management for Kubernetes Jobs."""

from __future__ import annotations

import time
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import ResourceNotFoundError, parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager


class JobManager(BaseResourceManager[client.V1Job]):
    """Full lifecycle manager for Kubernetes Jobs."""

    def __init__(
        self,
        kube_client: KubeClient,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        super().__init__(kube_client, default_namespace, dry_run)

    def _get_api(self) -> client.BatchV1Api:
        return self.client.batch_v1

    def _kind(self) -> str:
        return "Job"

    def _api_version(self) -> str:
        return "batch/v1"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_job(
        self,
        name: str,
        namespace: str | None = None,
        pod_template: dict | None = None,
        completions: int | None = None,
        parallelism: int | None = None,
        backoff_limit: int = 6,
        active_deadline_seconds: int | None = None,
        ttl_seconds_after_finished: int | None = None,
        completion_mode: str | None = None,
        suspend: bool = False,
        manual_selector: bool = False,
        pod_failure_policy: dict | None = None,
        labels: dict[str, str] | None = None,
    ) -> client.V1Job:
        ns = namespace or self.default_namespace
        metadata: dict[str, Any] = {"name": name, "namespace": ns}
        if labels:
            metadata["labels"] = labels

        spec: dict[str, Any] = {
            "template": pod_template or {},
            "backoffLimit": backoff_limit,
            "suspend": suspend,
            "manualSelector": manual_selector,
        }
        if completions is not None:
            spec["completions"] = completions
        if parallelism is not None:
            spec["parallelism"] = parallelism
        if active_deadline_seconds is not None:
            spec["activeDeadlineSeconds"] = active_deadline_seconds
        if ttl_seconds_after_finished is not None:
            spec["ttlSecondsAfterFinished"] = ttl_seconds_after_finished
        if completion_mode is not None:
            spec["completionMode"] = completion_mode
        if pod_failure_policy is not None:
            spec["podFailurePolicy"] = pod_failure_policy

        manifest: dict[str, Any] = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": metadata,
            "spec": spec,
        }
        return self.create(manifest, ns)

    def get_job(self, name: str, namespace: str | None = None) -> client.V1Job:
        return self.get(name, namespace)

    def list_jobs(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> list[client.V1Job]:
        return self.list(namespace, label_selector)

    def delete_job(
        self,
        name: str,
        namespace: str | None = None,
        propagation_policy: str = "Background",
    ) -> None:
        self.delete(name, namespace, propagation_policy=propagation_policy)

    # ------------------------------------------------------------------
    # Suspend / Resume
    # ------------------------------------------------------------------

    def suspend_job(
        self, name: str, namespace: str | None = None
    ) -> client.V1Job:
        patch: dict[str, Any] = {"spec": {"suspend": True}}
        return self.patch(name, patch, namespace, "merge")

    def resume_job(
        self, name: str, namespace: str | None = None
    ) -> client.V1Job:
        patch: dict[str, Any] = {"spec": {"suspend": False}}
        return self.patch(name, patch, namespace, "merge")

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_status(self, name: str, namespace: str | None = None) -> dict:
        job = self.get_job(name, namespace)
        status = job.status
        return {
            "active": (status.active or 0) if status else 0,
            "succeeded": (status.succeeded or 0) if status else 0,
            "failed": (status.failed or 0) if status else 0,
            "ready": (status.ready or 0) if status else 0,
            "start_time": str(status.start_time) if status and status.start_time else None,
            "completion_time": str(status.completion_time) if status and status.completion_time else None,
            "conditions": [
                c.to_dict() if hasattr(c, "to_dict") else c
                for c in (status.conditions or [])
            ] if status else [],
        }

    def get_active_count(self, name: str, namespace: str | None = None) -> int:
        job = self.get_job(name, namespace)
        return (job.status.active or 0) if job.status else 0

    def get_succeeded_count(self, name: str, namespace: str | None = None) -> int:
        job = self.get_job(name, namespace)
        return (job.status.succeeded or 0) if job.status else 0

    def get_failed_count(self, name: str, namespace: str | None = None) -> int:
        job = self.get_job(name, namespace)
        return (job.status.failed or 0) if job.status else 0

    def is_complete(self, name: str, namespace: str | None = None) -> bool:
        job = self.get_job(name, namespace)
        if not job.status or not job.status.conditions:
            return False
        return any(
            c.type == "Complete" and c.status == "True"
            for c in job.status.conditions
        )

    def is_failed(self, name: str, namespace: str | None = None) -> bool:
        job = self.get_job(name, namespace)
        if not job.status or not job.status.conditions:
            return False
        return any(
            c.type == "Failed" and c.status == "True"
            for c in job.status.conditions
        )

    def get_pods(
        self, name: str, namespace: str | None = None
    ) -> list[client.V1Pod]:
        ns = namespace or self.default_namespace
        job = self.get_job(name, ns)
        match_labels = (
            job.spec.selector.match_labels
            if job.spec and job.spec.selector
            else {}
        )
        label_selector = ",".join(
            f"{k}={v}" for k, v in (match_labels or {}).items()
        )
        try:
            result = self.client.core_v1.list_namespaced_pod(
                namespace=ns, label_selector=label_selector
            )
        except ApiException as exc:
            raise parse_api_exception(exc) from exc
        return result.items

    # ------------------------------------------------------------------
    # Wait
    # ------------------------------------------------------------------

    def wait_for_completion(
        self,
        name: str,
        namespace: str | None = None,
        timeout_seconds: int = 600,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                if self.is_complete(name, namespace):
                    return True
                if self.is_failed(name, namespace):
                    return False
            except ResourceNotFoundError:
                pass
            time.sleep(5)
        return False
