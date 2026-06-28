from __future__ import annotations

from datetime import datetime
from typing import Any

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.logging import get_logger
from kube_orchestrator.rollback.snapshot import DeploymentSnapshot, SnapshotStore


class AutoRollback:
    def __init__(
        self,
        client: KubeClient | None = None,
        snapshot_store: SnapshotStore | None = None,
    ) -> None:
        self._client = client or KubeClient.get_instance()
        self._snapshot_store = snapshot_store or SnapshotStore(self._client)
        self._logger = get_logger(__name__)
        self._history: list[dict[str, Any]] = []

    def trigger_rollback(
        self, deployment_name: str, namespace: str, reason: str
    ) -> None:
        self._logger.warning(
            "rollback_triggered",
            deployment=deployment_name,
            namespace=namespace,
            reason=reason,
        )
        snapshots = self._snapshot_store.list_snapshots(deployment_name, namespace)
        if not snapshots:
            try:
                deploy = self._client.apps_v1.read_namespaced_deployment(
                    deployment_name, namespace
                )
                revision = int(
                    (
                        (deploy.metadata.annotations if deploy.metadata else None) or {}
                    ).get("deployment.kubernetes.io/revision", "1")
                )
                if revision > 1:
                    self.rollback_to_revision(deployment_name, namespace, revision - 1)
            except Exception as exc:
                self._logger.error("trigger_rollback_failed", error=str(exc))
                self.log_recovery_event(deployment_name, namespace, reason, False)
                return
        else:
            last_good = (
                sorted(snapshots, key=lambda s: s.revision)[-2]
                if len(snapshots) >= 2
                else snapshots[-1]
            )
            self.rollback_to_snapshot(last_good)
        self.log_recovery_event(deployment_name, namespace, reason, True)

    def rollback_to_snapshot(self, snap: DeploymentSnapshot) -> None:
        self._logger.info(
            "rolling_back_to_snapshot",
            deployment=snap.name,
            revision=snap.revision,
        )
        try:
            self._client.apps_v1.replace_namespaced_deployment(
                snap.name,
                snap.namespace,
                snap.manifest,  # type: ignore[arg-type]  # dict body accepted at runtime
            )
        except Exception as exc:
            self._logger.error(
                "rollback_to_snapshot_failed",
                deployment=snap.name,
                error=str(exc),
            )
            raise

    def rollback_to_revision(
        self, deployment_name: str, namespace: str, revision: int
    ) -> None:
        self._logger.info(
            "rolling_back_to_revision",
            deployment=deployment_name,
            revision=revision,
        )
        try:
            replica_sets = self._client.apps_v1.list_namespaced_replica_set(
                namespace,
                label_selector=f"app={deployment_name}",
            )
            target_rs = None
            for rs in replica_sets.items:
                rs_revision = int(
                    ((rs.metadata.annotations if rs.metadata else None) or {}).get(
                        "deployment.kubernetes.io/revision", "0"
                    )
                )
                if rs_revision == revision:
                    target_rs = rs
                    break

            if target_rs is None:
                self._logger.warning(
                    "rollback_revision_not_found",
                    deployment=deployment_name,
                    revision=revision,
                )
                return

            patch: dict[str, Any] = {
                "spec": {
                    "template": (
                        dict(target_rs.spec.template.to_dict())
                        if target_rs.spec and target_rs.spec.template
                        else {}
                    )
                }
            }
            self._client.apps_v1.patch_namespaced_deployment(
                deployment_name, namespace, patch
            )
        except Exception as exc:
            self._logger.error(
                "rollback_to_revision_failed",
                deployment=deployment_name,
                revision=revision,
                error=str(exc),
            )
            raise

    def get_rollback_history(
        self, deployment_name: str, namespace: str
    ) -> list[dict[str, Any]]:
        return [
            entry
            for entry in self._history
            if entry["deployment"] == deployment_name
            and entry["namespace"] == namespace
        ]

    def log_recovery_event(
        self,
        deployment_name: str,
        namespace: str,
        reason: str,
        success: bool,
    ) -> None:
        entry: dict[str, Any] = {
            "deployment": deployment_name,
            "namespace": namespace,
            "reason": reason,
            "success": success,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._history.append(entry)
        level = "info" if success else "error"
        getattr(self._logger, level)(
            "recovery_event",
            deployment=deployment_name,
            success=success,
            reason=reason,
        )

        try:
            body: dict[str, Any] = {
                "apiVersion": "v1",
                "kind": "Event",
                "metadata": {
                    "name": f"rollback-{deployment_name}-{int(datetime.utcnow().timestamp())}",
                    "namespace": namespace,
                },
                "involvedObject": {
                    "kind": "Deployment",
                    "name": deployment_name,
                    "namespace": namespace,
                },
                "reason": "AutoRollback",
                "message": f"{'Success' if success else 'Failed'}: {reason}",
                "type": "Normal" if success else "Warning",
            }
            self._client.core_v1.create_namespaced_event(
                namespace,
                body,  # type: ignore[arg-type]  # dict body accepted at runtime
            )
        except Exception:
            pass
