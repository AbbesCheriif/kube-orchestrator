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
    def test_deny_all_ingress(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        mock_networking_v1.create_namespaced_network_policy.return_value = MagicMock()
        np_manager.deny_all_ingress("deny-all", "default", pod_selector={})
        call_args = mock_networking_v1.create_namespaced_network_policy.call_args
        body = call_args[0][1] if call_args[0] else call_args[1].get("body")
        assert "Ingress" in body["spec"]["policyTypes"]
        assert body["spec"]["ingress"] == []

    def test_allow_all_ingress(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        mock_networking_v1.create_namespaced_network_policy.return_value = MagicMock()
        np_manager.allow_all_ingress("allow-all", "default", pod_selector={})
        call_args = mock_networking_v1.create_namespaced_network_policy.call_args
        body = call_args[0][1] if call_args[0] else call_args[1].get("body")
        assert body["spec"]["ingress"] == [{}]

    def test_deny_all_egress(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        mock_networking_v1.create_namespaced_network_policy.return_value = MagicMock()
        np_manager.deny_all_egress("deny-egress", "default", pod_selector={})
        call_args = mock_networking_v1.create_namespaced_network_policy.call_args
        body = call_args[0][1] if call_args[0] else call_args[1].get("body")
        assert "Egress" in body["spec"]["policyTypes"]

    def test_allow_all_egress(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        np_manager.allow_all_egress("allow-egress", "default", pod_selector={})
        call_kwargs = mock_networking_v1.create_namespaced_network_policy.call_args.kwargs
        assert call_kwargs["body"]["spec"]["egress"] == [{}]

    def test_allow_from_namespace(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        np_manager.allow_from_namespace(
            "allow-ns",
            "default",
            pod_selector={},
            from_namespace_selector={"matchLabels": {"team": "core"}},
            ports=[{"port": 80, "protocol": "TCP", "endPort": 90}],
        )
        call_kwargs = mock_networking_v1.create_namespaced_network_policy.call_args.kwargs
        rule = call_kwargs["body"]["spec"]["ingress"][0]
        assert rule["from"][0]["namespaceSelector"]["matchLabels"] == {"team": "core"}
        assert rule["ports"][0]["port"] == 80
        assert rule["ports"][0]["endPort"] == 90

    def test_allow_from_pod(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        np_manager.allow_from_pod(
            "allow-pod",
            "default",
            pod_selector={},
            from_pod_selector={"matchLabels": {"app": "api"}},
            ports=[{"port": 8080}],
        )
        call_kwargs = mock_networking_v1.create_namespaced_network_policy.call_args.kwargs
        rule = call_kwargs["body"]["spec"]["ingress"][0]
        assert rule["from"][0]["podSelector"]["matchLabels"] == {"app": "api"}
        assert rule["ports"][0]["port"] == 8080

    def test_allow_egress_to_ip_block(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        np_manager.allow_egress_to_ip_block(
            "allow-cidr",
            "default",
            pod_selector={},
            cidr="10.0.0.0/24",
            except_cidrs=["10.0.0.1/32"],
            ports=[{"port": 443}],
        )
        call_kwargs = mock_networking_v1.create_namespaced_network_policy.call_args.kwargs
        rule = call_kwargs["body"]["spec"]["egress"][0]
        assert rule["to"][0]["ipBlock"]["cidr"] == "10.0.0.0/24"
        assert rule["to"][0]["ipBlock"]["except"] == ["10.0.0.1/32"]

    def test_get_list_delete_policy(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        mock_networking_v1.read_namespaced_network_policy.return_value = "np-obj"
        assert np_manager.get_policy("deny-all", "default") == "np-obj"

        mock_networking_v1.list_namespaced_network_policy.return_value.items = ["a"]
        assert np_manager.list_policies("default") == ["a"]

        np_manager.delete_policy("deny-all", "default")
        mock_networking_v1.delete_namespaced_network_policy.assert_called_once()

    def test_kind_and_api_version(self, np_manager: NetworkPolicyManager) -> None:
        assert np_manager._kind() == "NetworkPolicy"
        assert np_manager._api_version() == "networking.k8s.io/v1"
        assert np_manager._resource_name() == "network_policy"


@pytest.mark.unit
class TestValidatePolicy:
    def test_valid_policy_has_no_errors(self, np_manager: NetworkPolicyManager) -> None:
        policy = {
            "spec": {
                "podSelector": {},
                "policyTypes": ["Ingress"],
                "ingress": [{"from": [{"podSelector": {}}], "ports": [{"protocol": "TCP", "port": 80}]}],
            }
        }
        assert np_manager.validate_policy(policy) == []

    def test_missing_pod_selector(self, np_manager: NetworkPolicyManager) -> None:
        errors = np_manager.validate_policy({"spec": {"policyTypes": []}})
        assert "spec.podSelector is required" in errors

    def test_invalid_policy_type(self, np_manager: NetworkPolicyManager) -> None:
        errors = np_manager.validate_policy(
            {"spec": {"podSelector": {}, "policyTypes": ["Bogus"]}}
        )
        assert any("invalid policyType" in e for e in errors)

    def test_ingress_type_without_ingress_spec(
        self, np_manager: NetworkPolicyManager
    ) -> None:
        errors = np_manager.validate_policy(
            {"spec": {"podSelector": {}, "policyTypes": ["Ingress"]}}
        )
        assert any("spec.ingress is missing" in e for e in errors)

    def test_egress_type_without_egress_spec(
        self, np_manager: NetworkPolicyManager
    ) -> None:
        errors = np_manager.validate_policy(
            {"spec": {"podSelector": {}, "policyTypes": ["Egress"]}}
        )
        assert any("spec.egress is missing" in e for e in errors)

    def test_invalid_peer_keys(self, np_manager: NetworkPolicyManager) -> None:
        policy = {
            "spec": {
                "podSelector": {},
                "policyTypes": ["Ingress"],
                "ingress": [{"from": [{"bogusKey": {}}]}],
            }
        }
        errors = np_manager.validate_policy(policy)
        assert any("unknown peer keys" in e for e in errors)

    def test_ip_block_without_cidr(self, np_manager: NetworkPolicyManager) -> None:
        policy = {
            "spec": {
                "podSelector": {},
                "policyTypes": ["Egress"],
                "egress": [{"to": [{"ipBlock": {}}]}],
            }
        }
        errors = np_manager.validate_policy(policy)
        assert any("'cidr' is required" in e for e in errors)

    def test_invalid_port_protocol(self, np_manager: NetworkPolicyManager) -> None:
        policy = {
            "spec": {
                "podSelector": {},
                "policyTypes": ["Ingress"],
                "ingress": [{"ports": [{"protocol": "BOGUS"}]}],
            }
        }
        errors = np_manager.validate_policy(policy)
        assert any("is not valid" in e for e in errors)

    def test_end_port_without_port(self, np_manager: NetworkPolicyManager) -> None:
        policy = {
            "spec": {
                "podSelector": {},
                "policyTypes": ["Egress"],
                "egress": [{"ports": [{"endPort": 9000}]}],
            }
        }
        errors = np_manager.validate_policy(policy)
        assert any("'endPort' requires 'port'" in e for e in errors)


@pytest.mark.unit
class TestDetectConflicts:
    def test_detects_overlap_between_wildcard_selectors(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        p1 = MagicMock()
        p1.metadata.name = "policy-a"
        p1.spec.pod_selector.match_labels = {}
        p2 = MagicMock()
        p2.metadata.name = "policy-b"
        p2.spec.pod_selector.match_labels = {}
        mock_networking_v1.list_namespaced_network_policy.return_value.items = [p1, p2]

        conflicts = np_manager.detect_conflicts("default")

        assert conflicts == [
            {"policy_a": "policy-a", "policy_b": "policy-b", "reason": "overlapping podSelectors"}
        ]

    def test_no_conflict_for_disjoint_selectors(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        p1 = MagicMock()
        p1.spec.pod_selector.match_labels = {"app": "web"}
        p2 = MagicMock()
        p2.spec.pod_selector.match_labels = {"app": "api"}
        mock_networking_v1.list_namespaced_network_policy.return_value.items = [p1, p2]

        assert np_manager.detect_conflicts("default") == []

    def test_conflict_for_shared_label(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        p1 = MagicMock()
        p1.metadata.name = "policy-a"
        p1.spec.pod_selector.match_labels = {"app": "web", "tier": "frontend"}
        p2 = MagicMock()
        p2.metadata.name = "policy-b"
        p2.spec.pod_selector.match_labels = {"app": "web"}
        mock_networking_v1.list_namespaced_network_policy.return_value.items = [p1, p2]

        conflicts = np_manager.detect_conflicts("default")
        assert len(conflicts) == 1


@pytest.mark.unit
class TestGetPoliciesForPod:
    def test_matches_policy_with_matching_labels(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        policy = MagicMock()
        policy.spec.pod_selector.match_labels = {"app": "web"}
        mock_networking_v1.list_namespaced_network_policy.return_value.items = [policy]

        result = np_manager.get_policies_for_pod("default", {"app": "web", "extra": "x"})
        assert result == [policy]

    def test_wildcard_selector_matches_any_pod(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        policy = MagicMock()
        policy.spec.pod_selector.match_labels = {}
        mock_networking_v1.list_namespaced_network_policy.return_value.items = [policy]

        assert np_manager.get_policies_for_pod("default", {}) == [policy]

    def test_skips_policy_without_pod_selector(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        policy = MagicMock()
        policy.spec.pod_selector = None
        mock_networking_v1.list_namespaced_network_policy.return_value.items = [policy]

        assert np_manager.get_policies_for_pod("default", {"app": "web"}) == []

    def test_skips_policy_without_spec(
        self, np_manager: NetworkPolicyManager, mock_networking_v1: MagicMock
    ) -> None:
        policy = MagicMock()
        policy.spec = None
        mock_networking_v1.list_namespaced_network_policy.return_value.items = [policy]

        assert np_manager.get_policies_for_pod("default", {"app": "web"}) == []
