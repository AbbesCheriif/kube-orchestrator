from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.logging import get_logger


@dataclass
class DeploymentSnapshot:
    name: str
    namespace: str
    timestamp: datetime
    revision: int
    manifest: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class SnapshotStore:
    def __init__(self, client: KubeClient | None = None) -> None:
        self._client = client or KubeClient.get_instance()
        self._logger = get_logger(__name__)
        self._store: dict[str, list[DeploymentSnapshot]] = {}

    def _key(self, deployment_name: str, namespace: str) -> str:
        return f"{namespace}/{deployment_name}"

    def take_snapshot(self, deployment_name: str, namespace: str) -> DeploymentSnapshot:
        deploy = self._client.apps_v1().read_namespaced_deployment(
            deployment_name, namespace
        )
        revision = int(
            (deploy.metadata.annotations or {}).get(
                "deployment.kubernetes.io/revision", "0"
            )
        )
        manifest: dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": deploy.metadata.name,
                "namespace": deploy.metadata.namespace,
                "labels": deploy.metadata.labels,
                "annotations": deploy.metadata.annotations,
            },
            "spec": {
                "replicas": deploy.spec.replicas,
                "selector": deploy.spec.selector.to_dict() if deploy.spec.selector else {},
                "template": deploy.spec.template.to_dict() if deploy.spec.template else {},
            },
        }
        snap = DeploymentSnapshot(
            name=deployment_name,
            namespace=namespace,
            timestamp=datetime.utcnow(),
            revision=revision,
            manifest=manifest,
            metadata={"revision": revision, "image": self._extract_image(deploy)},
        )
        key = self._key(deployment_name, namespace)
        self._store.setdefault(key, []).append(snap)
        self._logger.info("snapshot_taken", deployment=deployment_name, revision=revision)
        return snap

    def list_snapshots(self, deployment_name: str, namespace: str) -> list[DeploymentSnapshot]:
        return list(self._store.get(self._key(deployment_name, namespace), []))

    def get_snapshot(
        self, deployment_name: str, namespace: str, revision: int
    ) -> DeploymentSnapshot | None:
        for snap in self._store.get(self._key(deployment_name, namespace), []):
            if snap.revision == revision:
                return snap
        return None

    def delete_snapshot(self, deployment_name: str, namespace: str, revision: int) -> None:
        key = self._key(deployment_name, namespace)
        self._store[key] = [
            s for s in self._store.get(key, []) if s.revision != revision
        ]

    def compare_snapshots(
        self, snap_a: DeploymentSnapshot, snap_b: DeploymentSnapshot
    ) -> dict:
        return {
            "from_revision": snap_a.revision,
            "to_revision": snap_b.revision,
            "from_timestamp": snap_a.timestamp.isoformat(),
            "to_timestamp": snap_b.timestamp.isoformat(),
            "image_changed": snap_a.metadata.get("image") != snap_b.metadata.get("image"),
            "from_image": snap_a.metadata.get("image"),
            "to_image": snap_b.metadata.get("image"),
        }

    def export_snapshot(self, snap: DeploymentSnapshot, path: str) -> None:
        data = {
            "name": snap.name,
            "namespace": snap.namespace,
            "timestamp": snap.timestamp.isoformat(),
            "revision": snap.revision,
            "manifest": snap.manifest,
            "metadata": snap.metadata,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        self._logger.info("snapshot_exported", path=path)

    def import_snapshot(self, path: str) -> DeploymentSnapshot:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return DeploymentSnapshot(
            name=data["name"],
            namespace=data["namespace"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            revision=data["revision"],
            manifest=data["manifest"],
            metadata=data.get("metadata", {}),
        )

    def _extract_image(self, deploy: Any) -> str:
        try:
            return deploy.spec.template.spec.containers[0].image or ""
        except (AttributeError, IndexError):
            return ""
