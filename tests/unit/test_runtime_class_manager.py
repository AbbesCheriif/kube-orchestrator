"""Unit tests for RuntimeClassManager and LeaseManager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.cluster.runtime_class import (
    LeaseManager,
    RuntimeClassManager,
)


@pytest.fixture
def rc_manager(mock_kube_client: MagicMock) -> RuntimeClassManager:
    return RuntimeClassManager(kube_client=mock_kube_client)


@pytest.fixture
def node_api(mock_kube_client: MagicMock) -> MagicMock:
    # RuntimeClass is cluster-scoped: the real NodeV1Api only has
    # create_runtime_class/read_runtime_class/etc (no `_namespaced_` variant).
    # A bare MagicMock auto-vivifies the namespaced name too, which would
    # short-circuit BaseResourceManager's getattr probe — delete it so the
    # test exercises the same fallback branch used against a real cluster.
    api = mock_kube_client.node_v1
    for verb in ("create", "read", "list", "patch", "delete"):
        delattr(api, f"{verb}_namespaced_runtime_class")
    return api


@pytest.mark.unit
class TestRuntimeClassManager:
    def test_create_runtime_class_minimal(
        self, rc_manager: RuntimeClassManager, node_api: MagicMock
    ) -> None:
        rc_manager.create_runtime_class("gvisor", "runsc")
        call_kwargs = node_api.create_runtime_class.call_args.kwargs
        assert call_kwargs["body"]["handler"] == "runsc"

    def test_create_runtime_class_with_overhead_and_scheduling(
        self, rc_manager: RuntimeClassManager, node_api: MagicMock
    ) -> None:
        rc_manager.create_runtime_class(
            "gvisor",
            "runsc",
            overhead={"podFixed": {"cpu": "250m"}},
            scheduling={"nodeSelector": {"runtime": "gvisor"}},
            labels={"tier": "secure"},
        )
        call_kwargs = node_api.create_runtime_class.call_args.kwargs
        body = call_kwargs["body"]
        assert body["overhead"]["podFixed"]["cpu"] == "250m"
        assert body["scheduling"]["nodeSelector"]["runtime"] == "gvisor"

    def test_get_runtime_class(
        self, rc_manager: RuntimeClassManager, node_api: MagicMock
    ) -> None:
        node_api.read_runtime_class.return_value = "rc-obj"
        assert rc_manager.get_runtime_class("gvisor") == "rc-obj"

    def test_list_runtime_classes(
        self, rc_manager: RuntimeClassManager, node_api: MagicMock
    ) -> None:
        node_api.list_runtime_class.return_value.items = ["a"]
        assert rc_manager.list_runtime_classes() == ["a"]

    def test_delete_runtime_class(
        self, rc_manager: RuntimeClassManager, node_api: MagicMock
    ) -> None:
        rc_manager.delete_runtime_class("gvisor")
        node_api.delete_runtime_class.assert_called_once()

    def test_kind_and_api_version(self, rc_manager: RuntimeClassManager) -> None:
        assert rc_manager._kind() == "RuntimeClass"
        assert rc_manager._api_version() == "node.k8s.io/v1"
        assert rc_manager._resource_name() == "runtime_class"
        assert rc_manager.default_namespace == ""


@pytest.fixture
def lease_manager(mock_kube_client: MagicMock) -> LeaseManager:
    return LeaseManager(kube_client=mock_kube_client)


@pytest.fixture
def coordination_api(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.coordination_v1


@pytest.mark.unit
class TestLeaseManager:
    def test_get_lease_uses_default_namespace(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        coordination_api.read_namespaced_lease.return_value = "lease-obj"
        assert lease_manager.get_lease("leader") == "lease-obj"
        kwargs = coordination_api.read_namespaced_lease.call_args.kwargs
        assert kwargs["namespace"] == "kube-system"

    def test_get_lease_with_explicit_namespace(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        coordination_api.read_namespaced_lease.return_value = "lease-obj"
        lease_manager.get_lease("leader", namespace="default")
        kwargs = coordination_api.read_namespaced_lease.call_args.kwargs
        assert kwargs["namespace"] == "default"

    def test_list_leases(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        coordination_api.list_namespaced_lease.return_value.items = ["a"]
        assert lease_manager.list_leases() == ["a"]

    def test_delete_lease(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        lease_manager.delete_lease("leader")
        coordination_api.delete_namespaced_lease.assert_called_once()

    def test_get_holder_identity(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        lease = MagicMock()
        lease.spec.holder_identity = "pod-abc"
        coordination_api.read_namespaced_lease.return_value = lease
        assert lease_manager.get_holder_identity("leader") == "pod-abc"

    def test_get_holder_identity_none_without_spec(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        lease = MagicMock()
        lease.spec = None
        coordination_api.read_namespaced_lease.return_value = lease
        assert lease_manager.get_holder_identity("leader") is None

    def test_is_expired_true_without_spec(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        lease = MagicMock()
        lease.spec = None
        coordination_api.read_namespaced_lease.return_value = lease
        assert lease_manager.is_expired("leader") is True

    def test_is_expired_true_without_renew_time(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        lease = MagicMock()
        lease.spec.renew_time = None
        coordination_api.read_namespaced_lease.return_value = lease
        assert lease_manager.is_expired("leader") is True

    def test_is_expired_false_with_renew_time(
        self, lease_manager: LeaseManager, coordination_api: MagicMock
    ) -> None:
        lease = MagicMock()
        lease.spec.renew_time = "2026-01-01T00:00:00Z"
        coordination_api.read_namespaced_lease.return_value = lease
        assert lease_manager.is_expired("leader") is False

    def test_kind_and_api_version(self, lease_manager: LeaseManager) -> None:
        assert lease_manager._kind() == "Lease"
        assert lease_manager._api_version() == "coordination.k8s.io/v1"
        assert lease_manager.default_namespace == "kube-system"
