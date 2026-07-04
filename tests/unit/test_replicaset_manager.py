"""Unit tests for ReplicaSetManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError
from kube_orchestrator.resources.workloads.replicaset import ReplicaSetManager


@pytest.fixture
def rs_manager(mock_kube_client: MagicMock) -> ReplicaSetManager:
    return ReplicaSetManager(kube_client=mock_kube_client)


def _owned_rs(owner_kind: str = "Deployment", owner_name: str = "web") -> MagicMock:
    ref = MagicMock(kind=owner_kind)
    ref.name = owner_name
    rs = MagicMock()
    rs.metadata.owner_references = [ref]
    return rs


@pytest.mark.unit
class TestCreateGetListDelete:
    def test_create_replicaset_minimal(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs_manager.create_replicaset("web-rs", "default")
        call_kwargs = mock_apps_v1.create_namespaced_replica_set.call_args.kwargs
        assert call_kwargs["body"]["spec"]["replicas"] == 1

    def test_create_replicaset_with_all_fields(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs_manager.create_replicaset(
            "web-rs",
            "default",
            replicas=3,
            selector={"matchLabels": {"app": "web"}},
            pod_template={"spec": {}},
            min_ready_seconds=5,
            labels={"app": "web"},
        )
        call_kwargs = mock_apps_v1.create_namespaced_replica_set.call_args.kwargs
        spec = call_kwargs["body"]["spec"]
        assert spec["replicas"] == 3
        assert spec["minReadySeconds"] == 5
        assert call_kwargs["body"]["metadata"]["labels"] == {"app": "web"}

    def test_get_replicaset(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.read_namespaced_replica_set.return_value = "rs-obj"
        assert rs_manager.get_replicaset("web-rs", "default") == "rs-obj"

    def test_list_replicasets(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.list_namespaced_replica_set.return_value.items = ["a"]
        assert rs_manager.list_replicasets("default") == ["a"]

    def test_delete_replicaset(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs_manager.delete_replicaset("web-rs", "default")
        mock_apps_v1.delete_namespaced_replica_set.assert_called_once()

    def test_kind_and_api_version(self, rs_manager: ReplicaSetManager) -> None:
        assert rs_manager._kind() == "ReplicaSet"
        assert rs_manager._api_version() == "apps/v1"
        assert rs_manager._resource_name() == "replica_set"


@pytest.mark.unit
class TestScale:
    def test_scale_replicas(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs_manager.scale_replicas("web-rs", "default", replicas=5)
        mock_apps_v1.patch_namespaced_replica_set_scale.assert_called_once()

    def test_scale_replicas_raises_parsed_exception(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.patch_namespaced_replica_set_scale.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            rs_manager.scale_replicas("web-rs", "default", replicas=5)


@pytest.mark.unit
class TestRelatedResources:
    def test_get_pods(
        self,
        rs_manager: ReplicaSetManager,
        mock_apps_v1: MagicMock,
        mock_core_v1: MagicMock,
    ) -> None:
        rs = MagicMock()
        rs.spec.selector.match_labels = {"app": "web"}
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        mock_core_v1.list_namespaced_pod.return_value.items = ["pod-a"]

        assert rs_manager.get_pods("web-rs", "default") == ["pod-a"]

    def test_get_pods_raises_parsed_exception(
        self,
        rs_manager: ReplicaSetManager,
        mock_apps_v1: MagicMock,
        mock_core_v1: MagicMock,
    ) -> None:
        rs = MagicMock()
        rs.spec.selector.match_labels = {"app": "web"}
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        mock_core_v1.list_namespaced_pod.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            rs_manager.get_pods("web-rs", "default")

    def test_get_owner_deployment_found(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = _owned_rs()
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        mock_apps_v1.read_namespaced_deployment.return_value = "dep-obj"

        assert rs_manager.get_owner_deployment("web-rs", "default") == "dep-obj"

    def test_get_owner_deployment_none_without_metadata(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = MagicMock()
        rs.metadata = None
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        assert rs_manager.get_owner_deployment("web-rs", "default") is None

    def test_get_owner_deployment_none_without_deployment_ref(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = _owned_rs(owner_kind="ReplicationController")
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        assert rs_manager.get_owner_deployment("web-rs", "default") is None

    def test_get_owner_deployment_none_when_read_fails(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = _owned_rs()
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        mock_apps_v1.read_namespaced_deployment.side_effect = ApiException(status=404)
        assert rs_manager.get_owner_deployment("web-rs", "default") is None


@pytest.mark.unit
class TestOrphanHelpers:
    def test_is_orphan_true_without_metadata(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = MagicMock()
        rs.metadata = None
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        assert rs_manager.is_orphan("web-rs", "default") is True

    def test_is_orphan_false_when_owned_by_deployment(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = _owned_rs()
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        assert rs_manager.is_orphan("web-rs", "default") is False

    def test_is_orphan_true_without_owner_references(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = MagicMock()
        rs.metadata.owner_references = []
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        assert rs_manager.is_orphan("web-rs", "default") is True

    def test_list_orphan_replicasets(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        owned = _owned_rs()
        orphan = MagicMock()
        orphan.metadata.owner_references = []
        mock_apps_v1.list_namespaced_replica_set.return_value.items = [owned, orphan]

        result = rs_manager.list_orphan_replicasets("default")
        assert result == [orphan]

    def test_list_orphan_replicasets_without_metadata(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        no_meta = MagicMock()
        no_meta.metadata = None
        mock_apps_v1.list_namespaced_replica_set.return_value.items = [no_meta]
        assert rs_manager.list_orphan_replicasets("default") == [no_meta]

    def test_delete_orphans(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        orphan = MagicMock()
        orphan.metadata.owner_references = []
        orphan.metadata.name = "orphan-rs"
        mock_apps_v1.list_namespaced_replica_set.return_value.items = [orphan]

        deleted = rs_manager.delete_orphans("default")

        assert deleted == ["orphan-rs"]
        mock_apps_v1.delete_namespaced_replica_set.assert_called_once()

    def test_delete_orphans_skips_unnamed(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        orphan = MagicMock()
        orphan.metadata = None
        mock_apps_v1.list_namespaced_replica_set.return_value.items = [orphan]

        assert rs_manager.delete_orphans("default") == []


@pytest.mark.unit
class TestValidationAndStatus:
    def test_validate_selector_matches(self, rs_manager: ReplicaSetManager) -> None:
        assert rs_manager.validate_selector({"app": "web"}, {"app": "web", "x": "y"})

    def test_validate_selector_mismatch(self, rs_manager: ReplicaSetManager) -> None:
        assert not rs_manager.validate_selector({"app": "web"}, {"app": "other"})

    def test_get_ready_replicas(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = MagicMock()
        rs.status.ready_replicas = 3
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        assert rs_manager.get_ready_replicas("web-rs", "default") == 3

    def test_get_ready_replicas_without_status(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = MagicMock(status=None)
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        assert rs_manager.get_ready_replicas("web-rs", "default") == 0

    def test_wait_for_replicas_returns_true(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        rs = MagicMock()
        rs.status.ready_replicas = 3
        mock_apps_v1.read_namespaced_replica_set.return_value = rs
        assert (
            rs_manager.wait_for_replicas(
                "web-rs", "default", count=3, timeout_seconds=5
            )
            is True
        )

    def test_wait_for_replicas_ignores_not_found_and_times_out(
        self, rs_manager: ReplicaSetManager, mock_apps_v1: MagicMock
    ) -> None:
        mock_apps_v1.read_namespaced_replica_set.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.workloads.replicaset.time.sleep"):
            assert (
                rs_manager.wait_for_replicas(
                    "web-rs", "default", count=1, timeout_seconds=0.05
                )
                is False
            )
