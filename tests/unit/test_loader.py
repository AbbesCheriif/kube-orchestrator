"""Unit tests for ManifestLoader."""
from __future__ import annotations

import pytest

from kube_orchestrator.manifest.loader import load_file, load_string, validate_yaml_syntax


@pytest.mark.unit
class TestLoadString:
    def test_single_doc(self) -> None:
        content = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test\n"
        result = load_string(content)
        assert len(result) == 1
        assert result[0]["kind"] == "Pod"

    def test_multi_doc(self) -> None:
        content = (
            "apiVersion: v1\nkind: Pod\nmetadata:\n  name: pod1\n"
            "---\n"
            "apiVersion: v1\nkind: Service\nmetadata:\n  name: svc1\n"
        )
        result = load_string(content)
        assert len(result) == 2
        assert result[0]["kind"] == "Pod"
        assert result[1]["kind"] == "Service"

    def test_empty_string_returns_empty_list(self) -> None:
        result = load_string("")
        assert result == []

    def test_invalid_yaml_raises(self) -> None:
        from kube_orchestrator.core.exceptions import ManifestParseError

        with pytest.raises(ManifestParseError):
            load_string("key: [unclosed bracket")


@pytest.mark.unit
class TestLoadFile:
    def test_load_yaml_file(self, tmp_path) -> None:
        manifest_file = tmp_path / "pod.yaml"
        manifest_file.write_text("apiVersion: v1\nkind: Pod\nmetadata:\n  name: test\n")
        result = load_file(str(manifest_file))
        assert len(result) == 1
        assert result[0]["metadata"]["name"] == "test"

    def test_load_multi_doc_file(self, tmp_path) -> None:
        manifest_file = tmp_path / "multi.yaml"
        manifest_file.write_text(
            "apiVersion: v1\nkind: Pod\nmetadata:\n  name: p1\n"
            "---\n"
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: cm1\n"
        )
        result = load_file(str(manifest_file))
        assert len(result) == 2

    def test_nonexistent_file_raises(self) -> None:
        from kube_orchestrator.core.exceptions import ManifestParseError

        with pytest.raises(ManifestParseError):
            load_file("/nonexistent/path/manifest.yaml")


@pytest.mark.unit
class TestValidateYamlSyntax:
    def test_valid_yaml_no_errors(self) -> None:
        errors = validate_yaml_syntax("key: value\nlist:\n  - a\n  - b\n")
        assert errors == []

    def test_invalid_yaml_returns_errors(self) -> None:
        errors = validate_yaml_syntax("key: [unclosed")
        assert len(errors) > 0
