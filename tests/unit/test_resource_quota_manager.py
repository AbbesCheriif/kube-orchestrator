"""Unit tests for ResourceQuotaManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import APIError, ResourceNotFoundError
from kube_orchestrator.resources.cluster.resource_quota import ResourceQuotaManager


@pytest.fixture
def rq_manager(mock_kube_client: MagicMock) -> ResourceQuotaManager:
    return ResourceQuotaManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestCreateQuota:
    def test_creates_with_hard_only(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        rq_manager.create_quota("compute-quota", "default", hard={"cpu": "4"})
        call_kwargs = mock_core_v1.create_namespaced_resource_quota.call_args.kwargs
        assert call_kwargs["body"]["spec"]["hard"] == {"cpu": "4"}
        assert "scopes" not in call_kwargs["body"]["spec"]

    def test_creates_with_scopes_and_scope_selector(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        rq_manager.create_quota(
            "compute-quota",
            "default",
            hard={"cpu": "4"},
            scopes=["Terminating"],
            scope_selector={"matchExpressions": []},
        )
        call_kwargs = mock_core_v1.create_namespaced_resource_quota.call_args.kwargs
        spec = call_kwargs["body"]["spec"]
        assert spec["scopes"] == ["Terminating"]
        assert spec["scopeSelector"] == {"matchExpressions": []}


@pytest.mark.unit
class TestUpdateQuota:
    def test_updates_hard_values(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock()
        quota.to_dict.return_value = {"spec": {"hard": {"cpu": "8"}}}
        mock_core_v1.read_namespaced_resource_quota.return_value = quota

        rq_manager.update_quota("compute-quota", "default", {"cpu": "8"})

        assert quota.spec.hard == {"cpu": "8"}
        mock_core_v1.replace_namespaced_resource_quota.assert_called_once()

    def test_raises_when_spec_missing(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock()
        quota.spec = None
        mock_core_v1.read_namespaced_resource_quota.return_value = quota
        with pytest.raises(ResourceNotFoundError):
            rq_manager.update_quota("compute-quota", "default", {"cpu": "8"})


@pytest.mark.unit
class TestGetListDelete:
    def test_get_quota(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_resource_quota.return_value = "quota-obj"
        assert rq_manager.get_quota("compute-quota", "default") == "quota-obj"

    def test_list_quotas(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_resource_quota.return_value.items = ["a"]
        assert rq_manager.list_quotas("default") == ["a"]

    def test_delete_quota(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        rq_manager.delete_quota("compute-quota", "default")
        mock_core_v1.delete_namespaced_resource_quota.assert_called_once()


@pytest.mark.unit
class TestUsageHelpers:
    def test_get_used_returns_status_used(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock()
        quota.status.used = {"cpu": "2"}
        mock_core_v1.read_namespaced_resource_quota.return_value = quota
        assert rq_manager.get_used("compute-quota", "default") == {"cpu": "2"}

    def test_get_used_returns_empty_without_status(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock(status=None)
        mock_core_v1.read_namespaced_resource_quota.return_value = quota
        assert rq_manager.get_used("compute-quota", "default") == {}

    def test_get_remaining_formats_hard_and_used(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock()
        quota.status.hard = {"cpu": "4", "memory": "8Gi"}
        quota.status.used = {"cpu": "2"}
        mock_core_v1.read_namespaced_resource_quota.return_value = quota

        result = rq_manager.get_remaining("compute-quota", "default")

        assert result["cpu"] == "4 (used: 2)"
        assert result["memory"] == "8Gi (used: 0)"

    def test_get_remaining_returns_empty_without_status(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock(status=None)
        mock_core_v1.read_namespaced_resource_quota.return_value = quota
        assert rq_manager.get_remaining("compute-quota", "default") == {}

    def test_is_limit_reached_true(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock()
        quota.status.hard = {"pods": "10"}
        quota.status.used = {"pods": "10"}
        mock_core_v1.list_namespaced_resource_quota.return_value.items = [quota]
        assert rq_manager.is_limit_reached("default", "pods") is True

    def test_is_limit_reached_false(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock()
        quota.status.hard = {"pods": "9"}
        quota.status.used = {"pods": "3"}
        mock_core_v1.list_namespaced_resource_quota.return_value.items = [quota]
        assert rq_manager.is_limit_reached("default", "pods") is False

    def test_is_limit_reached_skips_quotas_without_status(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        quota = MagicMock(status=None)
        mock_core_v1.list_namespaced_resource_quota.return_value.items = [quota]
        assert rq_manager.is_limit_reached("default", "pods") is False

    def test_is_limit_reached_raises_parsed_exception(
        self, rq_manager: ResourceQuotaManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_resource_quota.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            rq_manager.is_limit_reached("default", "pods")


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, rq_manager: ResourceQuotaManager) -> None:
        assert rq_manager._kind() == "ResourceQuota"
        assert rq_manager._api_version() == "v1"
        assert rq_manager._resource_name() == "resource_quota"
