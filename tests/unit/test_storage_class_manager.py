"""Unit tests for StorageClassManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.core.exceptions import ResourceNotFoundError
from kube_orchestrator.resources.storage.storage_class import StorageClassManager


@pytest.fixture
def sc_manager(mock_kube_client: MagicMock) -> StorageClassManager:
    return StorageClassManager(kube_client=mock_kube_client)


@pytest.fixture
def storage_api(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.storage_v1


@pytest.mark.unit
class TestCreateStorageClass:
    def test_creates_with_defaults(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        sc_manager.create_storage_class("fast", "kubernetes.io/aws-ebs")
        call_body = storage_api.create_storage_class.call_args.kwargs["body"]
        assert call_body.provisioner == "kubernetes.io/aws-ebs"
        assert call_body.reclaim_policy == "Delete"
        assert call_body.volume_binding_mode == "Immediate"

    def test_creates_with_all_fields(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        sc_manager.create_storage_class(
            "fast",
            "kubernetes.io/aws-ebs",
            parameters={"type": "gp3"},
            reclaim_policy="Retain",
            volume_binding_mode="WaitForFirstConsumer",
            allow_volume_expansion=True,
            mount_options=["debug"],
            allowed_topologies=[{"matchLabelExpressions": []}],
            labels={"tier": "gold"},
            annotations={"owner": "team-a"},
        )
        call_body = storage_api.create_storage_class.call_args.kwargs["body"]
        assert call_body.parameters == {"type": "gp3"}
        assert call_body.reclaim_policy == "Retain"
        assert call_body.allow_volume_expansion is True
        assert call_body.mount_options == ["debug"]


@pytest.mark.unit
class TestGetListDelete:
    def test_get_storage_class(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        storage_api.read_storage_class.return_value = "sc-obj"
        assert sc_manager.get_storage_class("fast") == "sc-obj"

    def test_list_storage_classes(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        storage_api.list_storage_class.return_value.items = ["a", "b"]
        assert sc_manager.list_storage_classes() == ["a", "b"]

    def test_delete_storage_class(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        sc_manager.delete_storage_class("fast")
        storage_api.delete_storage_class.assert_called_once()


@pytest.mark.unit
class TestDefaultManagement:
    def test_set_as_default(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        sc = MagicMock()
        sc.metadata.annotations = {}
        storage_api.read_storage_class.return_value = sc

        sc_manager.set_as_default("fast")

        assert (
            sc.metadata.annotations["storageclass.kubernetes.io/is-default-class"]
            == "true"
        )

    def test_set_as_default_raises_without_metadata(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        storage_api.read_storage_class.return_value = MagicMock(metadata=None)
        with pytest.raises(ResourceNotFoundError):
            sc_manager.set_as_default("fast")

    def test_unset_default(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        sc = MagicMock()
        sc.metadata.annotations = {
            "storageclass.kubernetes.io/is-default-class": "true"
        }
        storage_api.read_storage_class.return_value = sc

        sc_manager.unset_default("fast")

        assert (
            "storageclass.kubernetes.io/is-default-class" not in sc.metadata.annotations
        )

    def test_unset_default_without_annotations_is_noop(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        sc = MagicMock()
        sc.metadata.annotations = None
        storage_api.read_storage_class.return_value = sc

        sc_manager.unset_default("fast")
        storage_api.replace_storage_class.assert_called_once()

    def test_get_default_returns_matching_class(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        default_sc = MagicMock()
        default_sc.metadata.annotations = {
            "storageclass.kubernetes.io/is-default-class": "true"
        }
        other_sc = MagicMock()
        other_sc.metadata.annotations = {}
        storage_api.list_storage_class.return_value.items = [other_sc, default_sc]

        assert sc_manager.get_default() is default_sc

    def test_get_default_returns_none_when_no_default(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        other_sc = MagicMock()
        other_sc.metadata.annotations = {}
        storage_api.list_storage_class.return_value.items = [other_sc]

        assert sc_manager.get_default() is None


@pytest.mark.unit
class TestUpdateReclaimPolicyAndUsage:
    def test_update_reclaim_policy(
        self, sc_manager: StorageClassManager, storage_api: MagicMock
    ) -> None:
        sc = MagicMock()
        storage_api.read_storage_class.return_value = sc

        sc_manager.update_reclaim_policy("fast", "Retain")

        assert sc.reclaim_policy == "Retain"

    def test_get_pvs_using(
        self, sc_manager: StorageClassManager, mock_kube_client: MagicMock
    ) -> None:
        pv1 = MagicMock()
        pv1.spec.storage_class_name = "fast"
        pv2 = MagicMock()
        pv2.spec.storage_class_name = "slow"
        mock_kube_client.core_v1.list_persistent_volume.return_value.items = [
            pv1,
            pv2,
        ]

        assert sc_manager.get_pvs_using("fast") == [pv1]


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, sc_manager: StorageClassManager) -> None:
        assert sc_manager._kind() == "StorageClass"
        assert sc_manager._api_version() == "storage.k8s.io/v1"
        assert sc_manager._resource_name() == "storage_class"
