"""Manifest loader — YAML single-doc, multi-doc, file, directory, URL and stdin."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import yaml


def load_file(path: str) -> list[dict[str, Any]]:
    """Load one or more Kubernetes manifests from a YAML/JSON file."""
    from kube_orchestrator.core.exceptions import ManifestParseError

    try:
        file_path = Path(path)
        content = file_path.read_text(encoding=detect_encoding(path))
        return load_string(content)
    except (FileNotFoundError, OSError) as exc:
        raise ManifestParseError(file=path, line=0) from exc


def load_string(content: str) -> list[dict[str, Any]]:
    """Parse a YAML string containing one or multiple documents."""
    from kube_orchestrator.core.exceptions import ManifestParseError

    try:
        docs = list(yaml.safe_load_all(content))
        return [d for d in docs if d is not None]
    except yaml.YAMLError as exc:
        raise ManifestParseError(file="<string>", line=0) from exc


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


def load_directory(
    path: str,
    recursive: bool = False,
    extensions: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Load all matching manifest files from a directory.

    Args:
        path: Directory to scan.
        recursive: Whether to descend into sub-directories.
        extensions: File extensions to include (default: .yaml, .yml).
        exclude_patterns: Glob patterns for files to skip.
    """
    exts = set(extensions or [".yaml", ".yml"])
    exclude = set(exclude_patterns or [])
    dir_path = Path(path)
    manifests: list[dict[str, Any]] = []

    iter_fn = dir_path.rglob if recursive else dir_path.glob
    for file_path in sorted(iter_fn("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix not in exts:
            continue
        if any(file_path.match(pat) for pat in exclude):
            continue
        manifests.extend(load_file(str(file_path)))

    return manifests


def load_multiple_files(paths: list[str]) -> list[dict[str, Any]]:
    """Load manifests from a list of file paths, preserving document order."""
    manifests: list[dict[str, Any]] = []
    for p in paths:
        manifests.extend(load_file(p))
    return manifests
