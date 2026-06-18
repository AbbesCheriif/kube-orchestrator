from __future__ import annotations

from typing import Annotated, Optional

import typer

app = typer.Typer(help="Show cluster and workload status")


@app.callback(invoke_without_command=True)
def status(
    namespace: Annotated[Optional[str], typer.Option("--namespace", "-n", help="Filter by namespace")] = None,
    all_namespaces: Annotated[bool, typer.Option("--all-namespaces", "-A", help="Show resources across all namespaces")] = False,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Watch for changes")] = False,
    output: Annotated[str, typer.Option("--output", "-o", help="Output format: table|json|yaml")] = "table",
) -> None:
    """Display the status of Deployments and Pods in the cluster."""
    from kube_orchestrator.cli.output import print_error, print_info, print_table

    target_ns = None if all_namespaces else (namespace or "default")
    label = "all namespaces" if all_namespaces else f"namespace '{target_ns}'"
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

        dep_rows = []
        for d in deployments:
            meta = d.metadata
            spec = d.spec
            s = d.status
            dep_rows.append([
                meta.namespace or "-",
                meta.name,
                f"{s.ready_replicas or 0}/{spec.replicas or 0}",
                "Available" if (s.available_replicas or 0) > 0 else "Unavailable",
                str(meta.creation_timestamp)[:10] if meta.creation_timestamp else "-",
            ])

        pod_rows = []
        for p in pods:
            meta = p.metadata
            phase = p.status.phase if p.status else "Unknown"
            pod_rows.append([
                meta.namespace or "-",
                meta.name,
                phase,
                str(meta.creation_timestamp)[:10] if meta.creation_timestamp else "-",
            ])

        print_table(
            headers=["NAMESPACE", "NAME", "READY", "STATUS", "AGE"],
            rows=dep_rows,
            title="Deployments",
        )
        print_table(
            headers=["NAMESPACE", "NAME", "PHASE", "AGE"],
            rows=pod_rows,
            title="Pods",
        )
    except Exception as exc:
        print_error(f"Status check failed: {exc}")
        raise typer.Exit(1)
