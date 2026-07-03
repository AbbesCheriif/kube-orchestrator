"""Unit tests for kube_orchestrator.resources.workloads._builders.affinity_builder."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.workloads._builders.affinity_builder import (
    AffinityBuilder,
)


@pytest.mark.unit
class TestAffinityBuilder:
    def test_empty_builder_returns_empty_dict(self) -> None:
        assert AffinityBuilder().build() == {}

    def test_required_node_affinity(self) -> None:
        affinity = AffinityBuilder().required_node_affinity(
            "disktype", "In", ["ssd"]
        ).build()
        terms = affinity["nodeAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"
        ]["nodeSelectorTerms"]
        assert terms[0]["matchExpressions"][0]["key"] == "disktype"

    def test_preferred_node_affinity(self) -> None:
        affinity = AffinityBuilder().preferred_node_affinity(
            "zone", "In", ["us-east"], weight=5
        ).build()
        preferred = affinity["nodeAffinity"][
            "preferredDuringSchedulingIgnoredDuringExecution"
        ]
        assert preferred[0]["weight"] == 5

    def test_required_pod_affinity_with_namespaces(self) -> None:
        affinity = AffinityBuilder().required_pod_affinity(
            {"matchLabels": {"app": "web"}},
            "kubernetes.io/hostname",
            namespaces=["default"],
        ).build()
        term = affinity["podAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"
        ][0]
        assert term["namespaces"] == ["default"]

    def test_required_pod_affinity_without_namespaces(self) -> None:
        affinity = AffinityBuilder().required_pod_affinity(
            {"matchLabels": {"app": "web"}}, "kubernetes.io/hostname"
        ).build()
        term = affinity["podAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"
        ][0]
        assert "namespaces" not in term

    def test_preferred_pod_affinity(self) -> None:
        affinity = AffinityBuilder().preferred_pod_affinity(
            {"matchLabels": {"app": "web"}},
            "kubernetes.io/hostname",
            namespaces=["prod"],
            weight=10,
        ).build()
        preferred = affinity["podAffinity"][
            "preferredDuringSchedulingIgnoredDuringExecution"
        ][0]
        assert preferred["weight"] == 10
        assert preferred["podAffinityTerm"]["namespaces"] == ["prod"]

    def test_required_pod_anti_affinity(self) -> None:
        affinity = AffinityBuilder().required_pod_anti_affinity(
            {"matchLabels": {"app": "web"}},
            "kubernetes.io/hostname",
            namespaces=["default"],
        ).build()
        term = affinity["podAntiAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"
        ][0]
        assert term["namespaces"] == ["default"]

    def test_preferred_pod_anti_affinity_with_namespaces(self) -> None:
        affinity = AffinityBuilder().preferred_pod_anti_affinity(
            {"matchLabels": {"app": "web"}},
            "kubernetes.io/hostname",
            namespaces=["default"],
            weight=3,
        ).build()
        preferred = affinity["podAntiAffinity"][
            "preferredDuringSchedulingIgnoredDuringExecution"
        ][0]
        assert preferred["weight"] == 3
        assert preferred["podAffinityTerm"]["namespaces"] == ["default"]

    def test_combines_all_affinity_types(self) -> None:
        affinity = (
            AffinityBuilder()
            .required_node_affinity("disktype", "In", ["ssd"])
            .required_pod_affinity({"matchLabels": {}}, "kubernetes.io/hostname")
            .required_pod_anti_affinity({"matchLabels": {}}, "kubernetes.io/hostname")
            .build()
        )
        assert set(affinity.keys()) == {
            "nodeAffinity",
            "podAffinity",
            "podAntiAffinity",
        }
