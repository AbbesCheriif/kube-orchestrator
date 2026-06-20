"""Apply manifests example — load, validate, render and apply."""
from __future__ import annotations

from pathlib import Path

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.manifest.applier import ManifestApplier
from kube_orchestrator.manifest.loader import load_file
from kube_orchestrator.manifest.renderer import render_file
from kube_orchestrator.manifest.validator import order_by_dependency, validate_manifest

MANIFESTS_DIR = Path(__file__).parent.parent / "full-app"

client = KubeClient.get_instance()

values = {
    "namespace": "production",
    "replicas": 3,
    "image": "myapp:v1.2.0",
}

all_manifests = []
for yaml_file in sorted(MANIFESTS_DIR.glob("*.yaml")):
    try:
        docs = render_file(str(yaml_file), values=values)
        all_manifests.extend(docs)
    except Exception:
        docs = load_file(str(yaml_file))
        all_manifests.extend(docs)

errors = []
for manifest in all_manifests:
    errs = validate_manifest(manifest)
    if errs:
        errors.extend(errs)

if errors:
    print("Validation errors:")
    for e in errors:
        print(f"  - {e}")
    raise SystemExit(1)

ordered = order_by_dependency(all_manifests)
print(f"Applying {len(ordered)} manifest(s) in dependency order:")

applier = ManifestApplier(client=client, dry_run=False, force=False, server_side=False)
for manifest in ordered:
    result = applier.apply_manifest(manifest, namespace=values["namespace"])
    action = result.get("action", "applied").upper()
    kind = manifest.get("kind", "")
    name = manifest.get("metadata", {}).get("name", "")
    print(f"  {action}: {kind}/{name}")

print("All manifests applied successfully.")
