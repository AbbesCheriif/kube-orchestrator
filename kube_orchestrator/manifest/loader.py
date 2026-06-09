"""Manifest loader — YAML single-doc, multi-doc, file, directory, URL and stdin."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import yaml


def load_file(path: str) -> list[dict[str, Any]]:
    """Load one or more Kubernetes manifests from a YAML/JSON file."""
    file_path = Path(path)
    content = file_path.read_text(encoding=detect_encoding(path))
    return load_string(content)


def load_string(content: str) -> list[dict[str, Any]]:
    """Parse a YAML string containing one or multiple documents."""
    docs = list(yaml.safe_load_all(content))
    return [d for d in docs if d is not None]


def load_url(url: str, headers: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Fetch and parse YAML manifests from a remote URL."""
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=30) as response:
        content = response.read().decode("utf-8")
    return load_string(content)


def load_stdin() -> list[dict[str, Any]]:
    """Read and parse YAML manifests from standard input."""
    content = sys.stdin.read()
    return load_string(content)


def validate_yaml_syntax(content: str) -> list[str]:
    """Return a list of syntax error messages; empty list means valid."""
    errors: list[str] = []
    try:
        list(yaml.safe_load_all(content))
    except yaml.YAMLError as exc:
        errors.append(str(exc))
    return errors


def detect_encoding(path: str) -> str:
    """Detect file encoding by reading the BOM or falling back to utf-8."""
    with open(path, "rb") as f:
        raw = f.read(4)
    if raw.startswith(b"\xff\xfe\x00\x00") or raw.startswith(b"\x00\x00\xfe\xff"):
        return "utf-32"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return "utf-8"
