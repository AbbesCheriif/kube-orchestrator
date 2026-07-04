from __future__ import annotations

from typing import Annotated, Any

import typer

app = typer.Typer(help="Manage cluster nodes")


@app.command("list")
def nodes_list(
    label_selector: Annotated[
        str | None, typer.Option("--selector", "-l", help="Label selector")
    ] = None,
    output: Annotated[
        str, typer.Option("--output", "-o", help="Output format: table|json")
    ] = "table",
) -> None:
    """List all cluster nodes with their status."""
    from kube_orchestrator.cli.output import print_error, print_json, print_table
    from kube_orchestrator.core.client import KubeClient
    from kube_orchestrator.resources.cluster.node import NodeManager

    try:
        client = KubeClient.get_instance()
        manager = NodeManager(kube_client=client)
        nodes = manager.list_nodes(label_selector=label_selector)
        items: list[dict[str, Any]] = []
        for n in nodes:
            meta = n.metadata
            if meta is None or not meta.name:
                continue
            items.append(
                {
                    "name": meta.name,
                    "status": "Ready" if manager.is_ready(meta.name) else "NotReady",
                    "schedulable": (
                        "Yes" if manager.is_schedulable(meta.name) else "No (cordoned)"
                    ),
                    "age": (
                        str(meta.creation_timestamp)[:10]
                        if meta.creation_timestamp
                        else "-"
                    ),
                }
            )
        if output == "json":
            print_json({"nodes": items})
        else:
            print_table(
                headers=["NAME", "STATUS", "SCHEDULABLE", "AGE"],
                rows=[
                    [i["name"], i["status"], i["schedulable"], i["age"]] for i in items
                ],
                title="Nodes",
            )
    except Exception as exc:
        print_error(f"Failed to list nodes: {exc}")
        raise typer.Exit(1) from exc


@app.command("cordon")
def nodes_cordon(
    name: Annotated[str, typer.Argument(help="Node name to cordon")],
) -> None:
    """Mark a node as unschedulable (cordon)."""
    from kube_orchestrator.cli.output import print_error, print_success
    from kube_orchestrator.core.client import KubeClient
    from kube_orchestrator.resources.cluster.node import NodeManager

    try:
        client = KubeClient.get_instance()
        NodeManager(kube_client=client).cordon(name)
        print_success(f"Node '{name}' cordoned.")
    except Exception as exc:
        print_error(f"Cordon failed: {exc}")
        raise typer.Exit(1) from exc


@app.command("uncordon")
def nodes_uncordon(
    name: Annotated[str, typer.Argument(help="Node name to uncordon")],
) -> None:
    """Mark a node as schedulable again (uncordon)."""
    from kube_orchestrator.cli.output import print_error, print_success
    from kube_orchestrator.core.client import KubeClient
    from kube_orchestrator.resources.cluster.node import NodeManager

    try:
        client = KubeClient.get_instance()
        NodeManager(kube_client=client).uncordon(name)
        print_success(f"Node '{name}' uncordoned.")
    except Exception as exc:
        print_error(f"Uncordon failed: {exc}")
        raise typer.Exit(1) from exc


@app.command("drain")
def nodes_drain(
    name: Annotated[str, typer.Argument(help="Node name to drain")],
    ignore_daemonsets: Annotated[
        bool, typer.Option("--ignore-daemonsets", help="Ignore DaemonSet-managed pods")
    ] = True,
    delete_emptydir: Annotated[
        bool,
        typer.Option(
            "--delete-emptydir-data", help="Delete pods with emptyDir volumes"
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Force eviction of pods without controllers")
    ] = False,
) -> None:
    """Drain a node by evicting all pods (prepares node for maintenance)."""
    from kube_orchestrator.cli.output import print_error, print_info, print_success
    from kube_orchestrator.core.client import KubeClient
    from kube_orchestrator.resources.cluster.node import NodeManager

    try:
        print_info(f"Draining node '{name}'...")
        client = KubeClient.get_instance()
        evicted = NodeManager(kube_client=client).drain(
            name,
            ignore_daemonsets=ignore_daemonsets,
            delete_emptydir_data=delete_emptydir,
            force=force,
        )
        for pod in evicted:
            print_info(f"  Evicted: {pod}")
        print_success(f"Node '{name}' drained successfully.")
    except Exception as exc:
        print_error(f"Drain failed: {exc}")
        raise typer.Exit(1) from exc


@app.command("taint")
def nodes_taint(
    name: Annotated[str, typer.Argument(help="Node name")],
    key: Annotated[str, typer.Argument(help="Taint key")],
    value: Annotated[str, typer.Argument(help="Taint value")],
    effect: Annotated[
        str, typer.Argument(help="Taint effect: NoSchedule|PreferNoSchedule|NoExecute")
    ],
) -> None:
    """Add a taint to a node."""
    from kube_orchestrator.cli.output import print_error, print_success
    from kube_orchestrator.core.client import KubeClient
    from kube_orchestrator.resources.cluster.node import NodeManager

    try:
        client = KubeClient.get_instance()
        NodeManager(kube_client=client).add_taint(name, key, value, effect)
        print_success(f"Taint '{key}={value}:{effect}' added to node '{name}'.")
    except Exception as exc:
        print_error(f"Taint failed: {exc}")
        raise typer.Exit(1) from exc


@app.command("untaint")
def nodes_untaint(
    name: Annotated[str, typer.Argument(help="Node name")],
    key: Annotated[str, typer.Argument(help="Taint key to remove")],
) -> None:
    """Remove a taint from a node."""
    from kube_orchestrator.cli.output import print_error, print_success
    from kube_orchestrator.core.client import KubeClient
    from kube_orchestrator.resources.cluster.node import NodeManager

    try:
        client = KubeClient.get_instance()
        NodeManager(kube_client=client).remove_taint(name, key)
        print_success(f"Taint '{key}' removed from node '{name}'.")
    except Exception as exc:
        print_error(f"Untaint failed: {exc}")
        raise typer.Exit(1) from exc
