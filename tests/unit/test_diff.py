"""Unit tests for kube_orchestrator.resources.diff."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.diff import (
    compute_diff,
    extract_managed_fields,
    format_diff_output,
    is_spec_changed,
    json_merge_patch,
    strategic_merge_patch,
)


@pytest.mark.unit
class TestComputeDiff:
    def test_no_diff_when_identical(self) -> None:
        assert compute_diff({"a": 1}, {"a": 1}) == {}

    def test_detects_top_level_change(self) -> None:
        diff = compute_diff({"a": 1}, {"a": 2})
        assert diff == {"a": {"current": 1, "desired": 2}}

    def test_detects_added_key(self) -> None:
        diff = compute_diff({}, {"a": 1})
        assert diff == {"a": {"current": None, "desired": 1}}

    def test_detects_removed_key(self) -> None:
        diff = compute_diff({"a": 1}, {})
        assert diff == {"a": {"current": 1, "desired": None}}

    def test_recurses_into_nested_dicts(self) -> None:
        current = {"spec": {"replicas": 1, "image": "nginx"}}
        desired = {"spec": {"replicas": 3, "image": "nginx"}}
        diff = compute_diff(current, desired)
        assert diff == {"spec": {"replicas": {"current": 1, "desired": 3}}}

    def test_nested_dict_with_no_diff_is_omitted(self) -> None:
        current = {"spec": {"replicas": 1}}
        desired = {"spec": {"replicas": 1}}
        assert compute_diff(current, desired) == {}


@pytest.mark.unit
class TestStrategicMergePatch:
    def test_adds_new_field(self) -> None:
        result = strategic_merge_patch({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_none_value_removes_key(self) -> None:
        result = strategic_merge_patch({"a": 1, "b": 2}, {"b": None})
        assert result == {"a": 1}

    def test_merges_nested_dicts(self) -> None:
        current = {"spec": {"replicas": 1, "image": "nginx"}}
        patch = {"spec": {"replicas": 3}}
        result = strategic_merge_patch(current, patch)
        assert result == {"spec": {"replicas": 3, "image": "nginx"}}

    def test_does_not_mutate_original(self) -> None:
        current = {"a": {"b": 1}}
        strategic_merge_patch(current, {"a": {"b": 2}})
        assert current == {"a": {"b": 1}}

    def test_replaces_non_dict_value(self) -> None:
        result = strategic_merge_patch({"tags": ["a"]}, {"tags": ["b", "c"]})
        assert result == {"tags": ["b", "c"]}


@pytest.mark.unit
class TestJsonMergePatch:
    def test_adds_new_field(self) -> None:
        assert json_merge_patch({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_none_value_removes_key(self) -> None:
        assert json_merge_patch({"a": 1, "b": 2}, {"b": None}) == {"a": 1}

    def test_replaces_nested_dict_wholesale(self) -> None:
        current = {"spec": {"replicas": 1, "image": "nginx"}}
        patch = {"spec": {"replicas": 3}}
        result = json_merge_patch(current, patch)
        assert result == {"spec": {"replicas": 3}}

    def test_does_not_mutate_original(self) -> None:
        current = {"a": 1}
        json_merge_patch(current, {"a": 2})
        assert current == {"a": 1}


@pytest.mark.unit
class TestFormatDiffOutput:
    def test_formats_leaf_change(self) -> None:
        diff = {"replicas": {"current": 1, "desired": 3}}
        output = format_diff_output(diff)
        assert "replicas:" in output
        assert "- 1" in output
        assert "+ 3" in output

    def test_formats_nested_diff_with_indentation(self) -> None:
        diff = {"spec": {"replicas": {"current": 1, "desired": 3}}}
        output = format_diff_output(diff)
        assert "spec:" in output
        assert "  replicas:" in output


@pytest.mark.unit
class TestIsSpecChanged:
    def test_true_when_specs_differ(self) -> None:
        assert is_spec_changed({"spec": {"a": 1}}, {"spec": {"a": 2}}) is True

    def test_false_when_specs_match(self) -> None:
        assert is_spec_changed({"spec": {"a": 1}}, {"spec": {"a": 1}}) is False

    def test_false_when_both_missing_spec(self) -> None:
        assert is_spec_changed({}, {}) is False


@pytest.mark.unit
class TestExtractManagedFields:
    def test_returns_managed_fields(self) -> None:
        resource = {"metadata": {"managedFields": [{"manager": "kubectl"}]}}
        assert extract_managed_fields(resource) == [{"manager": "kubectl"}]

    def test_returns_empty_list_when_absent(self) -> None:
        assert extract_managed_fields({"metadata": {}}) == []

    def test_returns_empty_list_without_metadata(self) -> None:
        assert extract_managed_fields({}) == []
