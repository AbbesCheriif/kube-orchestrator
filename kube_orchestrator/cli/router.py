from __future__ import annotations

import typer


def register_all_commands(app: typer.Typer) -> None:
    from kube_orchestrator.cli.commands.apply import app as apply_app
    from kube_orchestrator.cli.commands.delete import app as delete_app
    from kube_orchestrator.cli.commands.deploy import app as deploy_app
    from kube_orchestrator.cli.commands.doctor import app as doctor_app
    from kube_orchestrator.cli.commands.logs import app as logs_app
    from kube_orchestrator.cli.commands.nodes import app as nodes_app
    from kube_orchestrator.cli.commands.rollback import app as rollback_app
    from kube_orchestrator.cli.commands.status import app as status_app

    app.add_typer(apply_app, name="apply")
    app.add_typer(delete_app, name="delete")
    app.add_typer(deploy_app, name="deploy")
    app.add_typer(rollback_app, name="rollback")
    app.add_typer(status_app, name="status")
    app.add_typer(nodes_app, name="nodes")
    app.add_typer(doctor_app, name="doctor")
    app.add_typer(logs_app, name="logs")
