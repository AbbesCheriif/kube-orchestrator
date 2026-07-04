"""Unit tests for kube_orchestrator.resources.rbac.access_validator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.resources.rbac.access_validator import AccessValidator


@pytest.fixture
def validator(mock_kube_client: MagicMock) -> AccessValidator:
    return AccessValidator(client=mock_kube_client)


@pytest.fixture
def auth_api() -> MagicMock:
    with patch(
        "kube_orchestrator.resources.rbac.access_validator.AuthorizationV1Api"
    ) as auth_cls:
        yield auth_cls.return_value


@pytest.mark.unit
class TestCanI:
    def test_returns_true_when_allowed(
        self, validator: AccessValidator, auth_api: MagicMock
    ) -> None:
        auth_api.create_self_subject_access_review.return_value.status.allowed = True
        assert validator.can_i("get", "pods", namespace="default") is True

    def test_returns_false_when_denied(
        self, validator: AccessValidator, auth_api: MagicMock
    ) -> None:
        auth_api.create_self_subject_access_review.return_value.status.allowed = False
        assert validator.can_i("delete", "secrets") is False

    def test_returns_false_without_status(
        self, validator: AccessValidator, auth_api: MagicMock
    ) -> None:
        auth_api.create_self_subject_access_review.return_value.status = None
        assert validator.can_i("get", "pods") is False

    def test_sends_resource_attributes(
        self, validator: AccessValidator, auth_api: MagicMock
    ) -> None:
        auth_api.create_self_subject_access_review.return_value.status.allowed = True
        validator.can_i(
            "get", "pods", namespace="default", resource_name="web-1", subresource="log"
        )
        body = auth_api.create_self_subject_access_review.call_args.args[0]
        attrs = body["spec"]["resourceAttributes"]
        assert attrs["name"] == "web-1"
        assert attrs["subresource"] == "log"


@pytest.mark.unit
class TestCanServiceAccount:
    def test_returns_true_when_allowed(
        self, validator: AccessValidator, auth_api: MagicMock
    ) -> None:
        auth_api.create_subject_access_review.return_value.status.allowed = True
        result = validator.can_service_account(
            "my-sa", "default", "get", "pods", namespace="default"
        )
        assert result is True
        body = auth_api.create_subject_access_review.call_args.args[0]
        assert body["spec"]["user"] == "system:serviceaccount:default:my-sa"

    def test_returns_false_without_status(
        self, validator: AccessValidator, auth_api: MagicMock
    ) -> None:
        auth_api.create_subject_access_review.return_value.status = None
        assert validator.can_service_account("my-sa", "default", "get", "pods") is False


@pytest.mark.unit
class TestListPermissionsForSubject:
    def test_collects_namespaced_and_cluster_roles(
        self, validator: AccessValidator, mock_kube_client: MagicMock
    ) -> None:
        subject = MagicMock(kind="ServiceAccount")
        subject.name = "my-sa"
        rb = MagicMock()
        rb.subjects = [subject]
        rb.role_ref.name = "pod-reader"
        mock_kube_client.rbac_v1.list_namespaced_role_binding.return_value.items = [rb]

        crb_subject = MagicMock(kind="ServiceAccount")
        crb_subject.name = "my-sa"
        crb = MagicMock()
        crb.subjects = [crb_subject]
        crb.role_ref.name = "node-reader"
        mock_kube_client.rbac_v1.list_cluster_role_binding.return_value.items = [crb]

        result = validator.list_permissions_for_subject(
            "ServiceAccount", "my-sa", "default"
        )

        assert result["roles"] == ["pod-reader"]
        assert result["cluster_roles"] == ["node-reader"]

    def test_skips_non_matching_subjects(
        self, validator: AccessValidator, mock_kube_client: MagicMock
    ) -> None:
        other_subject = MagicMock(kind="User")
        other_subject.name = "alice"
        rb = MagicMock()
        rb.subjects = [other_subject]
        mock_kube_client.rbac_v1.list_namespaced_role_binding.return_value.items = [rb]
        mock_kube_client.rbac_v1.list_cluster_role_binding.return_value.items = []

        result = validator.list_permissions_for_subject(
            "ServiceAccount", "my-sa", "default"
        )
        assert result["roles"] == []

    def test_cluster_scoped_only_when_no_namespace(
        self, validator: AccessValidator, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.rbac_v1.list_cluster_role_binding.return_value.items = []
        result = validator.list_permissions_for_subject("ServiceAccount", "my-sa")
        mock_kube_client.rbac_v1.list_namespaced_role_binding.assert_not_called()
        assert result == {"roles": [], "cluster_roles": []}

    def test_handles_bindings_without_subjects(
        self, validator: AccessValidator, mock_kube_client: MagicMock
    ) -> None:
        rb = MagicMock(subjects=None)
        mock_kube_client.rbac_v1.list_namespaced_role_binding.return_value.items = [rb]
        crb = MagicMock(subjects=None)
        mock_kube_client.rbac_v1.list_cluster_role_binding.return_value.items = [crb]

        result = validator.list_permissions_for_subject(
            "ServiceAccount", "my-sa", "default"
        )
        assert result == {"roles": [], "cluster_roles": []}


@pytest.mark.unit
class TestCheckRbacCoverage:
    def test_checks_each_required_permission(
        self, validator: AccessValidator, auth_api: MagicMock
    ) -> None:
        auth_api.create_self_subject_access_review.return_value.status.allowed = True
        result = validator.check_rbac_coverage(
            "default", [{"verb": "get", "resource": "pods"}]
        )
        assert result == {"get:pods": True}


@pytest.mark.unit
class TestGetWhoCan:
    def test_lists_subjects_with_roles(
        self, validator: AccessValidator, mock_kube_client: MagicMock
    ) -> None:
        subject = MagicMock(kind="User")
        subject.name = "alice"
        del subject.namespace
        rb = MagicMock()
        rb.subjects = [subject]
        rb.role_ref.name = "pod-reader"
        mock_kube_client.rbac_v1.list_namespaced_role_binding.return_value.items = [rb]

        result = validator.get_who_can("get", "pods", "default")

        assert result == [
            {"kind": "User", "name": "alice", "namespace": None, "role": "pod-reader"}
        ]

    def test_handles_bindings_without_subjects(
        self, validator: AccessValidator, mock_kube_client: MagicMock
    ) -> None:
        rb = MagicMock(subjects=None)
        mock_kube_client.rbac_v1.list_namespaced_role_binding.return_value.items = [rb]
        assert validator.get_who_can("get", "pods", "default") == []


@pytest.mark.unit
class TestAuditServiceAccount:
    def test_combines_permissions_and_access_checks(
        self,
        validator: AccessValidator,
        mock_kube_client: MagicMock,
        auth_api: MagicMock,
    ) -> None:
        mock_kube_client.rbac_v1.list_namespaced_role_binding.return_value.items = []
        mock_kube_client.rbac_v1.list_cluster_role_binding.return_value.items = []
        auth_api.create_subject_access_review.return_value.status.allowed = True

        result = validator.audit_service_account("my-sa", "default")

        assert result["permissions"] == {"roles": [], "cluster_roles": []}
        assert result["access_checks"]["get:pods"] is True
        assert len(result["access_checks"]) == 5
