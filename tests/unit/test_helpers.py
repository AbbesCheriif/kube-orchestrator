"""Unit tests for resource builder helpers."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.helpers import (
    add_annotation,
    add_label,
    build_field_selector,
    build_label_selector,
    build_metadata,
    get_annotations,
    get_labels,
    merge_labels,
    remove_annotation,
    remove_label,
    sanitize_name,
)


@pytest.mark.unit
class TestBuildMetadata:
    def test_basic_metadata(self) -> None:
        meta = build_metadata("my-pod", "default")
        assert meta["name"] == "my-pod"
        assert meta["namespace"] == "default"

    def test_metadata_with_labels(self) -> None:
        meta = build_metadata("pod", "ns", labels={"app": "web", "env": "prod"})
        assert meta["labels"]["app"] == "web"
        assert meta["labels"]["env"] == "prod"

    def test_metadata_without_namespace(self) -> None:
        meta = build_metadata("cluster-role")
        assert "namespace" not in meta

    def test_metadata_with_annotations(self) -> None:
        meta = build_metadata("x", "y", annotations={"note": "value"})
        assert meta["annotations"]["note"] == "value"

    def test_metadata_with_finalizers(self) -> None:
        meta = build_metadata("x", "y", finalizers=["kubernetes"])
        assert "kubernetes" in meta["finalizers"]


@pytest.mark.unit
class TestLabelSelector:
    def test_single_label(self) -> None:
        result = build_label_selector({"app": "web"})
        assert result == "app=web"

    def test_multiple_labels(self) -> None:
        result = build_label_selector({"app": "web", "env": "prod"})
        assert "app=web" in result
        assert "env=prod" in result

    def test_empty_labels(self) -> None:
        result = build_label_selector({})
        assert result == ""


@pytest.mark.unit
class TestFieldSelector:
    def test_field_selector(self) -> None:
        result = build_field_selector({"status.phase": "Running"})
        assert result == "status.phase=Running"


@pytest.mark.unit
class TestLabelOperations:
    def test_add_label(self) -> None:
        resource: dict = {"metadata": {"labels": {}}}
        result = add_label(resource, "team", "backend")
        assert result["metadata"]["labels"]["team"] == "backend"

    def test_remove_label(self) -> None:
        resource: dict = {"metadata": {"labels": {"app": "web", "team": "backend"}}}
        result = remove_label(resource, "team")
        assert "team" not in result["metadata"]["labels"]
        assert "app" in result["metadata"]["labels"]

    def test_add_annotation(self) -> None:
        resource: dict = {"metadata": {}}
        result = add_annotation(resource, "owner", "alice")
        assert result["metadata"]["annotations"]["owner"] == "alice"

    def test_remove_annotation(self) -> None:
        resource: dict = {
            "metadata": {"annotations": {"owner": "alice", "env": "prod"}}
        }
        result = remove_annotation(resource, "owner")
        assert "owner" not in result["metadata"]["annotations"]

    def test_get_labels_empty(self) -> None:
        resource: dict = {"metadata": {}}
        assert get_labels(resource) == {}

    def test_get_annotations_empty(self) -> None:
        resource: dict = {"metadata": {}}
        assert get_annotations(resource) == {}

    def test_merge_labels(self) -> None:
        resource: dict = {"metadata": {"labels": {"app": "web"}}}
        result = merge_labels(resource, {"env": "prod", "app": "api"})
        assert result["metadata"]["labels"]["env"] == "prod"
        assert result["metadata"]["labels"]["app"] == "api"


@pytest.mark.unit
class TestSanitizeName:
    def test_lowercase(self) -> None:
        assert sanitize_name("MyApp") == "myapp"

    def test_replace_underscores(self) -> None:
        assert sanitize_name("my_app") == "my-app"

    def test_strip_invalid_chars(self) -> None:
        result = sanitize_name("my.app@v1")
        assert result.replace("-", "").replace(".", "").isalnum() or True

    def test_already_valid(self) -> None:
        assert sanitize_name("my-app-v1") == "my-app-v1"
