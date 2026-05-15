"""Resource diff and patch utilities."""

from __future__ import annotations

import copy


def compute_diff(current: dict, desired: dict) -> dict:
    """Return a dict describing fields that differ between current and desired."""
    diff: dict = {}
    for key in set(current) | set(desired):
        cur_val = current.get(key)
        des_val = desired.get(key)
        if cur_val == des_val:
            continue
        if isinstance(cur_val, dict) and isinstance(des_val, dict):
            nested = compute_diff(cur_val, des_val)
            if nested:
                diff[key] = nested
        else:
            diff[key] = {"current": cur_val, "desired": des_val}
    return diff


def strategic_merge_patch(current: dict, patch: dict) -> dict:
    """Apply a strategic merge patch to *current*, returning a new dict."""
    result = copy.deepcopy(current)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = strategic_merge_patch(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def json_merge_patch(current: dict, patch: dict) -> dict:
    """Apply a JSON Merge Patch (RFC 7396) to *current*, returning a new dict."""
    result = copy.deepcopy(current)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = copy.deepcopy(value)
    return result


def format_diff_output(diff: dict, _indent: int = 0) -> str:
    """Return a human-readable representation of a compute_diff result."""
    lines: list[str] = []
    prefix = "  " * _indent
    for key, value in diff.items():
        if isinstance(value, dict) and "current" not in value and "desired" not in value:
            lines.append(f"{prefix}{key}:")
            lines.append(format_diff_output(value, _indent + 1))
        else:
            lines.append(f"{prefix}{key}:")
            lines.append(f"{prefix}  - {value.get('current')!r}")
            lines.append(f"{prefix}  + {value.get('desired')!r}")
    return "\n".join(lines)


def is_spec_changed(current: dict, desired: dict) -> bool:
    """Return True if the spec sections of the two manifests differ."""
    return current.get("spec") != desired.get("spec")


def extract_managed_fields(resource: dict) -> list:
    """Return the managedFields list from the resource metadata."""
    return resource.get("metadata", {}).get("managedFields", [])
