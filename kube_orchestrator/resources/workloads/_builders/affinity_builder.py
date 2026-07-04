"""Fluent builder for Kubernetes Affinity rules."""

from __future__ import annotations

from typing import Any


class AffinityBuilder:
    """Fluent interface for building Kubernetes Affinity manifests."""

    def __init__(self) -> None:
        self._node_required: list[dict[str, Any]] = []
        self._node_preferred: list[dict[str, Any]] = []
        self._pod_affinity_required: list[dict[str, Any]] = []
        self._pod_affinity_preferred: list[dict[str, Any]] = []
        self._pod_anti_required: list[dict[str, Any]] = []
        self._pod_anti_preferred: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Node affinity
    # ------------------------------------------------------------------

    def required_node_affinity(
        self,
        key: str,
        operator: str,
        values: list[str],
    ) -> AffinityBuilder:
        self._node_required.append({"key": key, "operator": operator, "values": values})
        return self

    def preferred_node_affinity(
        self,
        key: str,
        operator: str,
        values: list[str],
        weight: int = 1,
    ) -> AffinityBuilder:
        self._node_preferred.append(
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

    # ------------------------------------------------------------------
    # Pod affinity
    # ------------------------------------------------------------------

    def required_pod_affinity(
        self,
        label_selector: dict[str, Any],
        topology_key: str,
        namespaces: list[Any] | None = None,
    ) -> AffinityBuilder:
        term: dict[str, Any] = {
            "labelSelector": label_selector,
            "topologyKey": topology_key,
        }
        if namespaces:
            term["namespaces"] = namespaces
        self._pod_affinity_required.append(term)
        return self

    def preferred_pod_affinity(
        self,
        label_selector: dict[str, Any],
        topology_key: str,
        namespaces: list[Any] | None = None,
        weight: int = 1,
    ) -> AffinityBuilder:
        term: dict[str, Any] = {
            "labelSelector": label_selector,
            "topologyKey": topology_key,
        }
        if namespaces:
            term["namespaces"] = namespaces
        self._pod_affinity_preferred.append({"weight": weight, "podAffinityTerm": term})
        return self

    # ------------------------------------------------------------------
    # Pod anti-affinity
    # ------------------------------------------------------------------

    def required_pod_anti_affinity(
        self,
        label_selector: dict[str, Any],
        topology_key: str,
        namespaces: list[Any] | None = None,
    ) -> AffinityBuilder:
        term: dict[str, Any] = {
            "labelSelector": label_selector,
            "topologyKey": topology_key,
        }
        if namespaces:
            term["namespaces"] = namespaces
        self._pod_anti_required.append(term)
        return self

    def preferred_pod_anti_affinity(
        self,
        label_selector: dict[str, Any],
        topology_key: str,
        namespaces: list[Any] | None = None,
        weight: int = 1,
    ) -> AffinityBuilder:
        term: dict[str, Any] = {
            "labelSelector": label_selector,
            "topologyKey": topology_key,
        }
        if namespaces:
            term["namespaces"] = namespaces
        self._pod_anti_preferred.append({"weight": weight, "podAffinityTerm": term})
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> dict[str, Any]:
        affinity: dict[str, Any] = {}

        if self._node_required or self._node_preferred:
            node_affinity: dict[str, Any] = {}
            if self._node_required:
                node_affinity["requiredDuringSchedulingIgnoredDuringExecution"] = {
                    "nodeSelectorTerms": [{"matchExpressions": self._node_required}]
                }
            if self._node_preferred:
                node_affinity["preferredDuringSchedulingIgnoredDuringExecution"] = (
                    self._node_preferred
                )
            affinity["nodeAffinity"] = node_affinity

        if self._pod_affinity_required or self._pod_affinity_preferred:
            pod_affinity: dict[str, Any] = {}
            if self._pod_affinity_required:
                pod_affinity["requiredDuringSchedulingIgnoredDuringExecution"] = (
                    self._pod_affinity_required
                )
            if self._pod_affinity_preferred:
                pod_affinity["preferredDuringSchedulingIgnoredDuringExecution"] = (
                    self._pod_affinity_preferred
                )
            affinity["podAffinity"] = pod_affinity

        if self._pod_anti_required or self._pod_anti_preferred:
            pod_anti: dict[str, Any] = {}
            if self._pod_anti_required:
                pod_anti["requiredDuringSchedulingIgnoredDuringExecution"] = (
                    self._pod_anti_required
                )
            if self._pod_anti_preferred:
                pod_anti["preferredDuringSchedulingIgnoredDuringExecution"] = (
                    self._pod_anti_preferred
                )
            affinity["podAntiAffinity"] = pod_anti

        return affinity
