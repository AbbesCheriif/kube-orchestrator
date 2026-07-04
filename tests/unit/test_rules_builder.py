"""Unit tests for kube_orchestrator.resources.rbac._builders.rules_builder."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.rbac._builders.rules_builder import RulesBuilder


@pytest.mark.unit
class TestRulesBuilder:
    def test_empty_builder_returns_empty_list(self) -> None:
        assert RulesBuilder().build() == []

    def test_allow_pods_default_verbs(self) -> None:
        rules = RulesBuilder().allow_pods().build()
        assert rules[0]["apiGroups"] == [""]
        assert "pods" in rules[0]["resources"]
        assert rules[0]["verbs"] == ["get", "list", "watch"]

    def test_allow_pods_custom_verbs(self) -> None:
        rules = RulesBuilder().allow_pods(verbs=["get"]).build()
        assert rules[0]["verbs"] == ["get"]

    def test_allow_deployments(self) -> None:
        rules = RulesBuilder().allow_deployments().build()
        assert rules[0]["apiGroups"] == ["apps"]
        assert "deployments" in rules[0]["resources"]

    def test_allow_services(self) -> None:
        rules = RulesBuilder().allow_services().build()
        assert rules[0]["resources"] == ["services", "endpoints"]

    def test_allow_configmaps(self) -> None:
        rules = RulesBuilder().allow_configmaps().build()
        assert rules[0]["resources"] == ["configmaps"]

    def test_allow_secrets(self) -> None:
        rules = RulesBuilder().allow_secrets().build()
        assert rules[0]["resources"] == ["secrets"]

    def test_allow_all(self) -> None:
        rules = RulesBuilder().allow_all().build()
        assert rules[0]["apiGroups"] == ["*"]
        assert rules[0]["resources"] == ["*"]

    def test_custom_rule_with_resource_names(self) -> None:
        rules = (
            RulesBuilder()
            .custom(["apps"], ["deployments"], ["get"], resource_names=["web"])
            .build()
        )
        assert rules[0]["resourceNames"] == ["web"]

    def test_custom_rule_without_resource_names(self) -> None:
        rules = RulesBuilder().custom(["apps"], ["deployments"], ["get"]).build()
        assert "resourceNames" not in rules[0]

    def test_read_only(self) -> None:
        rules = RulesBuilder().read_only().build()
        assert rules[0]["verbs"] == ["get", "list", "watch"]

    def test_read_write(self) -> None:
        rules = RulesBuilder().read_write().build()
        assert rules[0]["verbs"] == [
            "get",
            "list",
            "watch",
            "create",
            "update",
            "patch",
        ]

    def test_admin(self) -> None:
        rules = RulesBuilder().admin().build()
        assert "delete" in rules[0]["verbs"]
        assert "deletecollection" in rules[0]["verbs"]

    def test_chained_rules_accumulate(self) -> None:
        builder = RulesBuilder().allow_pods().allow_secrets()
        assert len(builder.build()) == 2

    def test_build_returns_a_copy(self) -> None:
        builder = RulesBuilder().allow_pods()
        rules_a = builder.build()
        rules_a.append({"fake": "rule"})
        assert len(builder.build()) == 1
