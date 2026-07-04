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

    def test_create_with_rules(
        self, role_manager: RoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        role_manager.create_with_rules(
            "pod-reader", "default", [""], ["pods"], ["get"], resource_names=["web"]
        )
        call_body = mock_rbac_v1.create_namespaced_role.call_args.kwargs["body"]
        assert call_body.rules[0].resource_names == ["web"]

    def test_add_rule(self, role_manager: RoleManager, mock_rbac_v1: MagicMock) -> None:
        existing = MagicMock()
        existing.rules = []
        mock_rbac_v1.read_namespaced_role.return_value = existing
        role_manager.add_rule("pod-reader", "default", [""], ["pods"], ["get"])
        assert len(existing.rules) == 1
        mock_rbac_v1.replace_namespaced_role.assert_called_once()

    def test_get_role(self, role_manager: RoleManager, mock_rbac_v1: MagicMock) -> None:
        mock_rbac_v1.read_namespaced_role.return_value = "role-obj"
        assert role_manager.get_role("pod-reader", "default") == "role-obj"

    def test_list_roles(
        self, role_manager: RoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_rbac_v1.list_namespaced_role.return_value.items = ["a"]
        assert role_manager.list_roles("default") == ["a"]

    def test_delete_role(
        self, role_manager: RoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        role_manager.delete_role("pod-reader", "default")
        mock_rbac_v1.delete_namespaced_role.assert_called_once()

    def test_kind_and_api_version(self, role_manager: RoleManager) -> None:
        assert role_manager._kind() == "Role"
        assert role_manager._api_version() == "rbac.authorization.k8s.io/v1"


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

    def test_create_cluster_role_with_aggregation_rule(
        self, cr_manager: ClusterRoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        cr_manager.create_cluster_role(
            name="aggregated",
            rules=[],
            aggregation_rule={
                "clusterRoleSelectors": [
                    {"matchLabels": {"rbac.example.com/agg": "true"}}
                ]
            },
        )
        call_body = mock_rbac_v1.create_cluster_role.call_args.kwargs["body"]
        assert call_body.aggregation_rule is not None

    def test_create_with_rules(
        self, cr_manager: ClusterRoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        cr_manager.create_with_rules(
            "node-reader", [""], ["nodes"], ["get"], non_resource_urls=["/healthz"]
        )
        call_body = mock_rbac_v1.create_cluster_role.call_args.kwargs["body"]
        assert call_body.rules[0].resources == ["nodes"]

    def test_add_rule(
        self, cr_manager: ClusterRoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.rules = []
        mock_rbac_v1.read_cluster_role.return_value = existing
        cr_manager.add_rule("node-reader", [""], ["nodes"], ["get"])
        assert len(existing.rules) == 1
        mock_rbac_v1.replace_cluster_role.assert_called_once()

    def test_get_cluster_role(
        self, cr_manager: ClusterRoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_rbac_v1.read_cluster_role.return_value = "cr-obj"
        assert cr_manager.get_cluster_role("node-reader") == "cr-obj"

    def test_list_cluster_roles(
        self, cr_manager: ClusterRoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_rbac_v1.list_cluster_role.return_value.items = ["a"]
        assert cr_manager.list_cluster_roles() == ["a"]

    def test_delete_cluster_role(
        self, cr_manager: ClusterRoleManager, mock_rbac_v1: MagicMock
    ) -> None:
        cr_manager.delete_cluster_role("node-reader")
        mock_rbac_v1.delete_cluster_role.assert_called_once()

    def test_kind_and_api_version(self, cr_manager: ClusterRoleManager) -> None:
        assert cr_manager._kind() == "ClusterRole"
        assert cr_manager._api_version() == "rbac.authorization.k8s.io/v1"
        assert cr_manager._resource_name() == "cluster_role"


@pytest.mark.unit
class TestClusterRoleImportShim:
    def test_cluster_role_module_reexports_manager(self) -> None:
        from kube_orchestrator.resources.rbac.cluster_role import (
            ClusterRoleManager as Reexported,
        )

        assert Reexported is ClusterRoleManager


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

    def test_bind_user(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        rb_manager.bind_user("binding", "default", "pod-reader", "alice")
        call_kwargs = mock_rbac_v1.create_namespaced_role_binding.call_args.kwargs
        assert call_kwargs["body"]["subjects"][0]["kind"] == "User"

    def test_bind_group(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        rb_manager.bind_group("binding", "default", "pod-reader", "devs")
        call_kwargs = mock_rbac_v1.create_namespaced_role_binding.call_args.kwargs
        assert call_kwargs["body"]["subjects"][0]["kind"] == "Group"

    def test_get_rolebinding(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_rbac_v1.read_namespaced_role_binding.return_value = "rb-obj"
        assert rb_manager.get_rolebinding("binding", "default") == "rb-obj"

    def test_list_rolebindings(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        mock_list = MagicMock()
        mock_list.items = [MagicMock()]
        mock_rbac_v1.list_namespaced_role_binding.return_value = mock_list
        result = rb_manager.list_rolebindings("default")
        assert len(result) == 1

    def test_delete_rolebinding(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        rb_manager.delete_rolebinding("binding", "default")
        mock_rbac_v1.delete_namespaced_role_binding.assert_called_once()

    def test_add_subject(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.subjects = []
        mock_rbac_v1.read_namespaced_role_binding.return_value = existing
        rb_manager.add_subject("binding", "default", {"kind": "User", "name": "bob"})
        call_body = mock_rbac_v1.patch_namespaced_role_binding.call_args.kwargs["body"]
        assert call_body["subjects"] == [{"kind": "User", "name": "bob"}]

    def test_remove_subject(
        self, rb_manager: RoleBindingManager, mock_rbac_v1: MagicMock
    ) -> None:
        subject = MagicMock()
        subject.name = "alice"
        existing = MagicMock()
        existing.subjects = [subject]
        mock_rbac_v1.read_namespaced_role_binding.return_value = existing
        rb_manager.remove_subject("binding", "default", "alice")
        call_body = mock_rbac_v1.patch_namespaced_role_binding.call_args.kwargs["body"]
        assert call_body["subjects"] == []

    def test_kind_and_api_version(self, rb_manager: RoleBindingManager) -> None:
        assert rb_manager._kind() == "RoleBinding"
        assert rb_manager._api_version() == "rbac.authorization.k8s.io/v1"
        assert rb_manager._resource_name() == "role_binding"


@pytest.fixture
def crb_api(mock_kube_client: MagicMock) -> MagicMock:
    # ClusterRoleBinding is cluster-scoped: force the same fallback branch
    # BaseResourceManager takes against the real RbacAuthorizationV1Api,
    # which has no `_namespaced_` variant for this resource.
    api = mock_kube_client.rbac_v1
    for verb in ("create", "read", "list", "patch", "delete"):
        delattr(api, f"{verb}_namespaced_cluster_role_binding")
    return api


@pytest.mark.unit
class TestClusterRoleBindingManager:
    def test_create_clusterrolebinding(
        self, crb_manager: ClusterRoleBindingManager, crb_api: MagicMock
    ) -> None:
        crb_manager.create_clusterrolebinding(
            "binding", "node-reader", [{"kind": "User", "name": "alice"}]
        )
        call_kwargs = crb_api.create_cluster_role_binding.call_args.kwargs
        assert call_kwargs["body"]["roleRef"]["name"] == "node-reader"

    def test_bind_service_account(
        self, crb_manager: ClusterRoleBindingManager, crb_api: MagicMock
    ) -> None:
        crb_manager.bind_service_account("binding", "node-reader", "my-sa", "default")
        call_kwargs = crb_api.create_cluster_role_binding.call_args.kwargs
        assert call_kwargs["body"]["subjects"][0]["kind"] == "ServiceAccount"

    def test_bind_user(
        self, crb_manager: ClusterRoleBindingManager, crb_api: MagicMock
    ) -> None:
        crb_manager.bind_user("binding", "node-reader", "alice")
        call_kwargs = crb_api.create_cluster_role_binding.call_args.kwargs
        assert call_kwargs["body"]["subjects"][0]["kind"] == "User"

    def test_bind_group(
        self, crb_manager: ClusterRoleBindingManager, crb_api: MagicMock
    ) -> None:
        crb_manager.bind_group("binding", "node-reader", "devs")
        call_kwargs = crb_api.create_cluster_role_binding.call_args.kwargs
        assert call_kwargs["body"]["subjects"][0]["kind"] == "Group"

    def test_get_clusterrolebinding(
        self, crb_manager: ClusterRoleBindingManager, crb_api: MagicMock
    ) -> None:
        crb_api.read_cluster_role_binding.return_value = "crb-obj"
        assert crb_manager.get_clusterrolebinding("binding") == "crb-obj"

    def test_list_clusterrolebindings(
        self, crb_manager: ClusterRoleBindingManager, crb_api: MagicMock
    ) -> None:
        crb_api.list_cluster_role_binding.return_value.items = ["a"]
        assert crb_manager.list_clusterrolebindings() == ["a"]

    def test_delete_clusterrolebinding(
        self, crb_manager: ClusterRoleBindingManager, crb_api: MagicMock
    ) -> None:
        crb_manager.delete_clusterrolebinding("binding")
        crb_api.delete_cluster_role_binding.assert_called_once()

    def test_kind_and_api_version(self, crb_manager: ClusterRoleBindingManager) -> None:
        assert crb_manager._kind() == "ClusterRoleBinding"
        assert crb_manager._api_version() == "rbac.authorization.k8s.io/v1"
        assert crb_manager._resource_name() == "cluster_role_binding"


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

    def test_create_service_account_with_image_pull_secrets(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        sa_manager.create_service_account(
            "my-sa", "default", image_pull_secrets=["registry-cred"]
        )
        call_body = mock_core_v1.create_namespaced_service_account.call_args.kwargs[
            "body"
        ]
        assert call_body.image_pull_secrets[0].name == "registry-cred"

    def test_get_service_account(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.read_namespaced_service_account.return_value = "sa-obj"
        assert sa_manager.get_service_account("my-sa", "default") == "sa-obj"

    def test_list_service_accounts(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.list_namespaced_service_account.return_value.items = ["a"]
        assert sa_manager.list_service_accounts("default") == ["a"]

    def test_delete_service_account(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        sa_manager.delete_service_account("my-sa", "default")
        mock_core_v1.delete_namespaced_service_account.assert_called_once()

    def test_get_token_minimal(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_service_account_token.return_value.status.token = (
            "tok-123"
        )
        assert sa_manager.get_token("my-sa", "default") == "tok-123"
        call_kwargs = (
            mock_core_v1.create_namespaced_service_account_token.call_args.kwargs
        )
        assert call_kwargs["body"]["spec"] == {}

    def test_get_token_with_all_options(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_service_account_token.return_value.status.token = (
            "tok-123"
        )
        sa_manager.get_token(
            "my-sa",
            "default",
            expiration_seconds=3600,
            audiences=["api"],
            bound_object_ref={"kind": "Pod", "name": "web-1"},
        )
        call_kwargs = (
            mock_core_v1.create_namespaced_service_account_token.call_args.kwargs
        )
        spec = call_kwargs["body"]["spec"]
        assert spec["expirationSeconds"] == 3600
        assert spec["audiences"] == ["api"]
        assert spec["boundObjectRef"]["kind"] == "Pod"

    def test_get_token_returns_empty_without_status(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        mock_core_v1.create_namespaced_service_account_token.return_value.status = None
        assert sa_manager.get_token("my-sa", "default") == ""

    def test_add_image_pull_secret(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        sa = MagicMock()
        sa.image_pull_secrets = []
        mock_core_v1.read_namespaced_service_account.return_value = sa
        sa_manager.add_image_pull_secret("my-sa", "default", "registry-cred")
        assert sa.image_pull_secrets[0].name == "registry-cred"
        mock_core_v1.replace_namespaced_service_account.assert_called_once()

    def test_remove_image_pull_secret(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        secret_ref = MagicMock()
        secret_ref.name = "registry-cred"
        sa = MagicMock()
        sa.image_pull_secrets = [secret_ref]
        mock_core_v1.read_namespaced_service_account.return_value = sa
        sa_manager.remove_image_pull_secret("my-sa", "default", "registry-cred")
        assert sa.image_pull_secrets == []

    def test_set_automount(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        sa = MagicMock()
        mock_core_v1.read_namespaced_service_account.return_value = sa
        sa_manager.set_automount("my-sa", "default", False)
        assert sa.automount_service_account_token is False

    def test_get_secrets(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        sa = MagicMock()
        sa.secrets = ["secret-ref"]
        mock_core_v1.read_namespaced_service_account.return_value = sa
        assert sa_manager.get_secrets("my-sa", "default") == ["secret-ref"]

    def test_get_secrets_defaults_to_empty_list(
        self, sa_manager: ServiceAccountManager, mock_core_v1: MagicMock
    ) -> None:
        sa = MagicMock()
        sa.secrets = None
        mock_core_v1.read_namespaced_service_account.return_value = sa
        assert sa_manager.get_secrets("my-sa", "default") == []

    def test_kind_and_api_version(self, sa_manager: ServiceAccountManager) -> None:
        assert sa_manager._kind() == "ServiceAccount"
        assert sa_manager._api_version() == "v1"
        assert sa_manager._resource_name() == "service_account"
