"""Unit tests for kube_orchestrator.rollback.snapshot."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kube_orchestrator.rollback.snapshot import DeploymentSnapshot, SnapshotStore


@pytest.fixture
def store(mock_kube_client: MagicMock) -> SnapshotStore:
    return SnapshotStore(client=mock_kube_client)


def _fake_deployment(
    name: str = "web",
    namespace: str = "default",
    revision: str = "3",
    image: str = "nginx:1.24",
) -> MagicMock:
    deploy = MagicMock()
    deploy.metadata.name = name
    deploy.metadata.namespace = namespace
    deploy.metadata.labels = {"app": name}
    deploy.metadata.annotations = {"deployment.kubernetes.io/revision": revision}
    deploy.spec.replicas = 2
    deploy.spec.selector.to_dict.return_value = {"matchLabels": {"app": name}}
    deploy.spec.template.to_dict.return_value = {"metadata": {}, "spec": {}}
    deploy.spec.template.spec.containers = [MagicMock(image=image)]
    return deploy


@pytest.mark.unit
class TestTakeSnapshot:
    def test_captures_manifest_and_metadata(
        self, store: SnapshotStore, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = (
            _fake_deployment()
        )

        snap = store.take_snapshot("web", "default")

        assert snap.name == "web"
        assert snap.namespace == "default"
        assert snap.revision == 3
        assert snap.manifest["spec"]["replicas"] == 2
        assert snap.metadata["image"] == "nginx:1.24"

    def test_defaults_revision_to_zero_when_missing_annotation(
        self, store: SnapshotStore, mock_kube_client: MagicMock
    ) -> None:
        deploy = _fake_deployment()
        deploy.metadata.annotations = {}
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        snap = store.take_snapshot("web", "default")
        assert snap.revision == 0

    def test_raises_when_metadata_missing(
        self, store: SnapshotStore, mock_kube_client: MagicMock
    ) -> None:
        deploy = MagicMock()
        deploy.metadata = None
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy
        with pytest.raises(ValueError, match="no metadata/spec"):
            store.take_snapshot("web", "default")

    def test_stores_snapshot_for_later_retrieval(
        self, store: SnapshotStore, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = (
            _fake_deployment()
        )
        store.take_snapshot("web", "default")
        assert len(store.list_snapshots("web", "default")) == 1

    def test_extract_image_returns_empty_on_missing_containers(
        self, store: SnapshotStore, mock_kube_client: MagicMock
    ) -> None:
        deploy = _fake_deployment()
        deploy.spec.template.spec.containers = []
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        snap = store.take_snapshot("web", "default")
        assert snap.metadata["image"] == ""


@pytest.mark.unit
class TestListGetDeleteSnapshots:
    def test_list_snapshots_empty_by_default(self, store: SnapshotStore) -> None:
        assert store.list_snapshots("web", "default") == []

    def test_get_snapshot_by_revision(
        self, store: SnapshotStore, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = (
            _fake_deployment(revision="1")
        )
        store.take_snapshot("web", "default")
        found = store.get_snapshot("web", "default", 1)
        assert found is not None
        assert found.revision == 1

    def test_get_snapshot_returns_none_when_not_found(
        self, store: SnapshotStore
    ) -> None:
        assert store.get_snapshot("web", "default", 99) is None

    def test_delete_snapshot_removes_matching_revision(
        self, store: SnapshotStore, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = (
            _fake_deployment(revision="1")
        )
        store.take_snapshot("web", "default")
        store.delete_snapshot("web", "default", 1)
        assert store.list_snapshots("web", "default") == []


@pytest.mark.unit
class TestCompareSnapshots:
    def test_reports_image_change(self) -> None:
        store = SnapshotStore(client=MagicMock())
        snap_a = DeploymentSnapshot(
            name="web",
            namespace="default",
            timestamp=datetime(2026, 1, 1),
            revision=1,
            manifest={},
            metadata={"image": "nginx:1.24"},
        )
        snap_b = DeploymentSnapshot(
            name="web",
            namespace="default",
            timestamp=datetime(2026, 1, 2),
            revision=2,
            manifest={},
            metadata={"image": "nginx:1.25"},
        )

        diff = store.compare_snapshots(snap_a, snap_b)

        assert diff["from_revision"] == 1
        assert diff["to_revision"] == 2
        assert diff["image_changed"] is True
        assert diff["from_image"] == "nginx:1.24"
        assert diff["to_image"] == "nginx:1.25"

    def test_no_change_when_images_match(self) -> None:
        store = SnapshotStore(client=MagicMock())
        snap_a = DeploymentSnapshot(
            name="web",
            namespace="default",
            timestamp=datetime(2026, 1, 1),
            revision=1,
            manifest={},
            metadata={"image": "nginx:1.24"},
        )
        snap_b = DeploymentSnapshot(
            name="web",
            namespace="default",
            timestamp=datetime(2026, 1, 2),
            revision=2,
            manifest={},
            metadata={"image": "nginx:1.24"},
        )
        assert store.compare_snapshots(snap_a, snap_b)["image_changed"] is False


@pytest.mark.unit
class TestExportImportSnapshot:
    def test_round_trips_through_json_file(
        self, store: SnapshotStore, tmp_path: Path
    ) -> None:
        snap = DeploymentSnapshot(
            name="web",
            namespace="default",
            timestamp=datetime(2026, 1, 1, 12, 0, 0),
            revision=2,
            manifest={"kind": "Deployment"},
            metadata={"image": "nginx:1.24"},
        )
        path = tmp_path / "nested" / "snap.json"

        store.export_snapshot(snap, str(path))
        loaded = store.import_snapshot(str(path))

        assert loaded.name == "web"
        assert loaded.revision == 2
        assert loaded.manifest == {"kind": "Deployment"}
        assert loaded.metadata == {"image": "nginx:1.24"}

    def test_export_without_directory_component(
        self, store: SnapshotStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        snap = DeploymentSnapshot(
            name="web",
            namespace="default",
            timestamp=datetime(2026, 1, 1),
            revision=1,
            manifest={},
        )
        store.export_snapshot(snap, "flat.json")
        assert (tmp_path / "flat.json").exists()
        content = json.loads((tmp_path / "flat.json").read_text())
        assert content["name"] == "web"

    def test_import_defaults_metadata_to_empty_dict(
        self, store: SnapshotStore, tmp_path: Path
    ) -> None:
        path = tmp_path / "snap.json"
        path.write_text(
            json.dumps(
                {
                    "name": "web",
                    "namespace": "default",
                    "timestamp": "2026-01-01T00:00:00",
                    "revision": 1,
                    "manifest": {},
                }
            )
        )
        loaded = store.import_snapshot(str(path))
        assert loaded.metadata == {}
