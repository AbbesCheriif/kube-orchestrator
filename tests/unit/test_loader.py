"""Unit tests for ManifestLoader."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.manifest.loader import (
    detect_encoding,
    load_directory,
    load_file,
    load_multiple_files,
    load_stdin,
    load_string,
    load_url,
    validate_yaml_syntax,
)


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


@pytest.mark.unit
class TestDetectEncoding:
    def test_utf8_default(self, tmp_path) -> None:
        path = tmp_path / "plain.yaml"
        path.write_bytes(b"kind: Pod\n")
        assert detect_encoding(str(path)) == "utf-8"

    def test_utf8_sig_bom(self, tmp_path) -> None:
        path = tmp_path / "bom.yaml"
        path.write_bytes(b"\xef\xbb\xbfkind: Pod\n")
        assert detect_encoding(str(path)) == "utf-8-sig"

    def test_utf16_bom(self, tmp_path) -> None:
        path = tmp_path / "utf16.yaml"
        path.write_bytes(b"\xff\xfek\x00i\x00")
        assert detect_encoding(str(path)) == "utf-16"

    def test_utf16_be_bom(self, tmp_path) -> None:
        path = tmp_path / "utf16be.yaml"
        path.write_bytes(b"\xfe\xff\x00k\x00i")
        assert detect_encoding(str(path)) == "utf-16"

    def test_utf32_bom(self, tmp_path) -> None:
        path = tmp_path / "utf32.yaml"
        path.write_bytes(b"\xff\xfe\x00\x00kind")
        assert detect_encoding(str(path)) == "utf-32"


@pytest.mark.unit
class TestLoadUrl:
    def test_fetches_and_parses_yaml(self) -> None:
        fake_response = MagicMock()
        fake_response.read.return_value = (
            b"apiVersion: v1\nkind: Pod\nmetadata:\n  name: remote\n"
        )
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        with patch(
            "kube_orchestrator.manifest.loader.urlopen", return_value=fake_response
        ):
            result = load_url("https://example.com/pod.yaml")

        assert result[0]["metadata"]["name"] == "remote"

    def test_passes_custom_headers(self) -> None:
        fake_response = MagicMock()
        fake_response.read.return_value = b""
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        with patch(
            "kube_orchestrator.manifest.loader.urlopen", return_value=fake_response
        ) as fake_urlopen:
            load_url("https://example.com/pod.yaml", headers={"Authorization": "x"})
            request = fake_urlopen.call_args.args[0]
            assert request.headers["Authorization"] == "x"

    def test_rejects_non_http_scheme(self) -> None:
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            load_url("file:///etc/passwd")


@pytest.mark.unit
class TestLoadStdin:
    def test_reads_from_stdin(self) -> None:
        with patch("sys.stdin.read", return_value="kind: Pod\nmetadata:\n  name: p\n"):
            result = load_stdin()
        assert result[0]["kind"] == "Pod"


@pytest.mark.unit
class TestLoadDirectory:
    def test_loads_all_yaml_files_non_recursive(self, tmp_path) -> None:
        (tmp_path / "a.yaml").write_text("kind: Pod\nmetadata:\n  name: a\n")
        (tmp_path / "b.yml").write_text("kind: Service\nmetadata:\n  name: b\n")
        (tmp_path / "c.txt").write_text("not a manifest")

        result = load_directory(str(tmp_path))
        kinds = {m["kind"] for m in result}
        assert kinds == {"Pod", "Service"}

    def test_recursive_descends_into_subdirectories(self, tmp_path) -> None:
        nested = tmp_path / "nested"
        nested.mkdir()
        (tmp_path / "top.yaml").write_text("kind: Pod\nmetadata:\n  name: top\n")
        (nested / "inner.yaml").write_text("kind: Service\nmetadata:\n  name: inner\n")

        non_recursive = load_directory(str(tmp_path), recursive=False)
        recursive = load_directory(str(tmp_path), recursive=True)

        assert len(non_recursive) == 1
        assert len(recursive) == 2

    def test_custom_extensions(self, tmp_path) -> None:
        (tmp_path / "a.yaml").write_text("kind: Pod\nmetadata:\n  name: a\n")
        (tmp_path / "b.json").write_text(
            '{"kind": "Service", "metadata": {"name": "b"}}'
        )

        result = load_directory(str(tmp_path), extensions=[".json"])
        assert len(result) == 1
        assert result[0]["kind"] == "Service"

    def test_exclude_patterns(self, tmp_path) -> None:
        (tmp_path / "keep.yaml").write_text("kind: Pod\nmetadata:\n  name: keep\n")
        (tmp_path / "skip.yaml").write_text("kind: Service\nmetadata:\n  name: skip\n")

        result = load_directory(str(tmp_path), exclude_patterns=["skip.*"])
        assert len(result) == 1
        assert result[0]["metadata"]["name"] == "keep"

    def test_ignores_subdirectory_entries_when_not_recursive(self, tmp_path) -> None:
        nested = tmp_path / "nested"
        nested.mkdir()
        result = load_directory(str(tmp_path))
        assert result == []


@pytest.mark.unit
class TestLoadMultipleFiles:
    def test_preserves_order_across_files(self, tmp_path) -> None:
        file_a = tmp_path / "a.yaml"
        file_a.write_text("kind: Pod\nmetadata:\n  name: a\n")
        file_b = tmp_path / "b.yaml"
        file_b.write_text("kind: Service\nmetadata:\n  name: b\n")

        result = load_multiple_files([str(file_a), str(file_b)])
        assert [m["kind"] for m in result] == ["Pod", "Service"]
