from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    help="Delete Kubernetes resources defined in manifests",
    context_settings={"allow_interspersed_args": True},
)


@app.callback(invoke_without_command=True)
def delete(
    path: Annotated[Path, typer.Argument(help="Path to manifest file or directory")],
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help="Target namespace")
    ] = None,
    cascade: Annotated[
        bool, typer.Option("--cascade", help="Delete dependent resources")
    ] = True,
    grace_period: Annotated[
        int | None, typer.Option("--grace-period", help="Grace period in seconds")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Force deletion (grace-period=0)")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview deletions without executing")
    ] = False,
) -> None:
    """Delete resources described in a manifest file or directory."""
    from kube_orchestrator.cli.output import (
        print_error,
        print_info,
        print_success,
        print_warning,
    )

    if not path.exists():
        print_error(f"Path not found: {path}")
        raise typer.Exit(1)

    if dry_run:
        print_warning("[DRY-RUN] No resources will be deleted.")

    effective_grace = 0 if force else grace_period
    print_info(f"Deleting resources from: {path}")

    try:
        from kube_orchestrator.core.client import KubeClient
        from kube_orchestrator.manifest.deleter import ManifestDeleter

        client = KubeClient.get_instance()
        deleter = ManifestDeleter(client=client)

        if dry_run:
            results = deleter.dry_run_delete(str(path))
            for r in results:
                print_warning(f"WOULD DELETE: {r.get('kind')}/{r.get('name')}")
        else:
            if path.is_dir():
                deleted = deleter.delete_directory(
                    str(path), namespace, recursive=False
                )
            else:
                deleted = deleter.delete_file(
                    str(path), namespace, cascade=cascade, grace_period=effective_grace
                )

            for name in deleted:
                print_success(f"DELETED: {name}")

    except Exception as exc:
        print_error(f"Delete failed: {exc}")
        raise typer.Exit(1) from exc
