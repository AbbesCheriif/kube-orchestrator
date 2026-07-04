"""Unit tests for PersistentVolumeManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.resources.storage.persistent_volume import (
    PersistentVolumeManager,
)


@pytest.fixture
def pv_manager(mock_kube_client: MagicMock) -> PersistentVolumeManager:
    return PersistentVolumeManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestCreatePV:
    def test_creates_with_minimal_fields(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        pv_manager.create_pv("pv-1", "10Gi", ["ReadWriteOnce"])
        call_body = mock_core_v1.create_persistent_volume.call_args.kwargs["body"]
        assert call_body["spec"]["capacity"]["storage"] == "10Gi"
        assert call_body["spec"]["persistentVolumeReclaimPolicy"] == "Retain"

    def test_creates_with_all_optional_fields(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        pv_manager.create_pv(
            "pv-1",
            "10Gi",
            ["ReadWriteOnce"],
            storage_class_name="fast",
            nfs={"server": "nfs.local", "path": "/data"},
            host_path={"path": "/mnt/data"},
            csi={"driver": "ebs.csi.aws.com"},
            local={"path": "/mnt/disk"},
            node_affinity={"required": {}},
            mount_options=["hard"],
            claim_ref={"name": "pvc-1"},
            labels={"tier": "gold"},
        )
        call_body = mock_core_v1.create_persistent_volume.call_args.kwargs["body"]
        spec = call_body["spec"]
        assert spec["storageClassName"] == "fast"
        assert spec["nfs"]["server"] == "nfs.local"
        assert spec["hostPath"]["path"] == "/mnt/data"
        assert spec["csi"]["driver"] == "ebs.csi.aws.com"
        assert spec["local"]["path"] == "/mnt/disk"
        assert spec["nodeAffinity"] == {"required": {}}
        assert spec["mountOptions"] == ["hard"]
        assert spec["claimRef"]["name"] == "pvc-1"
        assert call_body["metadata"]["labels"] == {"tier": "gold"}


@pytest.mark.unit
class TestGetListDeletePV:
    def test_get_pv(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_persistent_volume.return_value = "pv-obj"
        assert pv_manager.get_pv("pv-1") == "pv-obj"

    def test_list_pvs_without_filter(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        pv1 = MagicMock(status=MagicMock(phase="Bound"))
        pv2 = MagicMock(status=MagicMock(phase="Available"))
        mock_core_v1.list_persistent_volume.return_value.items = [pv1, pv2]
        assert pv_manager.list_pvs() == [pv1, pv2]

    def test_list_pvs_filtered_by_phase(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        pv1 = MagicMock(status=MagicMock(phase="Bound"))
        pv2 = MagicMock(status=MagicMock(phase="Available"))
        mock_core_v1.list_persistent_volume.return_value.items = [pv1, pv2]
        assert pv_manager.list_pvs(phase="Available") == [pv2]

    def test_delete_pv(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        pv_manager.delete_pv("pv-1")
        mock_core_v1.delete_persistent_volume.assert_called_once()


@pytest.mark.unit
class TestPhaseAndBinding:
    def test_get_phase_returns_status_phase(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_persistent_volume.return_value = MagicMock(
            status=MagicMock(phase="Bound")
        )
        assert pv_manager.get_phase("pv-1") == "Bound"

    def test_get_phase_defaults_to_unknown(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_persistent_volume.return_value = MagicMock(status=None)
        assert pv_manager.get_phase("pv-1") == "Unknown"

    def test_get_bound_pvc_returns_namespace_slash_name(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        ref = MagicMock()
        ref.namespace = "default"
        ref.name = "my-pvc"
        pv = MagicMock()
        pv.spec.claim_ref = ref
        mock_core_v1.read_persistent_volume.return_value = pv
        assert pv_manager.get_bound_pvc("pv-1") == "default/my-pvc"

    def test_get_bound_pvc_returns_none_when_unbound(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        pv = MagicMock()
        pv.spec.claim_ref = None
        mock_core_v1.read_persistent_volume.return_value = pv
        assert pv_manager.get_bound_pvc("pv-1") is None


@pytest.mark.unit
class TestListingHelpers:
    def test_list_available_pvs(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        pv1 = MagicMock(status=MagicMock(phase="Available"))
        mock_core_v1.list_persistent_volume.return_value.items = [pv1]
        assert pv_manager.list_available_pvs() == [pv1]

    def test_list_by_storage_class(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        pv1 = MagicMock()
        pv1.spec.storage_class_name = "fast"
        pv2 = MagicMock()
        pv2.spec.storage_class_name = "slow"
        mock_core_v1.list_persistent_volume.return_value.items = [pv1, pv2]
        assert pv_manager.list_by_storage_class("fast") == [pv1]


@pytest.mark.unit
class TestWaitHelpers:
    def test_wait_for_available_returns_true_when_reached(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_persistent_volume.return_value = MagicMock(
            status=MagicMock(phase="Available")
        )
        assert pv_manager.wait_for_available("pv-1", timeout_seconds=5) is True

    def test_wait_for_available_times_out(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_persistent_volume.return_value = MagicMock(
            status=MagicMock(phase="Pending")
        )
        with patch("kube_orchestrator.resources.storage.persistent_volume.time.sleep"):
            assert pv_manager.wait_for_available("pv-1", timeout_seconds=0.05) is False

    def test_wait_for_released_returns_true_when_reached(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_persistent_volume.return_value = MagicMock(
            status=MagicMock(phase="Released")
        )
        assert pv_manager.wait_for_released("pv-1", timeout_seconds=5) is True

    def test_wait_for_released_times_out(
        self, pv_manager: PersistentVolumeManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_persistent_volume.return_value = MagicMock(
            status=MagicMock(phase="Bound")
        )
        with patch("kube_orchestrator.resources.storage.persistent_volume.time.sleep"):
            assert pv_manager.wait_for_released("pv-1", timeout_seconds=0.05) is False


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, pv_manager: PersistentVolumeManager) -> None:
        assert pv_manager._kind() == "PersistentVolume"
        assert pv_manager._api_version() == "v1"
        assert pv_manager._resource_name() == "persistent_volume"
