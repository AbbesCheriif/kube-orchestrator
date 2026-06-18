from __future__ import annotations

import typer

app = typer.Typer(
    name="kube-orchestrator",
    help="Kubernetes Python SDK & CLI — programmatic kubectl, GitOps engine, platform engineering SDK",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def main() -> None:
    from kube_orchestrator.cli.router import register_all_commands

    register_all_commands(app)
    app()


if __name__ == "__main__":
    main()
