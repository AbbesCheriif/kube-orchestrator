from __future__ import annotations

from typing import Any


class NodeAffinityBuilder:
    def __init__(self) -> None:
        self._required: list[dict[str, Any]] = []
        self._preferred: list[dict[str, Any]] = []

    def required_during_scheduling(
        self,
        key: str,
        operator: str,
        values: list[str],
    ) -> NodeAffinityBuilder:
        self._required.append(
            {"matchExpressions": [{"key": key, "operator": operator, "values": values}]}
        )
        return self

    def preferred_during_scheduling(
        self,
        key: str,
        operator: str,
        values: list[str],
        weight: int = 1,
    ) -> NodeAffinityBuilder:
        self._preferred.append(
            {
                "weight": weight,
                "preference": {
                    "matchExpressions": [
                        {"key": key, "operator": operator, "values": values}
                    ]
                },
            }
        )
        return self

    def build(self) -> dict[str, Any]:
        affinity: dict[str, Any] = {}
        if self._required:
            affinity["requiredDuringSchedulingIgnoredDuringExecution"] = {
                "nodeSelectorTerms": self._required
            }
        if self._preferred:
            affinity["preferredDuringSchedulingIgnoredDuringExecution"] = (
                self._preferred
            )
        return affinity


class PodAffinityBuilder:
    def __init__(self) -> None:
        self._required: list[dict[str, Any]] = []
        self._preferred: list[dict[str, Any]] = []

    def required(
        self,
        label_selector: dict[str, Any],
        topology_key: str,
        namespaces: list[str] | None = None,
        namespace_selector: dict[str, Any] | None = None,
    ) -> PodAffinityBuilder:
        term: dict[str, Any] = {
            "labelSelector": label_selector,
            "topologyKey": topology_key,
        }
        if namespaces:
            term["namespaces"] = namespaces
        if namespace_selector:
            term["namespaceSelector"] = namespace_selector
        self._required.append(term)
        return self

    def preferred(
        self,
        weight: int,
        label_selector: dict[str, Any],
        topology_key: str,
        namespaces: list[str] | None = None,
        namespace_selector: dict[str, Any] | None = None,
    ) -> PodAffinityBuilder:
        term: dict[str, Any] = {
            "labelSelector": label_selector,
            "topologyKey": topology_key,
        }
        if namespaces:
            term["namespaces"] = namespaces
        if namespace_selector:
            term["namespaceSelector"] = namespace_selector
        self._preferred.append({"weight": weight, "podAffinityTerm": term})
        return self

    def build(self) -> dict[str, Any]:
        affinity: dict[str, Any] = {}
        if self._required:
            affinity["requiredDuringSchedulingIgnoredDuringExecution"] = self._required
        if self._preferred:
            affinity["preferredDuringSchedulingIgnoredDuringExecution"] = (
                self._preferred
            )
        return affinity


class TopologySpreadBuilder:
    def __init__(self) -> None:
        self._constraints: list[dict[str, Any]] = []

    def add_constraint(
        self,
        max_skew: int,
        topology_key: str,
        when_unsatisfiable: str,
        label_selector: dict[str, Any],
        min_domains: int | None = None,
        node_affinity_policy: str | None = None,
        node_taints_policy: str | None = None,
        match_label_keys: list[str] | None = None,
    ) -> TopologySpreadBuilder:
        constraint: dict[str, Any] = {
            "maxSkew": max_skew,
            "topologyKey": topology_key,
            "whenUnsatisfiable": when_unsatisfiable,
            "labelSelector": label_selector,
        }
        if min_domains is not None:
            constraint["minDomains"] = min_domains
        if node_affinity_policy:
            constraint["nodeAffinityPolicy"] = node_affinity_policy
        if node_taints_policy:
            constraint["nodeTaintsPolicy"] = node_taints_policy
        if match_label_keys:
            constraint["matchLabelKeys"] = match_label_keys
        self._constraints.append(constraint)
        return self

    def build(self) -> list[dict[str, Any]]:
        return self._constraints


def build_node_selector(labels: dict[str, str]) -> dict[str, str]:
    return labels


def build_toleration(
    key: str,
    operator: str,
    value: str | None = None,
    effect: str | None = None,
    toleration_seconds: int | None = None,
) -> dict[str, Any]:
    toleration: dict[str, Any] = {"key": key, "operator": operator}
    if value is not None:
        toleration["value"] = value
    if effect is not None:
        toleration["effect"] = effect
    if toleration_seconds is not None:
        toleration["tolerationSeconds"] = toleration_seconds
    return toleration


def tolerate_all() -> dict[str, Any]:
    return {"operator": "Exists"}


def tolerate_masters() -> dict[str, Any]:
    return {
        "key": "node-role.kubernetes.io/control-plane",
        "operator": "Exists",
        "effect": "NoSchedule",
    }
