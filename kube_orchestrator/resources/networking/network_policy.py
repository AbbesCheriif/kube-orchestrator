"""NetworkPolicyManager — full NetworkPolicy spec coverage."""

from __future__ import annotations

from typing import Any

from kubernetes.client import (
    NetworkingV1Api,
    V1NetworkPolicy,
)

from kube_orchestrator.core.exceptions import parse_api_exception
from kube_orchestrator.resources.base import BaseResourceManager
from kube_orchestrator.resources.helpers import build_metadata


class NetworkPolicyManager(BaseResourceManager[V1NetworkPolicy]):
    """Manage Kubernetes NetworkPolicy resources with full spec coverage."""

    def _get_api(self) -> NetworkingV1Api:
        return self.client.networking_v1

    def _kind(self) -> str:
        return "NetworkPolicy"

    def _api_version(self) -> str:
        return "networking.k8s.io/v1"

    # ------------------------------------------------------------------
    # Full-spec factory
    # ------------------------------------------------------------------

    def create_policy(
        self,
        name: str,
        namespace: str,
        pod_selector: dict,
        policy_types: list[str],
        ingress_rules: list[dict] | None = None,
        egress_rules: list[dict] | None = None,
        labels: dict | None = None,
    ) -> V1NetworkPolicy:
        """Create a NetworkPolicy with full spec.

        Each ingress/egress rule dict supports:
          - ports: list of {port, endPort, protocol}
          - from/to: list of {ipBlock, namespaceSelector, podSelector}
        """
        spec: dict[str, Any] = {
            "podSelector": pod_selector,
            "policyTypes": policy_types,
        }

        if ingress_rules is not None:
            spec["ingress"] = [self._build_ingress_rule(r) for r in ingress_rules]
        if egress_rules is not None:
            spec["egress"] = [self._build_egress_rule(r) for r in egress_rules]

        manifest: dict[str, Any] = {
            "apiVersion": self._api_version(),
            "kind": self._kind(),
            "metadata": build_metadata(name=name, namespace=namespace, labels=labels),
            "spec": spec,
        }
        return self.create(manifest, namespace)

    # ------------------------------------------------------------------
    # Convenience policy factories
    # ------------------------------------------------------------------

    def allow_all_ingress(
        self,
        name: str,
        namespace: str,
        pod_selector: dict,
    ) -> V1NetworkPolicy:
        """Allow all ingress traffic to pods matching pod_selector."""
        return self.create_policy(
            name=name,
            namespace=namespace,
            pod_selector=pod_selector,
            policy_types=["Ingress"],
            ingress_rules=[{}],
        )

    def deny_all_ingress(
        self,
        name: str,
        namespace: str,
        pod_selector: dict,
    ) -> V1NetworkPolicy:
        """Deny all ingress traffic to pods matching pod_selector."""
        return self.create_policy(
            name=name,
            namespace=namespace,
            pod_selector=pod_selector,
            policy_types=["Ingress"],
            ingress_rules=[],
        )

    def allow_all_egress(
        self,
        name: str,
        namespace: str,
        pod_selector: dict,
    ) -> V1NetworkPolicy:
        """Allow all egress traffic from pods matching pod_selector."""
        return self.create_policy(
            name=name,
            namespace=namespace,
            pod_selector=pod_selector,
            policy_types=["Egress"],
            egress_rules=[{}],
        )

    def deny_all_egress(
        self,
        name: str,
        namespace: str,
        pod_selector: dict,
    ) -> V1NetworkPolicy:
        """Deny all egress traffic from pods matching pod_selector."""
        return self.create_policy(
            name=name,
            namespace=namespace,
            pod_selector=pod_selector,
            policy_types=["Egress"],
            egress_rules=[],
        )

    def allow_from_namespace(
        self,
        name: str,
        namespace: str,
        pod_selector: dict,
        from_namespace_selector: dict,
        ports: list[dict] | None = None,
    ) -> V1NetworkPolicy:
        """Allow ingress from all pods in namespaces matching from_namespace_selector."""
        rule: dict[str, Any] = {"from": [{"namespaceSelector": from_namespace_selector}]}
        if ports:
            rule["ports"] = ports
        return self.create_policy(
            name=name,
            namespace=namespace,
            pod_selector=pod_selector,
            policy_types=["Ingress"],
            ingress_rules=[rule],
        )

    def allow_from_pod(
        self,
        name: str,
        namespace: str,
        pod_selector: dict,
        from_pod_selector: dict,
        ports: list[dict] | None = None,
    ) -> V1NetworkPolicy:
        """Allow ingress from pods matching from_pod_selector in the same namespace."""
        rule: dict[str, Any] = {"from": [{"podSelector": from_pod_selector}]}
        if ports:
            rule["ports"] = ports
        return self.create_policy(
            name=name,
            namespace=namespace,
            pod_selector=pod_selector,
            policy_types=["Ingress"],
            ingress_rules=[rule],
        )

    def allow_egress_to_ip_block(
        self,
        name: str,
        namespace: str,
        pod_selector: dict,
        cidr: str,
        except_cidrs: list[str] | None = None,
        ports: list[dict] | None = None,
    ) -> V1NetworkPolicy:
        """Allow egress to an IP block (CIDR), optionally excluding sub-ranges."""
        ip_block: dict[str, Any] = {"cidr": cidr}
        if except_cidrs:
            ip_block["except"] = except_cidrs

        rule: dict[str, Any] = {"to": [{"ipBlock": ip_block}]}
        if ports:
            rule["ports"] = ports

        return self.create_policy(
            name=name,
            namespace=namespace,
            pod_selector=pod_selector,
            policy_types=["Egress"],
            egress_rules=[rule],
        )

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def get_policy(self, name: str, namespace: str) -> V1NetworkPolicy:
        return self.get(name, namespace)

    def list_policies(
        self,
        namespace: str,
        label_selector: str | None = None,
    ) -> list[V1NetworkPolicy]:
        return self.list(namespace, label_selector=label_selector)

    def delete_policy(self, name: str, namespace: str) -> None:
        self.delete(name, namespace)

    # ------------------------------------------------------------------
    # Analysis helpers
    # ------------------------------------------------------------------

    def validate_policy(self, policy: dict) -> list[str]:
        """Return a list of validation error messages for a raw policy dict.

        Checks required fields, valid policyTypes, and peer consistency.
        """
        errors: list[str] = []
        spec = policy.get("spec", {})

        if "podSelector" not in spec:
            errors.append("spec.podSelector is required")

        policy_types = spec.get("policyTypes", [])
        valid_types = {"Ingress", "Egress"}
        for pt in policy_types:
            if pt not in valid_types:
                errors.append(f"invalid policyType '{pt}': must be Ingress or Egress")

        if "Ingress" in policy_types and "ingress" not in spec:
            errors.append("policyTypes includes Ingress but spec.ingress is missing")
        if "Egress" in policy_types and "egress" not in spec:
            errors.append("policyTypes includes Egress but spec.egress is missing")

        for i, rule in enumerate(spec.get("ingress", [])):
            for j, peer in enumerate(rule.get("from", [])):
                errors.extend(self._validate_peer(peer, f"ingress[{i}].from[{j}]"))
            for j, port in enumerate(rule.get("ports", [])):
                errors.extend(self._validate_port(port, f"ingress[{i}].ports[{j}]"))

        for i, rule in enumerate(spec.get("egress", [])):
            for j, peer in enumerate(rule.get("to", [])):
                errors.extend(self._validate_peer(peer, f"egress[{i}].to[{j}]"))
            for j, port in enumerate(rule.get("ports", [])):
                errors.extend(self._validate_port(port, f"egress[{i}].ports[{j}]"))

        return errors

    def detect_conflicts(self, namespace: str) -> list[dict]:
        """Detect overlapping NetworkPolicies in a namespace.

        Returns a list of conflict descriptors: pairs of policy names
        whose podSelectors overlap (both select all pods or share labels).
        """
        policies = self.list_policies(namespace)
        conflicts: list[dict] = []

        for i in range(len(policies)):
            for j in range(i + 1, len(policies)):
                p1 = policies[i]
                p2 = policies[j]
                if self._selectors_overlap(p1, p2):
                    conflicts.append(
                        {
                            "policy_a": getattr(getattr(p1, "metadata", None), "name", ""),
                            "policy_b": getattr(getattr(p2, "metadata", None), "name", ""),
                            "reason": "overlapping podSelectors",
                        }
                    )
        return conflicts

    def get_policies_for_pod(
        self,
        namespace: str,
        pod_labels: dict,
    ) -> list[V1NetworkPolicy]:
        """Return all NetworkPolicies in namespace that select a pod with pod_labels."""
        policies = self.list_policies(namespace)
        matching: list[V1NetworkPolicy] = []
        for policy in policies:
            spec = getattr(policy, "spec", None)
            pod_selector = getattr(spec, "pod_selector", None) if spec else None
            if pod_selector is None:
                continue
            match_labels = getattr(pod_selector, "match_labels", None) or {}
            if not match_labels or self._labels_match(match_labels, pod_labels):
                matching.append(policy)
        return matching

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ports(ports: list[dict]) -> list[dict[str, Any]]:
        result = []
        for p in ports:
            entry: dict[str, Any] = {}
            if "protocol" in p:
                entry["protocol"] = p["protocol"]
            if "port" in p:
                entry["port"] = p["port"]
            if "endPort" in p:
                entry["endPort"] = p["endPort"]
            result.append(entry)
        return result

    @staticmethod
    def _build_peer(peer: dict) -> dict[str, Any]:
        entry: dict[str, Any] = {}
        if "ipBlock" in peer:
            ip_block: dict[str, Any] = {"cidr": peer["ipBlock"]["cidr"]}
            if "except" in peer["ipBlock"]:
                ip_block["except"] = peer["ipBlock"]["except"]
            entry["ipBlock"] = ip_block
        if "namespaceSelector" in peer:
            entry["namespaceSelector"] = peer["namespaceSelector"]
        if "podSelector" in peer:
            entry["podSelector"] = peer["podSelector"]
        return entry

    def _build_ingress_rule(self, rule: dict) -> dict[str, Any]:
        entry: dict[str, Any] = {}
        if "from" in rule:
            entry["from"] = [self._build_peer(p) for p in rule["from"]]
        if "ports" in rule:
            entry["ports"] = self._build_ports(rule["ports"])
        return entry

    def _build_egress_rule(self, rule: dict) -> dict[str, Any]:
        entry: dict[str, Any] = {}
        if "to" in rule:
            entry["to"] = [self._build_peer(p) for p in rule["to"]]
        if "ports" in rule:
            entry["ports"] = self._build_ports(rule["ports"])
        return entry

    @staticmethod
    def _validate_peer(peer: dict, path: str) -> list[str]:
        errors: list[str] = []
        valid_keys = {"ipBlock", "namespaceSelector", "podSelector"}
        unknown = set(peer.keys()) - valid_keys
        if unknown:
            errors.append(f"{path}: unknown peer keys {unknown}")
        if "ipBlock" in peer and "cidr" not in peer["ipBlock"]:
            errors.append(f"{path}.ipBlock: 'cidr' is required")
        return errors

    @staticmethod
    def _validate_port(port: dict, path: str) -> list[str]:
        errors: list[str] = []
        valid_protocols = {"TCP", "UDP", "SCTP"}
        if "protocol" in port and port["protocol"] not in valid_protocols:
            errors.append(
                f"{path}.protocol: '{port['protocol']}' is not valid; "
                f"must be one of {valid_protocols}"
            )
        if "endPort" in port and "port" not in port:
            errors.append(f"{path}: 'endPort' requires 'port' to be set")
        return errors

    @staticmethod
    def _selectors_overlap(p1: V1NetworkPolicy, p2: V1NetworkPolicy) -> bool:
        spec1 = getattr(p1, "spec", None)
        spec2 = getattr(p2, "spec", None)
        sel1 = getattr(spec1, "pod_selector", None) if spec1 else None
        sel2 = getattr(spec2, "pod_selector", None) if spec2 else None
        ml1 = getattr(sel1, "match_labels", None) or {}
        ml2 = getattr(sel2, "match_labels", None) or {}
        # Both select all pods, or one selects all and the other is non-empty
        if not ml1 or not ml2:
            return True
        return bool(set(ml1.items()) & set(ml2.items()))

    @staticmethod
    def _labels_match(selector_labels: dict, pod_labels: dict) -> bool:
        return all(pod_labels.get(k) == v for k, v in selector_labels.items())
