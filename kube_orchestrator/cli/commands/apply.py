from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(help="Apply Kubernetes manifests to the cluster")


@app.callback(invoke_without_command=True)
def apply(
    path: Annotated[Path, typer.Argument(help="Path to manifest file or directory")],
    namespace: Annotated[Optional[str], typer.Option("--namespace", "-n", help="Target namespace")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes without applying")] = False,
    values: Annotated[Optional[Path], typer.Option("--values", "-f", help="Values file for template rendering")] = None,
    recursive: Annotated[bool, typer.Option("--recursive", "-r", help="Process directories recursively")] = False,
    wait: Annotated[bool, typer.Option("--wait", help="Wait for resources to be ready")] = False,
    timeout: Annotated[int, typer.Option("--timeout", help="Timeout in seconds when waiting")] = 300,
) -> None:
    """Apply manifests from a file or directory (create or update resources)."""
    from kube_orchestrator.cli.output import print_error, print_info, print_success, print_warning

    if not path.exists():
        print_error(f"Path not found: {path}")
        raise typer.Exit(1)

    values_data: dict = {}
    if values:
        if not values.exists():
            print_error(f"Values file not found: {values}")
            raise typer.Exit(1)
        import yaml

        with open(values) as f:
            values_data = yaml.safe_load(f) or {}

    if dry_run:
        print_warning("[DRY-RUN] No changes will be applied to the cluster.")

    print_info(f"Applying {'directory' if path.is_dir() else 'file'}: {path}")

    try:
        from kube_orchestrator.core.client import KubeClient
        from kube_orchestrator.manifest.applier import ManifestApplier

        client = KubeClient.get_instance()
        applier = ManifestApplier(client=client, dry_run=dry_run, force=False, server_side=False)

        if path.is_dir():
            results = applier.apply_directory(str(path), namespace, recursive=recursive, values=values_data or None)
        else:
            results = applier.apply_file(str(path), namespace, values=values_data or None)

        for r in results:
            action = r.get("action", "applied")
            name = r.get("name", "unknown")
            kind = r.get("kind", "")
            print_success(f"{action.upper()}: {kind}/{name}")

        if wait and not dry_run:
            print_info(f"Waiting for resources (timeout: {timeout}s)...")

    except Exception as exc:
        print_error(f"Apply failed: {exc}")
        raise typer.Exit(1)
