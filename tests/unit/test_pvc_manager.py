"""Unit tests for PVCManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.core.exceptions import ResourceNotFoundError
from kube_orchestrator.resources.storage.persistent_volume_claim import PVCManager


@pytest.fixture
def pvc_manager(mock_kube_client: MagicMock) -> PVCManager:
    return PVCManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestCreatePVC:
    def test_creates_with_minimal_fields(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        pvc_manager.create_pvc("pvc-1", "default", ["ReadWriteOnce"], "5Gi")
        call_kwargs = mock_core_v1.create_namespaced_persistent_volume_claim.call_args.kwargs
        assert call_kwargs["body"]["spec"]["resources"]["requests"]["storage"] == "5Gi"

    def test_creates_with_all_optional_fields(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        pvc_manager.create_pvc(
            "pvc-1",
            "default",
            ["ReadWriteOnce"],
            "5Gi",
            storage_class_name="fast",
            volume_name="pv-1",
            selector={"matchLabels": {"tier": "gold"}},
            data_source={"kind": "VolumeSnapshot", "name": "snap-1"},
            data_source_ref={"kind": "VolumeSnapshot", "name": "snap-1"},
            storage_limit="10Gi",
            labels={"app": "db"},
        )
        call_kwargs = mock_core_v1.create_namespaced_persistent_volume_claim.call_args.kwargs
        spec = call_kwargs["body"]["spec"]
        assert spec["storageClassName"] == "fast"
        assert spec["volumeName"] == "pv-1"
        assert spec["selector"]["matchLabels"] == {"tier": "gold"}
        assert spec["dataSource"]["name"] == "snap-1"
        assert spec["dataSourceRef"]["name"] == "snap-1"
        assert spec["resources"]["limits"]["storage"] == "10Gi"
        assert call_kwargs["body"]["metadata"]["labels"] == {"app": "db"}


@pytest.mark.unit
class TestGetListPVC:
    def test_get_pvc(self, pvc_manager: PVCManager, mock_core_v1: MagicMock) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = "pvc-obj"
        assert pvc_manager.get_pvc("pvc-1", "default") == "pvc-obj"

    def test_list_pvcs_without_filter(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        p1 = MagicMock(status=MagicMock(phase="Bound"))
        p2 = MagicMock(status=MagicMock(phase="Pending"))
        mock_core_v1.list_namespaced_persistent_volume_claim.return_value.items = [
            p1,
            p2,
        ]
        assert pvc_manager.list_pvcs("default") == [p1, p2]

    def test_list_pvcs_filtered_by_phase(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        p1 = MagicMock(status=MagicMock(phase="Bound"))
        p2 = MagicMock(status=MagicMock(phase="Pending"))
        mock_core_v1.list_namespaced_persistent_volume_claim.return_value.items = [
            p1,
            p2,
        ]
        assert pvc_manager.list_pvcs("default", phase="Bound") == [p1]


@pytest.mark.unit
class TestDeletePVC:
    def test_delete_without_wait(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        pvc_manager.delete_pvc("pvc-1", "default")
        mock_core_v1.delete_namespaced_persistent_volume_claim.assert_called_once()

    def test_delete_with_wait_until_not_found(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.side_effect = RuntimeError(
            "not found"
        )
        pvc_manager.delete_pvc("pvc-1", "default", wait=True)
        mock_core_v1.delete_namespaced_persistent_volume_claim.assert_called_once()

    def test_delete_with_wait_polls_until_deadline(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = MagicMock()
        with patch(
            "kube_orchestrator.resources.storage.persistent_volume_claim.time"
        ) as fake_time:
            fake_time.time.side_effect = [0, 0, 200]
            pvc_manager.delete_pvc("pvc-1", "default", wait=True)
        mock_core_v1.delete_namespaced_persistent_volume_claim.assert_called_once()


@pytest.mark.unit
class TestPhaseAndBinding:
    def test_get_phase_returns_status_phase(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = MagicMock(
            status=MagicMock(phase="Bound")
        )
        assert pvc_manager.get_phase("pvc-1", "default") == "Bound"

    def test_get_phase_defaults_to_unknown(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = MagicMock(
            status=None
        )
        assert pvc_manager.get_phase("pvc-1", "default") == "Unknown"

    def test_get_bound_pv(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        pvc = MagicMock()
        pvc.spec.volume_name = "pv-1"
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = pvc
        assert pvc_manager.get_bound_pv("pvc-1", "default") == "pv-1"

    def test_get_bound_pv_returns_none_without_spec(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        pvc = MagicMock()
        pvc.spec = None
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = pvc
        assert pvc_manager.get_bound_pv("pvc-1", "default") is None


@pytest.mark.unit
class TestWaitForBound:
    def test_returns_true_when_bound(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = MagicMock(
            status=MagicMock(phase="Bound")
        )
        assert pvc_manager.wait_for_bound("pvc-1", "default", timeout_seconds=5) is True

    def test_returns_false_on_timeout(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = MagicMock(
            status=MagicMock(phase="Pending")
        )
        with patch(
            "kube_orchestrator.resources.storage.persistent_volume_claim.time.sleep"
        ):
            assert (
                pvc_manager.wait_for_bound("pvc-1", "default", timeout_seconds=0.05)
                is False
            )


@pytest.mark.unit
class TestExpand:
    def test_expand_sets_new_storage_request(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        pvc = MagicMock()
        pvc.spec.resources.requests = {"storage": "5Gi"}
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = pvc

        pvc_manager.expand("pvc-1", "default", "10Gi")

        assert pvc.spec.resources.requests["storage"] == "10Gi"
        mock_core_v1.replace_namespaced_persistent_volume_claim.assert_called_once()

    def test_expand_creates_resources_when_missing(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        pvc = MagicMock()
        pvc.spec.resources = None
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = pvc

        pvc_manager.expand("pvc-1", "default", "10Gi")

        assert pvc.spec.resources.requests["storage"] == "10Gi"

    def test_expand_raises_when_spec_missing(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        pvc = MagicMock()
        pvc.spec = None
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = pvc

        with pytest.raises(ResourceNotFoundError):
            pvc_manager.expand("pvc-1", "default", "10Gi")


@pytest.mark.unit
class TestGetCapacity:
    def test_returns_capacity_storage(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = MagicMock(
            status=MagicMock(capacity={"storage": "5Gi"})
        )
        assert pvc_manager.get_capacity("pvc-1", "default") == "5Gi"

    def test_returns_empty_string_without_capacity(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_persistent_volume_claim.return_value = MagicMock(
            status=None
        )
        assert pvc_manager.get_capacity("pvc-1", "default") == ""


@pytest.mark.unit
class TestGetUsedByPods:
    def test_finds_pods_mounting_the_claim(
        self, pvc_manager: PVCManager, mock_core_v1: MagicMock
    ) -> None:
        matching_pod = MagicMock()
        vol = MagicMock()
        vol.persistent_volume_claim.claim_name = "pvc-1"
        matching_pod.spec.volumes = [vol]

        other_pod = MagicMock()
        other_vol = MagicMock()
        other_vol.persistent_volume_claim.claim_name = "other-pvc"
        other_pod.spec.volumes = [other_vol]

        no_volumes_pod = MagicMock()
        no_volumes_pod.spec.volumes = None

        mock_core_v1.list_namespaced_pod.return_value.items = [
            matching_pod,
            other_pod,
            no_volumes_pod,
        ]

        result = pvc_manager.get_used_by_pods("pvc-1", "default")
        assert result == [matching_pod]


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, pvc_manager: PVCManager) -> None:
        assert pvc_manager._kind() == "PersistentVolumeClaim"
        assert pvc_manager._api_version() == "v1"
        assert pvc_manager._resource_name() == "persistent_volume_claim"
