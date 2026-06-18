from __future__ import annotations

import threading
from typing import Callable

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.logging import get_logger


class RolloutDetector:
    def __init__(self, client: KubeClient | None = None) -> None:
        self._client = client or KubeClient.get_instance()
        self._logger = get_logger(__name__)

    def detect_failed_rollout(self, deployment_name: str, namespace: str) -> bool:
        try:
            deploy = self._client.apps_v1.read_namespaced_deployment(
                deployment_name, namespace
            )
            for cond in (deploy.status.conditions or []):
                if cond.type == "Progressing" and cond.reason == "ProgressDeadlineExceeded":
                    return True
            desired = deploy.spec.replicas or 1
            updated = deploy.status.updated_replicas or 0
            available = deploy.status.available_replicas or 0
            if updated < desired or available < desired:
                unavailable = deploy.status.unavailable_replicas or 0
                if unavailable > 0:
                    return True
        except Exception as exc:
            self._logger.error(
                "detect_failed_rollout_error",
                deployment=deployment_name,
                error=str(exc),
            )
        return False

    def get_failure_reason(self, deployment_name: str, namespace: str) -> str | None:
        try:
            deploy = self._client.apps_v1.read_namespaced_deployment(
                deployment_name, namespace
            )
            for cond in (deploy.status.conditions or []):
                if cond.type == "Progressing" and cond.status == "False":
                    return cond.message
                if cond.type == "Available" and cond.status == "False":
                    return cond.message
        except Exception as exc:
            self._logger.error(
                "get_failure_reason_error",
                deployment=deployment_name,
                error=str(exc),
            )
        return None

    def is_rollout_stuck(
        self, deployment_name: str, namespace: str, timeout_seconds: int = 300
    ) -> bool:
        try:
            deploy = self._client.apps_v1.read_namespaced_deployment(
                deployment_name, namespace
            )
            for cond in (deploy.status.conditions or []):
                if cond.type == "Progressing" and cond.reason == "ProgressDeadlineExceeded":
                    return True
            observed = deploy.status.observed_generation or 0
            generation = deploy.metadata.generation or 0
            if observed < generation:
                return True
        except Exception as exc:
            self._logger.error(
                "is_rollout_stuck_error",
                deployment=deployment_name,
                error=str(exc),
            )
        return False

    def check_pod_errors(self, deployment_name: str, namespace: str) -> list[dict]:
        errors: list[dict] = []
        try:
            deploy = self._client.apps_v1.read_namespaced_deployment(
                deployment_name, namespace
            )
            selector = deploy.spec.selector
            if not selector or not selector.match_labels:
                return errors
            label_str = ",".join(
                f"{k}={v}" for k, v in selector.match_labels.items()
            )
            pods = self._client.core_v1.list_namespaced_pod(
                namespace, label_selector=label_str
            )
            for pod in pods.items:
                for cs in (pod.status.container_statuses or []):
                    if cs.state and cs.state.waiting:
                        waiting = cs.state.waiting
                        if waiting.reason in (
                            "CrashLoopBackOff",
                            "ImagePullBackOff",
                            "ErrImagePull",
                            "OOMKilled",
                        ):
                            errors.append(
                                {
                                    "pod": pod.metadata.name,
                                    "container": cs.name,
                                    "reason": waiting.reason,
                                    "message": waiting.message or "",
                                }
                            )
        except Exception as exc:
            self._logger.error(
                "check_pod_errors_failed",
                deployment=deployment_name,
                error=str(exc),
            )
        return errors

    def watch_and_detect(
        self,
        deployment_name: str,
        namespace: str,
        callback: Callable[[str, str], None],
    ) -> None:
        from kubernetes import watch as k8s_watch

        w = k8s_watch.Watch()

        def _run() -> None:
            try:
                for event in w.stream(
                    self._client.apps_v1.list_namespaced_deployment,
                    namespace=namespace,
                    field_selector=f"metadata.name={deployment_name}",
                ):
                    deploy = event["object"]
                    event_type: str = event["type"]
                    if event_type in ("ADDED", "MODIFIED"):
                        for cond in (deploy.status.conditions or []):
                            if (
                                cond.type == "Progressing"
                                and cond.reason == "ProgressDeadlineExceeded"
                            ):
                                callback(deployment_name, namespace)
                                w.stop()
                                return
            except Exception as exc:
                self._logger.error("watch_and_detect_error", error=str(exc))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
