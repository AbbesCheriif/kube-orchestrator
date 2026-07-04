from __future__ import annotations

from typing import Annotated, Any

import typer

app = typer.Typer(help="Show cluster and workload status")


@app.callback(invoke_without_command=True)
def status(
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help="Filter by namespace")
    ] = None,
    all_namespaces: Annotated[
        bool,
        typer.Option(
            "--all-namespaces", "-A", help="Show resources across all namespaces"
        ),
    ] = False,
    watch: Annotated[
        bool, typer.Option("--watch", "-w", help="Watch for changes")
    ] = False,
    output: Annotated[
        str, typer.Option("--output", "-o", help="Output format: table|json|yaml")
    ] = "table",
) -> None:
    """Display the status of Deployments and Pods in the cluster."""
    from kube_orchestrator.cli.output import (
        print_error,
        print_info,
        print_json,
        print_table,
        print_yaml,
    )

    target_ns = None if all_namespaces else (namespace or "default")
    label = "all namespaces" if all_namespaces else f"namespace '{target_ns}'"
    if output == "table":
        print_info(f"Fetching status for {label}...")

    try:
        from kube_orchestrator.core.client import KubeClient
        from kube_orchestrator.resources.workloads.deployment import DeploymentManager
        from kube_orchestrator.resources.workloads.pod import PodManager

        client = KubeClient.get_instance()
        dep_manager = DeploymentManager(kube_client=client)
        pod_manager = PodManager(kube_client=client)

        ns_arg = "" if all_namespaces else (target_ns or "default")
        deployments = dep_manager.list_deployments(namespace=ns_arg)
        pods = pod_manager.list_pods(namespace=ns_arg)

        dep_items: list[dict[str, Any]] = []
        for d in deployments:
            meta = d.metadata
            spec = d.spec
            s = d.status
            ready_replicas = (s.ready_replicas if s else None) or 0
            desired_replicas = (spec.replicas if spec else None) or 0
            available_replicas = (s.available_replicas if s else None) or 0
            creation_timestamp = meta.creation_timestamp if meta else None
            dep_items.append(
                {
                    "namespace": (meta.namespace if meta else None) or "-",
                    "name": meta.name if meta else None,
                    "ready": f"{ready_replicas}/{desired_replicas}",
                    "status": (
                        "Available" if available_replicas > 0 else "Unavailable"
                    ),
                    "age": str(creation_timestamp)[:10] if creation_timestamp else "-",
                }
            )

        pod_items: list[dict[str, Any]] = []
        for p in pods:
            meta = p.metadata
            phase = p.status.phase if p.status else "Unknown"
            creation_timestamp = meta.creation_timestamp if meta else None
            pod_items.append(
                {
                    "namespace": (meta.namespace if meta else None) or "-",
                    "name": meta.name if meta else None,
                    "phase": phase,
                    "age": str(creation_timestamp)[:10] if creation_timestamp else "-",
                }
            )

        if output == "json":
            print_json({"deployments": dep_items, "pods": pod_items})
        elif output == "yaml":
            print_yaml({"deployments": dep_items, "pods": pod_items})
        else:
            print_table(
                headers=["NAMESPACE", "NAME", "READY", "STATUS", "AGE"],
                rows=[
                    [i["namespace"], i["name"], i["ready"], i["status"], i["age"]]
                    for i in dep_items
                ],
                title="Deployments",
            )
            print_table(
                headers=["NAMESPACE", "NAME", "PHASE", "AGE"],
                rows=[
                    [i["namespace"], i["name"], i["phase"], i["age"]] for i in pod_items
                ],
                title="Pods",
            )
    except Exception as exc:
        print_error(f"Status check failed: {exc}")
        raise typer.Exit(1) from exc
