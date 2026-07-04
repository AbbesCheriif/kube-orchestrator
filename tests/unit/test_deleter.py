"""Unit tests for kube_orchestrator.manifest.deleter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.manifest.deleter import ManifestDeleter


@pytest.fixture
def deleter(mock_kube_client: MagicMock) -> ManifestDeleter:
    return ManifestDeleter(client=mock_kube_client)


CONFIGMAP = {
    "apiVersion": "v1",
    "kind": "ConfigMap",
    "metadata": {"name": "cm", "namespace": "default"},
}


@pytest.mark.unit
class TestDeleteManifest:
    def test_returns_none_for_unknown_kind(self, deleter: ManifestDeleter) -> None:
        manifest = {"kind": "TotallyUnknown", "metadata": {"name": "x"}}
        assert deleter.delete_manifest(manifest) is None

    def test_dry_run_returns_message_without_deleting(
        self, mock_kube_client: MagicMock
    ) -> None:
        deleter = ManifestDeleter(client=mock_kube_client, dry_run=True)
        with patch("kube_orchestrator.manifest.deleter.route_by_kind") as mock_route:
            manager_cls = MagicMock()
            mock_route.return_value = manager_cls
            result = deleter.delete_manifest(CONFIGMAP)
        assert result == "(dry-run) would delete ConfigMap/cm"
        manager_cls.return_value.delete.assert_not_called()

    def test_deletes_and_returns_kind_slash_name(
        self, deleter: ManifestDeleter
    ) -> None:
        with patch("kube_orchestrator.manifest.deleter.route_by_kind") as mock_route:
            manager_cls = MagicMock()
            mock_route.return_value = manager_cls
            result = deleter.delete_manifest(CONFIGMAP, cascade=False, grace_period=0)
        assert result == "ConfigMap/cm"
        call_kwargs = manager_cls.return_value.delete.call_args.kwargs
        assert call_kwargs["propagation_policy"] == "Orphan"
        assert call_kwargs["grace_period_seconds"] == 0

    def test_uses_namespace_override(self, deleter: ManifestDeleter) -> None:
        with patch("kube_orchestrator.manifest.deleter.route_by_kind") as mock_route:
            manager_cls = MagicMock()
            mock_route.return_value = manager_cls
            deleter.delete_manifest(CONFIGMAP, namespace="other-ns")
        args = manager_cls.return_value.delete.call_args.args
        assert args[1] == "other-ns"

    def test_returns_none_when_delete_raises(self, deleter: ManifestDeleter) -> None:
        with patch("kube_orchestrator.manifest.deleter.route_by_kind") as mock_route:
            manager_cls = MagicMock()
            manager_cls.return_value.delete.side_effect = RuntimeError("boom")
            mock_route.return_value = manager_cls
            assert deleter.delete_manifest(CONFIGMAP) is None


@pytest.mark.unit
class TestDeleteFile:
    def test_deletes_in_reverse_dependency_order(
        self, deleter: ManifestDeleter
    ) -> None:
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "web"},
        }
        with (
            patch(
                "kube_orchestrator.manifest.deleter.load_file",
                return_value=[dict(CONFIGMAP), deployment],
            ),
            patch.object(
                deleter, "delete_manifest", side_effect=lambda m, *a, **k: m["kind"]
            ) as mock_delete,
        ):
            result = deleter.delete_file("manifests.yaml")

        # Deployment depends on ConfigMap, so it must be deleted first.
        assert result == ["Deployment", "ConfigMap"]
        assert mock_delete.call_count == 2

    def test_skips_none_results(self, deleter: ManifestDeleter) -> None:
        with (
            patch(
                "kube_orchestrator.manifest.deleter.load_file",
                return_value=[dict(CONFIGMAP)],
            ),
            patch.object(deleter, "delete_manifest", return_value=None),
        ):
            assert deleter.delete_file("manifests.yaml") == []


@pytest.mark.unit
class TestDeleteDirectory:
    def test_deletes_all_manifests_in_directory(self, deleter: ManifestDeleter) -> None:
        with (
            patch(
                "kube_orchestrator.manifest.deleter.load_directory",
                return_value=[dict(CONFIGMAP)],
            ),
            patch.object(deleter, "delete_manifest", return_value="ConfigMap/cm"),
        ):
            result = deleter.delete_directory("manifests/", recursive=True)
        assert result == ["ConfigMap/cm"]


@pytest.mark.unit
class TestDryRunDelete:
    def test_returns_deletion_plan(self, deleter: ManifestDeleter) -> None:
        with patch(
            "kube_orchestrator.manifest.deleter.load_file",
            return_value=[dict(CONFIGMAP)],
        ):
            plan = deleter.dry_run_delete("manifests.yaml")
        assert plan == [
            {
                "action": "delete",
                "kind": "ConfigMap",
                "name": "cm",
                "namespace": "default",
                "dry_run": True,
            }
        ]


@pytest.mark.unit
class TestDetectOrphans:
    def test_returns_orphan_descriptors(
        self, deleter: ManifestDeleter, mock_kube_client: MagicMock
    ) -> None:
        orphan = MagicMock()
        orphan.metadata.name = "web-abc123"
        with patch(
            "kube_orchestrator.resources.workloads.replicaset.ReplicaSetManager"
        ) as mock_mgr_cls:
            mock_mgr_cls.return_value.list_orphan_replicasets.return_value = [orphan]
            result = deleter.detect_orphans("default")
        assert result == [
            {"kind": "ReplicaSet", "name": "web-abc123", "namespace": "default"}
        ]

    def test_returns_empty_list_on_error(
        self, deleter: ManifestDeleter, mock_kube_client: MagicMock
    ) -> None:
        with patch(
            "kube_orchestrator.resources.workloads.replicaset.ReplicaSetManager"
        ) as mock_mgr_cls:
            mock_mgr_cls.return_value.list_orphan_replicasets.side_effect = (
                RuntimeError("boom")
            )
            assert deleter.detect_orphans("default") == []
