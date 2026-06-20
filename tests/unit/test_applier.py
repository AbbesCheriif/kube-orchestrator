"""Unit tests for ManifestApplier."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.manifest.applier import ManifestApplier


@pytest.fixture
def applier(mock_kube_client: MagicMock) -> ManifestApplier:
    return ManifestApplier(client=mock_kube_client, dry_run=False, force=False, server_side=False)


@pytest.fixture
def dry_run_applier(mock_kube_client: MagicMock) -> ManifestApplier:
    return ManifestApplier(client=mock_kube_client, dry_run=True, force=False, server_side=False)


@pytest.mark.unit
class TestDecideAction:
    def test_create_when_no_live(self, applier: ManifestApplier) -> None:
        desired = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "p"}}
        action = applier.decide_action(live=None, desired=desired)
        assert action == "create"

    def test_update_when_live_differs(self, applier: ManifestApplier) -> None:
        live = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "p"}, "spec": {"replicas": 1}}
        desired = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "p"}, "spec": {"replicas": 3}}
        action = applier.decide_action(live=live, desired=desired)
        assert action in ("update", "replace")

    def test_skip_when_identical(self, applier: ManifestApplier) -> None:
        manifest = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "p"}, "spec": {}}
        action = applier.decide_action(live=manifest, desired=manifest)
        assert action == "skip"


@pytest.mark.unit
class TestComputeDiff:
    def test_diff_detects_changes(self, applier: ManifestApplier) -> None:
        current = {"spec": {"replicas": 1}}
        desired = {"spec": {"replicas": 3}}
        diff = applier.compute_diff(current, desired)
        assert diff != {}

    def test_diff_empty_when_identical(self, applier: ManifestApplier) -> None:
        manifest = {"spec": {"replicas": 1}}
        diff = applier.compute_diff(manifest, manifest)
        assert diff == {}


@pytest.mark.unit
class TestDryRunApply:
    def test_dry_run_does_not_call_api(self, dry_run_applier: ManifestApplier) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "test-cm", "namespace": "default"},
            "data": {"key": "value"},
        }
        with patch.object(dry_run_applier, "get_live_resource", return_value=None):
            result = dry_run_applier.apply_manifest(manifest, namespace="default")
        assert result.get("action") == "create"
        assert result.get("dry_run") is True
