"""Unit tests for ManifestValidator."""

from __future__ import annotations

import pytest

from kube_orchestrator.manifest.validator import (
    DEPENDENCY_ORDER,
    detect_api_version,
    detect_circular_deps,
    group_by_kind,
    group_by_namespace,
    order_by_dependency,
    route_by_kind,
    validate_manifest,
    validate_required_fields,
    validate_spec_for_kind,
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

    def test_metadata_not_a_mapping(self) -> None:
        manifest = {"apiVersion": "v1", "kind": "Pod", "metadata": "not-a-dict"}
        errors = validate_required_fields(manifest)
        assert any("must be a mapping" in e for e in errors)


@pytest.mark.unit
class TestDetectApiVersion:
    def test_returns_api_version(self) -> None:
        assert detect_api_version({"apiVersion": "apps/v1"}) == "apps/v1"

    def test_returns_empty_string_when_missing(self) -> None:
        assert detect_api_version({}) == ""


@pytest.mark.unit
class TestRouteByKind:
    def test_returns_manager_class_for_known_kind(self) -> None:
        from kube_orchestrator.resources.workloads.deployment import DeploymentManager

        manager_cls = route_by_kind({"kind": "Deployment"})
        assert manager_cls is DeploymentManager

    def test_returns_none_for_unknown_kind(self) -> None:
        assert route_by_kind({"kind": "TotallyUnknownKind"}) is None

    def test_returns_none_when_kind_missing(self) -> None:
        assert route_by_kind({}) is None


@pytest.mark.unit
class TestValidateSpecForKind:
    def test_deployment_missing_spec(self) -> None:
        errors = validate_spec_for_kind({"kind": "Deployment"})
        assert any("must have a 'spec'" in e for e in errors)

    def test_deployment_missing_selector_and_template(self) -> None:
        errors = validate_spec_for_kind(
            {"kind": "Deployment", "spec": {"replicas": 1}}
        )
        assert any("selector" in e for e in errors)
        assert any("template" in e for e in errors)

    def test_deployment_valid_spec(self) -> None:
        errors = validate_spec_for_kind(
            {"kind": "Deployment", "spec": {"selector": {}, "template": {}}}
        )
        assert errors == []

    def test_service_missing_spec(self) -> None:
        errors = validate_spec_for_kind({"kind": "Service"})
        assert any("must have a 'spec'" in e for e in errors)

    def test_service_missing_ports(self) -> None:
        errors = validate_spec_for_kind(
            {"kind": "Service", "spec": {"selector": {}}}
        )
        assert any("must have 'ports'" in e for e in errors)

    def test_service_valid_spec(self) -> None:
        errors = validate_spec_for_kind({"kind": "Service", "spec": {"ports": []}})
        assert errors == []

    def test_hpa_missing_spec(self) -> None:
        errors = validate_spec_for_kind({"kind": "HorizontalPodAutoscaler"})
        assert any("must have a 'spec'" in e for e in errors)

    def test_hpa_missing_scale_target_and_max_replicas(self) -> None:
        errors = validate_spec_for_kind(
            {"kind": "HorizontalPodAutoscaler", "spec": {"minReplicas": 1}}
        )
        assert any("scaleTargetRef" in e for e in errors)
        assert any("maxReplicas" in e for e in errors)

    def test_hpa_valid_spec(self) -> None:
        errors = validate_spec_for_kind(
            {
                "kind": "HorizontalPodAutoscaler",
                "spec": {"scaleTargetRef": {}, "maxReplicas": 5},
            }
        )
        assert errors == []

    def test_ingress_missing_spec(self) -> None:
        errors = validate_spec_for_kind({"kind": "Ingress"})
        assert any("must have a 'spec'" in e for e in errors)

    def test_unrecognized_kind_has_no_errors(self) -> None:
        assert validate_spec_for_kind({"kind": "ConfigMap", "spec": {}}) == []


@pytest.mark.unit
class TestDetectCircularDeps:
    def test_returns_empty_list(self) -> None:
        manifests = [
            {"kind": "ConfigMap", "metadata": {"name": "cfg"}},
            {"kind": "HorizontalPodAutoscaler", "metadata": {"name": "hpa"}},
        ]
        assert detect_circular_deps(manifests) == []

    def test_ignores_manifests_without_kind_or_name(self) -> None:
        assert detect_circular_deps([{"metadata": {}}, {}]) == []


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
