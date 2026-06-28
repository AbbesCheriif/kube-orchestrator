from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

import typer

app = typer.Typer(
    name="kube-orchestrator",
    help="Kubernetes Python SDK & CLI — programmatic kubectl, GitOps engine, platform engineering SDK",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def _version_callback(show_version: bool) -> None:
    if show_version:
        try:
            typer.echo(f"kube-orchestrator {version('kube-orchestrator')}")
        except PackageNotFoundError:
            typer.echo("kube-orchestrator (version unknown — not installed via pip)")
        raise typer.Exit()


@app.callback()
def root(
    version_: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the installed version and exit.",
        ),
    ] = None,
) -> None:
    """Kubernetes Python SDK & CLI — programmatic kubectl, GitOps engine, platform engineering SDK."""


def main() -> None:
    from kube_orchestrator.cli.router import register_all_commands

    register_all_commands(app)
    app()


if __name__ == "__main__":
    main()
