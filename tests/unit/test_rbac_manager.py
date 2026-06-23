"""Unit tests for RBAC managers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.rbac.role import ClusterRoleManager, RoleManager
from kube_orchestrator.resources.rbac.role_binding import (
    ClusterRoleBindingManager,
    RoleBindingManager,
)
from kube_orchestrator.resources.rbac.service_account import ServiceAccountManager


@pytest.fixture
def role_manager(mock_kube_client: MagicMock) -> RoleManager:
    return RoleManager(kube_client=mock_kube_client)


@pytest.fixture
def cr_manager(mock_kube_client: MagicMock) -> ClusterRoleManager:
    return ClusterRoleManager(kube_client=mock_kube_client)


@pytest.fixture
def rb_manager(mock_kube_client: MagicMock) -> RoleBindingManager:
    return RoleBindingManager(kube_client=mock_kube_client)


@pytest.fixture
def crb_manager(mock_kube_client: MagicMock) -> ClusterRoleBindingManager:
    return ClusterRoleBindingManager(kube_client=mock_kube_client)


@pytest.fixture
def sa_manager(mock_kube_client: MagicMock) -> ServiceAccountManager:
    return ServiceAccountManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestRoleManager:
    def test_create_role(
        self, role_manager: RoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_rbac_v1.create_namespaced_role.return_value = MagicMock()
        role_manager.create_role(
            name="pod-reader",
            namespace="default",
            rules=[
                {
                    "apiGroups": [""],
                    "resources": ["pods"],
                    "verbs": ["get", "list", "watch"],
                }
            ],
        )
        mock_rbac_v1.create_namespaced_role.assert_called_once()

    def test_delete_role(
        self, role_manager: RoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        role_manager.delete_role("pod-reader", "default")
        mock_rbac_v1.delete_namespaced_role.assert_called_once()


@pytest.mark.unit
class TestClusterRoleManager:
    def test_create_cluster_role(
        self, cr_manager: ClusterRoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_rbac_v1.create_cluster_role.return_value = MagicMock()
        cr_manager.create_cluster_role(
            name="node-reader",
            rules=[
                {"apiGroups": [""], "resources": ["nodes"], "verbs": ["get", "list"]}
            ],
        )
        mock_rbac_v1.create_cluster_role.assert_called_once()


@pytest.mark.unit
class TestRoleBindingManager:
    def test_bind_service_account(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_rbac_v1.create_namespaced_role_binding.return_value = MagicMock()
        rb_manager.bind_service_account(
            name="pod-reader-binding",
            namespace="default",
            role_name="pod-reader",
            service_account_name="my-sa",
            service_account_namespace="default",
            role_kind="Role",
        )
        mock_rbac_v1.create_namespaced_role_binding.assert_called_once()

    def test_list_rolebindings(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_list = MagicMock()
        mock_list.items = [MagicMock()]
        mock_rbac_v1.list_namespaced_role_binding.return_value = mock_list
        result = rb_manager.list_rolebindings("default")
        assert len(result) == 1


@pytest.mark.unit
class TestServiceAccountManager:
    def test_create_service_account(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_service_account.return_value = MagicMock()
        sa_manager.create_service_account(
            name="my-sa",
            namespace="default",
            automount_token=False,
        )
        mock_core_v1.create_namespaced_service_account.assert_called_once()
        call_body = mock_core_v1.create_namespaced_service_account.call_args.kwargs[
            "body"
        ]
        assert call_body.automount_service_account_token is False
