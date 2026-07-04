"""Unit tests for kube_orchestrator.resources.cluster.affinity."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.cluster.affinity import (
    NodeAffinityBuilder,
    PodAffinityBuilder,
    TopologySpreadBuilder,
    build_node_selector,
    build_toleration,
    tolerate_all,
    tolerate_masters,
)


@pytest.mark.unit
class TestNodeAffinityBuilder:
    def test_empty_builder_returns_empty_dict(self) -> None:
        assert NodeAffinityBuilder().build() == {}

    def test_required_during_scheduling(self) -> None:
        result = NodeAffinityBuilder().required_during_scheduling(
            "disktype", "In", ["ssd"]
        ).build()
        terms = result["requiredDuringSchedulingIgnoredDuringExecution"][
            "nodeSelectorTerms"
        ]
        assert terms[0]["matchExpressions"][0]["key"] == "disktype"

    def test_preferred_during_scheduling(self) -> None:
        result = (
            NodeAffinityBuilder()
            .preferred_during_scheduling("zone", "In", ["us-east"], weight=5)
            .build()
        )
        preferred = result["preferredDuringSchedulingIgnoredDuringExecution"]
        assert preferred[0]["weight"] == 5
        assert preferred[0]["preference"]["matchExpressions"][0]["key"] == "zone"

    def test_chained_required_and_preferred(self) -> None:
        result = (
            NodeAffinityBuilder()
            .required_during_scheduling("disktype", "In", ["ssd"])
            .preferred_during_scheduling("zone", "In", ["us-east"])
            .build()
        )
        assert "requiredDuringSchedulingIgnoredDuringExecution" in result
        assert "preferredDuringSchedulingIgnoredDuringExecution" in result


@pytest.mark.unit
class TestPodAffinityBuilder:
    def test_empty_builder_returns_empty_dict(self) -> None:
        assert PodAffinityBuilder().build() == {}

    def test_required_with_namespaces(self) -> None:
        result = PodAffinityBuilder().required(
            {"matchLabels": {"app": "web"}},
            "kubernetes.io/hostname",
            namespaces=["default"],
            namespace_selector={"matchLabels": {"team": "core"}},
        ).build()
        term = result["requiredDuringSchedulingIgnoredDuringExecution"][0]
        assert term["namespaces"] == ["default"]
        assert term["namespaceSelector"]["matchLabels"] == {"team": "core"}

    def test_required_without_optional_fields(self) -> None:
        result = PodAffinityBuilder().required(
            {"matchLabels": {"app": "web"}}, "kubernetes.io/hostname"
        ).build()
        term = result["requiredDuringSchedulingIgnoredDuringExecution"][0]
        assert "namespaces" not in term
        assert "namespaceSelector" not in term

    def test_preferred_with_weight(self) -> None:
        result = PodAffinityBuilder().preferred(
            10, {"matchLabels": {"app": "web"}}, "kubernetes.io/hostname"
        ).build()
        preferred = result["preferredDuringSchedulingIgnoredDuringExecution"][0]
        assert preferred["weight"] == 10
        assert preferred["podAffinityTerm"]["topologyKey"] == "kubernetes.io/hostname"

    def test_preferred_with_namespaces_and_selector(self) -> None:
        result = PodAffinityBuilder().preferred(
            10,
            {"matchLabels": {"app": "web"}},
            "kubernetes.io/hostname",
            namespaces=["prod"],
            namespace_selector={"matchLabels": {"team": "core"}},
        ).build()
        term = result["preferredDuringSchedulingIgnoredDuringExecution"][0][
            "podAffinityTerm"
        ]
        assert term["namespaces"] == ["prod"]
        assert term["namespaceSelector"]["matchLabels"] == {"team": "core"}


@pytest.mark.unit
class TestTopologySpreadBuilder:
    def test_empty_builder_returns_empty_list(self) -> None:
        assert TopologySpreadBuilder().build() == []

    def test_add_constraint_minimal(self) -> None:
        result = TopologySpreadBuilder().add_constraint(
            1, "zone", "DoNotSchedule", {"matchLabels": {"app": "web"}}
        ).build()
        assert result[0]["maxSkew"] == 1
        assert "minDomains" not in result[0]

    def test_add_constraint_with_all_optional_fields(self) -> None:
        result = TopologySpreadBuilder().add_constraint(
            1,
            "zone",
            "DoNotSchedule",
            {"matchLabels": {"app": "web"}},
            min_domains=2,
            node_affinity_policy="Honor",
            node_taints_policy="Ignore",
            match_label_keys=["pod-template-hash"],
        ).build()
        constraint = result[0]
        assert constraint["minDomains"] == 2
        assert constraint["nodeAffinityPolicy"] == "Honor"
        assert constraint["nodeTaintsPolicy"] == "Ignore"
        assert constraint["matchLabelKeys"] == ["pod-template-hash"]

    def test_multiple_constraints_accumulate(self) -> None:
        builder = TopologySpreadBuilder()
        builder.add_constraint(1, "zone", "DoNotSchedule", {})
        builder.add_constraint(2, "hostname", "ScheduleAnyway", {})
        assert len(builder.build()) == 2


@pytest.mark.unit
class TestModuleFunctions:
    def test_build_node_selector_passthrough(self) -> None:
        assert build_node_selector({"disktype": "ssd"}) == {"disktype": "ssd"}

    def test_build_toleration_minimal(self) -> None:
        result = build_toleration("key1", "Exists")
        assert result == {"key": "key1", "operator": "Exists"}

    def test_build_toleration_with_all_fields(self) -> None:
        result = build_toleration(
            "key1", "Equal", value="value1", effect="NoSchedule", toleration_seconds=30
        )
        assert result == {
            "key": "key1",
            "operator": "Equal",
            "value": "value1",
            "effect": "NoSchedule",
            "tolerationSeconds": 30,
        }

    def test_tolerate_all(self) -> None:
        assert tolerate_all() == {"operator": "Exists"}

    def test_tolerate_masters(self) -> None:
        result = tolerate_masters()
        assert result["key"] == "node-role.kubernetes.io/control-plane"
        assert result["effect"] == "NoSchedule"
