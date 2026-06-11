"""Manifest renderer — Jinja2-powered template engine with Helm-like helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined, Undefined


# ------------------------------------------------------------------
# Jinja2 filter/function helpers
# ------------------------------------------------------------------


def _b64encode(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def _b64decode(value: str) -> str:
    return base64.b64decode(value.encode()).decode()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _to_json(value: Any) -> str:
    return json.dumps(value)


def _from_json(value: str) -> Any:
    return json.loads(value)


def _to_yaml(value: Any) -> str:
    return yaml.dump(value, default_flow_style=False).rstrip()


def _required(value: Any, message: str = "Value is required") -> Any:
    if value is None or isinstance(value, Undefined):
        raise ValueError(message)
    return value


def _default(value: Any, default_val: Any = "") -> Any:
    if value is None or isinstance(value, Undefined):
        return default_val
    return value


def _indent(value: str, width: int = 2) -> str:
    pad = " " * width
    return "\n".join(pad + line if line else line for line in value.splitlines())


def _quote(value: str) -> str:
    return f'"{value}"'


def _trim_suffix(value: str, suffix: str) -> str:
    return value[: -len(suffix)] if value.endswith(suffix) else value


def _trim_prefix(value: str, prefix: str) -> str:
    return value[len(prefix) :] if value.startswith(prefix) else value


def _build_env() -> Environment:
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    filters: dict[str, Any] = {
        "b64encode": _b64encode,
        "b64decode": _b64decode,
        "sha256": _sha256,
        "to_json": _to_json,
        "from_json": _from_json,
        "to_yaml": _to_yaml,
        "indent": _indent,
        "quote": _quote,
        "trim_suffix": _trim_suffix,
        "trim_prefix": _trim_prefix,
        "upper": str.upper,
        "lower": str.lower,
        "title": str.title,
    }
    env.filters.update(filters)
    env.globals["required"] = _required
    env.globals["default"] = _default
    return env


_ENV = _build_env()


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def render_file(path: str, values: dict[str, Any]) -> list[dict[str, Any]]:
    """Render a Jinja2-templated YAML file and return parsed manifests."""
    content = Path(path).read_text(encoding="utf-8")
    return render_string(content, values)


def render_string(content: str, values: dict[str, Any]) -> list[dict[str, Any]]:
    """Render a Jinja2 template string and parse the result as YAML."""
    template = _ENV.from_string(content)
    rendered = template.render(**values)
    docs = list(yaml.safe_load_all(rendered))
    return [d for d in docs if d is not None]


def load_values_file(path: str) -> dict[str, Any]:
    """Load values from a YAML or JSON file."""
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix in (".json",):
        return json.loads(text)
    result = yaml.safe_load(text)
    return result if isinstance(result, dict) else {}


def merge_values(*values_dicts: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge multiple values dicts left to right (later dicts win)."""
    merged: dict[str, Any] = {}
    for d in values_dicts:
        _deep_merge(merged, d)
    return merged


def inject_env_vars(values: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of values with environment variables merged in under 'env'."""
    result = dict(values)
    result.setdefault("env", {})
    result["env"].update(os.environ)
    return result


def override_values(
    base: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """Return a deep-merged copy of base with overrides applied on top."""
    result: dict[str, Any] = {}
    _deep_merge(result, base)
    _deep_merge(result, overrides)
    return result


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
