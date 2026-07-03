"""Unit tests for ManifestRenderer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from kube_orchestrator.manifest.renderer import (
    get_available_filters,
    get_available_functions,
    inject_env_vars,
    load_values_file,
    merge_values,
    override_values,
    render_directory,
    render_file,
    render_string,
)


@pytest.mark.unit
class TestRenderString:
    def test_simple_variable_injection(self) -> None:
        template = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: {{ name }}\n"
        result = render_string(template, values={"name": "my-pod"})
        assert len(result) == 1
        assert result[0]["metadata"]["name"] == "my-pod"

    def test_multiple_variables(self) -> None:
        template = (
            "apiVersion: apps/v1\nkind: Deployment\n"
            "metadata:\n  name: {{ name }}\n  namespace: {{ namespace }}\n"
            "spec:\n  replicas: {{ replicas }}\n"
            "  selector:\n    matchLabels:\n      app: {{ name }}\n"
            "  template:\n    metadata:\n      labels:\n        app: {{ name }}\n"
            "    spec:\n      containers:\n        - name: app\n          image: {{ image }}\n"
        )
        result = render_string(
            template,
            values={
                "name": "web",
                "namespace": "prod",
                "replicas": 3,
                "image": "nginx:1.25",
            },
        )
        assert result[0]["spec"]["replicas"] == 3
        assert result[0]["metadata"]["namespace"] == "prod"

    def test_undefined_variable_raises(self) -> None:
        from kube_orchestrator.core.exceptions import ManifestRenderError

        template = "name: {{ undefined_var }}"
        with pytest.raises(ManifestRenderError):
            render_string(template, values={})

    def test_b64encode_helper(self) -> None:
        import base64

        template = "value: {{ 'hello' | b64encode }}"
        result = render_string(template, values={})
        expected = base64.b64encode(b"hello").decode()
        assert expected in str(result[0])

    def test_default_function_undefined_variable(self) -> None:
        template = "replicas: {{ default(replicas, 1) }}"
        result = render_string(template, values={})
        assert result[0]["replicas"] == 1

    def test_default_function_none_value(self) -> None:
        template = "replicas: {{ default(replicas, 1) }}"
        result = render_string(template, values={"replicas": None})
        assert result[0]["replicas"] == 1

    def test_default_function_present_value_is_kept(self) -> None:
        template = "replicas: {{ default(replicas, 1) }}"
        result = render_string(template, values={"replicas": 5})
        assert result[0]["replicas"] == 5

    def test_b64decode_helper(self) -> None:
        template = "value: {{ 'aGVsbG8=' | b64decode }}"
        result = render_string(template, values={})
        assert result[0]["value"] == "hello"

    def test_sha256_helper(self) -> None:
        import hashlib

        template = "value: {{ 'hello' | sha256 }}"
        result = render_string(template, values={})
        assert result[0]["value"] == hashlib.sha256(b"hello").hexdigest()

    def test_to_json_helper(self) -> None:
        template = "value: '{{ data | to_json }}'"
        result = render_string(template, values={"data": {"a": 1}})
        assert result[0]["value"] == '{"a": 1}'

    def test_from_json_helper(self) -> None:
        template = "{{ '{\"a\": 1}' | from_json }}"
        result = render_string(template, values={})
        assert result[0] == {"a": 1}

    def test_to_yaml_helper(self) -> None:
        template = "value: |\n  {{ data | to_yaml | indent(2) }}"
        result = render_string(template, values={"data": {"a": 1}})
        assert "a: 1" in result[0]["value"]

    def test_quote_helper(self) -> None:
        template = "value: {{ 'hello' | quote }}"
        result = render_string(template, values={})
        assert result[0]["value"] == "hello"

    def test_trim_suffix_helper(self) -> None:
        template = "value: {{ 'app.yaml' | trim_suffix('.yaml') }}"
        result = render_string(template, values={})
        assert result[0]["value"] == "app"

    def test_trim_suffix_no_match(self) -> None:
        template = "value: {{ 'app.txt' | trim_suffix('.yaml') }}"
        result = render_string(template, values={})
        assert result[0]["value"] == "app.txt"

    def test_trim_prefix_helper(self) -> None:
        template = "value: {{ 'prefix-app' | trim_prefix('prefix-') }}"
        result = render_string(template, values={})
        assert result[0]["value"] == "app"

    def test_trim_prefix_no_match(self) -> None:
        template = "value: {{ 'app' | trim_prefix('prefix-') }}"
        result = render_string(template, values={})
        assert result[0]["value"] == "app"

    def test_upper_lower_title_helpers(self) -> None:
        template = (
            "upper: {{ 'abc' | upper }}\n"
            "lower: {{ 'ABC' | lower }}\n"
            "title: {{ 'hello world' | title }}\n"
        )
        result = render_string(template, values={})
        assert result[0] == {"upper": "ABC", "lower": "abc", "title": "Hello World"}

    def test_required_raises_when_none(self) -> None:
        template = "value: {{ required(missing_value) }}"
        with pytest.raises(ValueError, match="Value is required"):
            render_string(template, values={"missing_value": None})

    def test_required_raises_when_undefined(self) -> None:
        template = "value: {{ required(totally_undefined) }}"
        with pytest.raises(ValueError, match="Value is required"):
            render_string(template, values={})

    def test_required_custom_message(self) -> None:
        template = "value: {{ required(missing_value, 'custom message') }}"
        with pytest.raises(ValueError, match="custom message"):
            render_string(template, values={"missing_value": None})

    def test_required_passes_through_value(self) -> None:
        template = "value: {{ required(name) }}"
        result = render_string(template, values={"name": "web"})
        assert result[0]["value"] == "web"

    def test_indent_helper_on_multiline(self) -> None:
        template = "block: |\n{{ text | indent(2) }}"
        result = render_string(template, values={"text": "line1\nline2"})
        assert "line1" in result[0]["block"]


@pytest.mark.unit
class TestRenderFile:
    def test_renders_templated_file(self, tmp_path) -> None:
        path = tmp_path / "pod.yaml.j2"
        path.write_text("kind: Pod\nmetadata:\n  name: {{ name }}\n")
        result = render_file(str(path), {"name": "web"})
        assert result[0]["metadata"]["name"] == "web"


@pytest.mark.unit
class TestRenderDirectory:
    def test_renders_all_matching_files(self, tmp_path) -> None:
        (tmp_path / "a.yaml").write_text("kind: Pod\nmetadata:\n  name: {{ name }}\n")
        (tmp_path / "b.j2").write_text("kind: Service\nmetadata:\n  name: {{ name }}\n")
        (tmp_path / "c.txt").write_text("not a template")

        result = render_directory(str(tmp_path), {"name": "web"})
        kinds = {m["kind"] for m in result}
        assert kinds == {"Pod", "Service"}

    def test_recursive_descends_into_subdirectories(self, tmp_path) -> None:
        nested = tmp_path / "nested"
        nested.mkdir()
        (tmp_path / "top.yaml").write_text("kind: Pod\nmetadata:\n  name: top\n")
        (nested / "inner.yaml").write_text("kind: Service\nmetadata:\n  name: inner\n")

        assert len(render_directory(str(tmp_path), {}, recursive=False)) == 1
        assert len(render_directory(str(tmp_path), {}, recursive=True)) == 2


@pytest.mark.unit
class TestLoadValuesFile:
    def test_loads_yaml_values(self, tmp_path) -> None:
        path = tmp_path / "values.yaml"
        path.write_text("replicas: 3\n")
        assert load_values_file(str(path)) == {"replicas": 3}

    def test_loads_json_values(self, tmp_path) -> None:
        path = tmp_path / "values.json"
        path.write_text('{"replicas": 3}')
        assert load_values_file(str(path)) == {"replicas": 3}

    def test_non_mapping_yaml_returns_empty_dict(self, tmp_path) -> None:
        path = tmp_path / "values.yaml"
        path.write_text("- a\n- b\n")
        assert load_values_file(str(path)) == {}


@pytest.mark.unit
class TestInjectEnvVars:
    def test_merges_environment_into_env_key(self) -> None:
        with patch.dict("os.environ", {"MY_VAR": "hello"}, clear=False):
            result = inject_env_vars({"replicas": 1})
        assert result["env"]["MY_VAR"] == "hello"
        assert result["replicas"] == 1

    def test_preserves_existing_env_key(self) -> None:
        with patch.dict("os.environ", {"MY_VAR": "hello"}, clear=False):
            result = inject_env_vars({"env": {"CUSTOM": "value"}})
        assert result["env"]["CUSTOM"] == "value"
        assert result["env"]["MY_VAR"] == "hello"


@pytest.mark.unit
class TestFilterAndFunctionRegistry:
    def test_get_available_filters_returns_copy(self) -> None:
        filters = get_available_filters()
        assert "b64encode" in filters
        filters["new"] = "should not persist"
        assert "new" not in get_available_filters()

    def test_get_available_functions_returns_copy(self) -> None:
        functions = get_available_functions()
        assert "required" in functions
        assert "default" in functions


@pytest.mark.unit
class TestMergeValues:
    def test_merge_two_dicts(self) -> None:
        base = {"key1": "val1", "key2": "val2"}
        extra = {"key2": "overridden", "key3": "val3"}
        merged = merge_values(base, extra)
        assert merged["key1"] == "val1"
        assert merged["key2"] == "overridden"
        assert merged["key3"] == "val3"

    def test_merge_nested(self) -> None:
        base = {"outer": {"inner": "old"}}
        extra = {"outer": {"inner": "new", "added": "yes"}}
        merged = merge_values(base, extra)
        assert merged["outer"]["inner"] == "new"


@pytest.mark.unit
class TestOverrideValues:
    def test_override_replaces_keys(self) -> None:
        base = {"replicas": 1, "image": "nginx:latest"}
        overrides = {"replicas": 3}
        result = override_values(base, overrides)
        assert result["replicas"] == 3
        assert result["image"] == "nginx:latest"
