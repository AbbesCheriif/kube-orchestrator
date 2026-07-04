"""Integration tests for the RBAC workflow (Role/RoleBinding/ServiceAccount)."""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestRbacWorkflow:
    def test_service_account_role_and_binding_lifecycle(
        self, kube_client, test_namespace
    ) -> None:
        """Create a ServiceAccount, a pod-reader Role, bind them, then tear down."""
        from kube_orchestrator.resources.rbac.role import RoleManager
        from kube_orchestrator.resources.rbac.role_binding import RoleBindingManager
        from kube_orchestrator.resources.rbac.service_account import (
            ServiceAccountManager,
        )

        sa_manager = ServiceAccountManager(kube_client=kube_client)
        role_manager = RoleManager(kube_client=kube_client)
        rb_manager = RoleBindingManager(kube_client=kube_client)

        sa_manager.create_service_account("ci-runner", test_namespace)
        role_manager.create_role(
            name="pod-reader",
            namespace=test_namespace,
            rules=[
                {
                    "apiGroups": [""],
                    "resources": ["pods"],
                    "verbs": ["get", "list", "watch"],
                }
            ],
        )
        rb_manager.bind_service_account(
            name="pod-reader-binding",
            namespace=test_namespace,
            role_name="pod-reader",
            service_account_name="ci-runner",
            service_account_namespace=test_namespace,
        )

        binding = rb_manager.get_rolebinding("pod-reader-binding", test_namespace)
        assert binding.role_ref.name == "pod-reader"

        rb_manager.delete_rolebinding("pod-reader-binding", test_namespace)
        role_manager.delete_role("pod-reader", test_namespace)
        sa_manager.delete_service_account("ci-runner", test_namespace)

    def test_access_validator_can_i_against_own_permissions(
        self, kube_client, test_namespace
    ) -> None:
        """can_i should return a plain bool without raising against a live cluster."""
        from kube_orchestrator.resources.rbac.access_validator import AccessValidator

        validator = AccessValidator(client=kube_client)
        result = validator.can_i("get", "pods", namespace=test_namespace)
        assert isinstance(result, bool)
