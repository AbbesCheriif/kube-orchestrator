"""Unit tests for PodDisruptionBudgetManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import (
    APIError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
)
from kube_orchestrator.resources.cluster.pdb import PodDisruptionBudgetManager


@pytest.fixture
def pdb_manager(mock_kube_client: MagicMock) -> PodDisruptionBudgetManager:
    return PodDisruptionBudgetManager(kube_client=mock_kube_client)


@pytest.fixture
def policy_api(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.policy_v1


@pytest.mark.unit
class TestCreatePdb:
    def test_creates_with_min_available(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb_manager.create_pdb(
            "web-pdb",
            "default",
            selector={"matchLabels": {"app": "web"}},
            min_available=2,
        )
        call_kwargs = (
            policy_api.create_namespaced_pod_disruption_budget.call_args.kwargs
        )
        assert call_kwargs["body"]["spec"]["minAvailable"] == 2

    def test_creates_with_max_unavailable_and_eviction_policy(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb_manager.create_pdb(
            "web-pdb",
            "default",
            max_unavailable="25%",
            unhealthy_pod_eviction_policy="AlwaysAllow",
        )
        call_kwargs = (
            policy_api.create_namespaced_pod_disruption_budget.call_args.kwargs
        )
        spec = call_kwargs["body"]["spec"]
        assert spec["maxUnavailable"] == "25%"
        assert spec["unhealthyPodEvictionPolicy"] == "AlwaysAllow"

    def test_raises_parsed_exception(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        policy_api.create_namespaced_pod_disruption_budget.side_effect = ApiException(
            status=409
        )
        with pytest.raises(ResourceAlreadyExistsError):
            pdb_manager.create_pdb("web-pdb", "default")


@pytest.mark.unit
class TestGetListUpdateDelete:
    def test_get_pdb(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        policy_api.read_namespaced_pod_disruption_budget.return_value = "pdb-obj"
        assert pdb_manager.get_pdb("web-pdb", "default") == "pdb-obj"

    def test_get_pdb_raises_parsed_exception(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        policy_api.read_namespaced_pod_disruption_budget.side_effect = ApiException(
            status=404
        )
        with pytest.raises(ResourceNotFoundError):
            pdb_manager.get_pdb("web-pdb", "default")

    def test_list_pdbs(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        policy_api.list_namespaced_pod_disruption_budget.return_value.items = ["a"]
        assert pdb_manager.list_pdbs("default") == ["a"]

    def test_list_pdbs_raises_parsed_exception(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        policy_api.list_namespaced_pod_disruption_budget.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            pdb_manager.list_pdbs("default")

    def test_update_pdb_min_available(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb_manager.update_pdb("web-pdb", "default", min_available=3)
        call_kwargs = policy_api.patch_namespaced_pod_disruption_budget.call_args.kwargs
        assert call_kwargs["body"]["spec"]["minAvailable"] == 3

    def test_update_pdb_max_unavailable(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb_manager.update_pdb("web-pdb", "default", max_unavailable=1)
        call_kwargs = policy_api.patch_namespaced_pod_disruption_budget.call_args.kwargs
        assert call_kwargs["body"]["spec"]["maxUnavailable"] == 1

    def test_update_pdb_raises_parsed_exception(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        policy_api.patch_namespaced_pod_disruption_budget.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            pdb_manager.update_pdb("web-pdb", "default", min_available=1)

    def test_delete_pdb(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb_manager.delete_pdb("web-pdb", "default")
        policy_api.delete_namespaced_pod_disruption_budget.assert_called_once()

    def test_delete_pdb_raises_parsed_exception(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        policy_api.delete_namespaced_pod_disruption_budget.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            pdb_manager.delete_pdb("web-pdb", "default")


@pytest.mark.unit
class TestStatusHelpers:
    def test_get_status_with_conditions(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        cond = MagicMock()
        cond.to_dict.return_value = {"type": "InsufficientPods"}
        pdb = MagicMock()
        pdb.status.current_healthy = 3
        pdb.status.desired_healthy = 2
        pdb.status.disruptions_allowed = 1
        pdb.status.expected_pods = 3
        pdb.status.observed_generation = 1
        pdb.status.conditions = [cond]
        policy_api.read_namespaced_pod_disruption_budget.return_value = pdb

        result = pdb_manager.get_status("web-pdb", "default")

        assert result["current_healthy"] == 3
        assert result["conditions"] == [{"type": "InsufficientPods"}]

    def test_get_status_without_status(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb = MagicMock(status=None)
        policy_api.read_namespaced_pod_disruption_budget.return_value = pdb

        result = pdb_manager.get_status("web-pdb", "default")

        assert result == {
            "current_healthy": 0,
            "desired_healthy": 0,
            "disruptions_allowed": 0,
            "expected_pods": 0,
            "observed_generation": 0,
            "conditions": [],
        }

    def test_get_disruptions_allowed(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb = MagicMock()
        pdb.status.disruptions_allowed = 2
        policy_api.read_namespaced_pod_disruption_budget.return_value = pdb
        assert pdb_manager.get_disruptions_allowed("web-pdb", "default") == 2

    def test_is_disruption_allowed_true(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb = MagicMock()
        pdb.status.disruptions_allowed = 1
        policy_api.read_namespaced_pod_disruption_budget.return_value = pdb
        assert pdb_manager.is_disruption_allowed("web-pdb", "default") is True

    def test_is_disruption_allowed_false(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        pdb = MagicMock()
        pdb.status.disruptions_allowed = 0
        policy_api.read_namespaced_pod_disruption_budget.return_value = pdb
        assert pdb_manager.is_disruption_allowed("web-pdb", "default") is False


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(
        self, pdb_manager: PodDisruptionBudgetManager
    ) -> None:
        assert pdb_manager._kind() == "PodDisruptionBudget"
        assert pdb_manager._api_version() == "policy/v1"
        assert pdb_manager._resource_name() == "pod_disruption_budget"

    def test_get_api_returns_policy_v1(
        self, pdb_manager: PodDisruptionBudgetManager, policy_api: MagicMock
    ) -> None:
        assert pdb_manager._get_api() is policy_api
