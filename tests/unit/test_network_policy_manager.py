"""Unit tests for NetworkPolicyManager."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.networking.network_policy import NetworkPolicyManager


@pytest.fixture
def np_manager(mock_kube_client: MagicMock) -> NetworkPolicyManager:
    return NetworkPolicyManager(kube_client=mock_kube_client)


@pytest.mark.unit
class TestNetworkPolicyManager:
    def test_deny_all_ingress(self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock) -> None:
        mock_networking_v1.create_namespaced_network_policy.return_value = MagicMock()
        np_manager.deny_all_ingress("deny-all", "default", pod_selector={})
        call_args = mock_networking_v1.create_namespaced_network_policy.call_args
        body = call_args[0][1] if call_args[0] else call_args[1].get("body")
        assert "Ingress" in body["spec"]["policyTypes"]
        assert body["spec"]["ingress"] == []

    def test_allow_all_ingress(self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock) -> None:
        mock_networking_v1.create_namespaced_network_policy.return_value = MagicMock()
        np_manager.allow_all_ingress("allow-all", "default", pod_selector={})
        call_args = mock_networking_v1.create_namespaced_network_policy.call_args
        body = call_args[0][1] if call_args[0] else call_args[1].get("body")
        assert body["spec"]["ingress"] == [{}]

    def test_deny_all_egress(self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock) -> None:
        mock_networking_v1.create_namespaced_network_policy.return_value = MagicMock()
        np_manager.deny_all_egress("deny-egress", "default", pod_selector={})
        call_args = mock_networking_v1.create_namespaced_network_policy.call_args
        body = call_args[0][1] if call_args[0] else call_args[1].get("body")
        assert "Egress" in body["spec"]["policyTypes"]
