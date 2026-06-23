"""Unit tests for ManifestRenderer."""

from __future__ import annotations

import pytest

from kube_orchestrator.manifest.renderer import (
    merge_values,
    override_values,
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

    def test_default_filter(self) -> None:
        template = "replicas: {{ replicas | default(1) }}"
        result = render_string(template, values={})
        assert result[0]["replicas"] == 1


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
