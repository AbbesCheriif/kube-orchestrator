"""Unit tests for ManifestValidator."""

from __future__ import annotations

import pytest

from kube_orchestrator.manifest.validator import (
    DEPENDENCY_ORDER,
    group_by_kind,
    group_by_namespace,
    order_by_dependency,
    validate_manifest,
    validate_required_fields,
)


@pytest.mark.unit
class TestValidateRequiredFields:
    def test_valid_manifest_no_errors(self) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "test"},
        }
        errors = validate_required_fields(manifest)
        assert errors == []

    def test_missing_api_version(self) -> None:
        manifest = {"kind": "Pod", "metadata": {"name": "test"}}
        errors = validate_required_fields(manifest)
        assert any("apiVersion" in e for e in errors)

    def test_missing_kind(self) -> None:
        manifest = {"apiVersion": "v1", "metadata": {"name": "test"}}
        errors = validate_required_fields(manifest)
        assert any("kind" in e for e in errors)

    def test_missing_name(self) -> None:
        manifest = {"apiVersion": "v1", "kind": "Pod", "metadata": {}}
        errors = validate_required_fields(manifest)
        assert any("name" in e for e in errors)


@pytest.mark.unit
class TestValidateManifest:
    def test_valid_manifest(self) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "test"},
            "spec": {"containers": [{"name": "app", "image": "nginx"}]},
        }
        errors = validate_manifest(manifest)
        assert isinstance(errors, list)

    def test_invalid_manifest_returns_errors(self) -> None:
        errors = validate_manifest({})
        assert len(errors) > 0


@pytest.mark.unit
class TestDependencyOrdering:
    def test_namespace_before_deployment(self) -> None:
        manifests = [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "app", "namespace": "ns"},
            },
            {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "ns"}},
        ]
        ordered = order_by_dependency(manifests)
        kinds = [m["kind"] for m in ordered]
        assert kinds.index("Namespace") < kinds.index("Deployment")

    def test_configmap_before_deployment(self) -> None:
        manifests = [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "app"},
            },
            {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "config"}},
        ]
        ordered = order_by_dependency(manifests)
        kinds = [m["kind"] for m in ordered]
        assert kinds.index("ConfigMap") < kinds.index("Deployment")

    def test_dependency_order_list_is_ordered(self) -> None:
        assert DEPENDENCY_ORDER.index("Namespace") < DEPENDENCY_ORDER.index(
            "Deployment"
        )
        assert DEPENDENCY_ORDER.index("ConfigMap") < DEPENDENCY_ORDER.index(
            "Deployment"
        )


@pytest.mark.unit
class TestGroupBy:
    def test_group_by_namespace(self) -> None:
        manifests = [
            {"kind": "Pod", "metadata": {"name": "p1", "namespace": "ns1"}},
            {"kind": "Pod", "metadata": {"name": "p2", "namespace": "ns2"}},
            {"kind": "Service", "metadata": {"name": "s1", "namespace": "ns1"}},
        ]
        groups = group_by_namespace(manifests)
        assert len(groups["ns1"]) == 2
        assert len(groups["ns2"]) == 1

    def test_group_by_kind(self) -> None:
        manifests = [
            {"kind": "Pod", "metadata": {"name": "p1"}},
            {"kind": "Pod", "metadata": {"name": "p2"}},
            {"kind": "Service", "metadata": {"name": "s1"}},
        ]
        groups = group_by_kind(manifests)
        assert len(groups["Pod"]) == 2
        assert len(groups["Service"]) == 1
