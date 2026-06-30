"""Unit tests for kube_orchestrator.rollback.auto_rollback."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.rollback.auto_rollback import AutoRollback
from kube_orchestrator.rollback.snapshot import DeploymentSnapshot


@pytest.fixture
def snapshot_store() -> MagicMock:
    return MagicMock()


@pytest.fixture
def auto_rollback(
    mock_kube_client: MagicMock, snapshot_store: MagicMock
) -> AutoRollback:
    return AutoRollback(client=mock_kube_client, snapshot_store=snapshot_store)


def _snapshot(revision: int) -> DeploymentSnapshot:
    return DeploymentSnapshot(
        name="web",
        namespace="default",
        timestamp=datetime(2026, 1, 1),
        revision=revision,
        manifest={"kind": "Deployment"},
    )


@pytest.mark.unit
class TestTriggerRollback:
    def test_no_snapshots_rolls_back_to_previous_revision(
        self,
        auto_rollback: AutoRollback,
        mock_kube_client: MagicMock,
        snapshot_store: MagicMock,
    ) -> None:
        snapshot_store.list_snapshots.return_value = []
        deploy = MagicMock()
        deploy.metadata.annotations = {"deployment.kubernetes.io/revision": "3"}
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        with patch.object(auto_rollback, "rollback_to_revision") as rollback:
            auto_rollback.trigger_rollback("web", "default", "crash loop")
            rollback.assert_called_once_with("web", "default", 2)

        history = auto_rollback.get_rollback_history("web", "default")
        assert len(history) == 1
        assert history[0]["success"] is True

    def test_no_snapshots_revision_one_skips_rollback(
        self,
        auto_rollback: AutoRollback,
        mock_kube_client: MagicMock,
        snapshot_store: MagicMock,
    ) -> None:
        snapshot_store.list_snapshots.return_value = []
        deploy = MagicMock()
        deploy.metadata.annotations = {"deployment.kubernetes.io/revision": "1"}
        mock_kube_client.apps_v1.read_namespaced_deployment.return_value = deploy

        with patch.object(auto_rollback, "rollback_to_revision") as rollback:
            auto_rollback.trigger_rollback("web", "default", "crash loop")
            rollback.assert_not_called()

        assert auto_rollback.get_rollback_history("web", "default")[0]["success"] is True

    def test_read_failure_logs_failure_and_returns_early(
        self,
        auto_rollback: AutoRollback,
        mock_kube_client: MagicMock,
        snapshot_store: MagicMock,
    ) -> None:
        snapshot_store.list_snapshots.return_value = []
        mock_kube_client.apps_v1.read_namespaced_deployment.side_effect = RuntimeError(
            "not found"
        )

        auto_rollback.trigger_rollback("web", "default", "crash loop")

        history = auto_rollback.get_rollback_history("web", "default")
        assert len(history) == 1
        assert history[0]["success"] is False

    def test_with_multiple_snapshots_uses_second_to_last(
        self, auto_rollback: AutoRollback, snapshot_store: MagicMock
    ) -> None:
        snaps = [_snapshot(1), _snapshot(3), _snapshot(2)]
        snapshot_store.list_snapshots.return_value = snaps

        with patch.object(auto_rollback, "rollback_to_snapshot") as rollback:
            auto_rollback.trigger_rollback("web", "default", "crash loop")
            used = rollback.call_args.args[0]
            assert used.revision == 2

    def test_with_single_snapshot_uses_it(
        self, auto_rollback: AutoRollback, snapshot_store: MagicMock
    ) -> None:
        snapshot_store.list_snapshots.return_value = [_snapshot(5)]

        with patch.object(auto_rollback, "rollback_to_snapshot") as rollback:
            auto_rollback.trigger_rollback("web", "default", "crash loop")
            assert rollback.call_args.args[0].revision == 5


@pytest.mark.unit
class TestRollbackToSnapshot:
    def test_replaces_deployment(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        snap = _snapshot(2)
        auto_rollback.rollback_to_snapshot(snap)
        mock_kube_client.apps_v1.replace_namespaced_deployment.assert_called_once_with(
            "web", "default", {"kind": "Deployment"}
        )

    def test_reraises_on_failure(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.replace_namespaced_deployment.side_effect = (
            RuntimeError("conflict")
        )
        with pytest.raises(RuntimeError, match="conflict"):
            auto_rollback.rollback_to_snapshot(_snapshot(2))


@pytest.mark.unit
class TestRollbackToRevision:
    def test_patches_deployment_with_matching_replicaset_template(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        rs = MagicMock()
        rs.metadata.annotations = {"deployment.kubernetes.io/revision": "2"}
        rs.spec.template.to_dict.return_value = {"metadata": {}, "spec": {}}
        mock_kube_client.apps_v1.list_namespaced_replica_set.return_value.items = [rs]

        auto_rollback.rollback_to_revision("web", "default", 2)

        mock_kube_client.apps_v1.patch_namespaced_deployment.assert_called_once_with(
            "web",
            "default",
            {"spec": {"template": {"metadata": {}, "spec": {}}}},
        )

    def test_no_matching_replicaset_logs_and_returns(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        rs = MagicMock()
        rs.metadata.annotations = {"deployment.kubernetes.io/revision": "1"}
        mock_kube_client.apps_v1.list_namespaced_replica_set.return_value.items = [rs]

        auto_rollback.rollback_to_revision("web", "default", 2)

        mock_kube_client.apps_v1.patch_namespaced_deployment.assert_not_called()

    def test_reraises_on_list_failure(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.apps_v1.list_namespaced_replica_set.side_effect = (
            RuntimeError("boom")
        )
        with pytest.raises(RuntimeError, match="boom"):
            auto_rollback.rollback_to_revision("web", "default", 2)

    def test_empty_template_when_replicaset_has_no_spec(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        rs = MagicMock()
        rs.metadata.annotations = {"deployment.kubernetes.io/revision": "2"}
        rs.spec = None
        mock_kube_client.apps_v1.list_namespaced_replica_set.return_value.items = [rs]

        auto_rollback.rollback_to_revision("web", "default", 2)

        mock_kube_client.apps_v1.patch_namespaced_deployment.assert_called_once_with(
            "web", "default", {"spec": {"template": {}}}
        )


@pytest.mark.unit
class TestGetRollbackHistory:
    def test_filters_by_deployment_and_namespace(
        self, auto_rollback: AutoRollback
    ) -> None:
        auto_rollback.log_recovery_event("web", "default", "reason a", True)
        auto_rollback.log_recovery_event("other", "default", "reason b", True)
        history = auto_rollback.get_rollback_history("web", "default")
        assert len(history) == 1
        assert history[0]["reason"] == "reason a"


@pytest.mark.unit
class TestLogRecoveryEvent:
    def test_success_creates_normal_event(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        auto_rollback.log_recovery_event("web", "default", "healed", True)
        mock_kube_client.core_v1.create_namespaced_event.assert_called_once()
        body = mock_kube_client.core_v1.create_namespaced_event.call_args.args[1]
        assert body["type"] == "Normal"

    def test_failure_creates_warning_event(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        auto_rollback.log_recovery_event("web", "default", "still broken", False)
        body = mock_kube_client.core_v1.create_namespaced_event.call_args.args[1]
        assert body["type"] == "Warning"

    def test_swallows_event_creation_errors(
        self, auto_rollback: AutoRollback, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.core_v1.create_namespaced_event.side_effect = RuntimeError(
            "no events api"
        )
        auto_rollback.log_recovery_event("web", "default", "healed", True)
        assert len(auto_rollback.get_rollback_history("web", "default")) == 1
