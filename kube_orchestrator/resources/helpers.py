"""Resource builder helpers and label/annotation utilities."""

from __future__ import annotations

import re


def build_metadata(
    name: str,
    namespace: str | None = None,
    labels: dict | None = None,
    annotations: dict | None = None,
    owner_references: list | None = None,
    finalizers: list | None = None,
) -> dict:
    """Build a Kubernetes metadata dict from individual fields."""
    meta: dict = {"name": name}
    if namespace:
        meta["namespace"] = namespace
    if labels:
        meta["labels"] = labels
    if annotations:
        meta["annotations"] = annotations
    if owner_references:
        meta["ownerReferences"] = owner_references
    if finalizers:
        meta["finalizers"] = finalizers
    return meta


def build_label_selector(labels: dict) -> str:
    """Convert a labels dict to a comma-separated selector string."""
    return ",".join(f"{k}={v}" for k, v in labels.items())


def build_field_selector(fields: dict) -> str:
    """Convert a fields dict to a comma-separated field selector string."""
    return ",".join(f"{k}={v}" for k, v in fields.items())


def add_label(resource: dict, key: str, value: str) -> dict:
    """Add or overwrite a label on a resource manifest."""
    resource.setdefault("metadata", {}).setdefault("labels", {})[key] = value
    return resource


def remove_label(resource: dict, key: str) -> dict:
    """Remove a label from a resource manifest."""
    resource.get("metadata", {}).get("labels", {}).pop(key, None)
    return resource


def add_annotation(resource: dict, key: str, value: str) -> dict:
    """Add or overwrite an annotation on a resource manifest."""
    resource.setdefault("metadata", {}).setdefault("annotations", {})[key] = value
    return resource


def remove_annotation(resource: dict, key: str) -> dict:
    """Remove an annotation from a resource manifest."""
    resource.get("metadata", {}).get("annotations", {}).pop(key, None)
    return resource


def get_labels(resource: dict) -> dict:
    """Return the labels dict of a resource manifest."""
    return resource.get("metadata", {}).get("labels", {})


def get_annotations(resource: dict) -> dict:
    """Return the annotations dict of a resource manifest."""
    return resource.get("metadata", {}).get("annotations", {})


def merge_labels(resource: dict, labels: dict) -> dict:
    """Merge labels into the resource manifest (existing keys are overwritten)."""
    resource.setdefault("metadata", {}).setdefault("labels", {}).update(labels)
    return resource


def build_owner_reference(owner: dict, block_owner_deletion: bool = True) -> dict:
    """Build an ownerReference entry from an owner manifest dict."""
    metadata = owner.get("metadata", {})
    return {
        "apiVersion": owner.get("apiVersion", ""),
        "kind": owner.get("kind", ""),
        "name": metadata.get("name", ""),
        "uid": metadata.get("uid", ""),
        "controller": True,
        "blockOwnerDeletion": block_owner_deletion,
    }


def sanitize_name(name: str) -> str:
    """Return a DNS-1123 compliant resource name derived from *name*."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name[:253]
