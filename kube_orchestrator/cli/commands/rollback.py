from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(
    help="Rollback a Deployment to a previous revision",
    context_settings={"allow_interspersed_args": True},
)


@app.callback(invoke_without_command=True)
def rollback(
    name: Annotated[str, typer.Argument(help="Deployment name to rollback")],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Namespace of the deployment")
    ] = "default",
    revision: Annotated[
        int | None,
        typer.Option("--revision", help="Target revision (omit for previous)"),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview rollback without executing")
    ] = False,
) -> None:
    """Roll back a Deployment to a previous revision."""
    from kube_orchestrator.cli.output import (
        print_error,
        print_info,
        print_success,
        print_warning,
    )

    if dry_run:
        print_warning("[DRY-RUN] No rollback will be performed.")

    target = f"revision {revision}" if revision else "previous revision"
    print_info(f"Rolling back '{name}' in namespace '{namespace}' to {target}...")

    try:
        from kube_orchestrator.core.client import KubeClient
        from kube_orchestrator.rollback.auto_rollback import AutoRollback

        client = KubeClient.get_instance()
        rollbacker = AutoRollback(client=client)

        if revision:
            rollbacker.rollback_to_revision(name, namespace, revision)
        else:
            rollbacker.trigger_rollback(name, namespace, reason="CLI rollback request")

        if not dry_run:
            print_success(f"Rollback of '{name}' to {target} completed.")
    except Exception as exc:
        print_error(f"Rollback failed: {exc}")
        raise typer.Exit(1) from exc
