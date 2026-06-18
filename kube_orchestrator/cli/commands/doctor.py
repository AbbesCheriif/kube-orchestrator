from __future__ import annotations

from typing import Annotated, Optional

import typer

app = typer.Typer(help="Diagnose cluster health issues")


@app.callback(invoke_without_command=True)
def doctor(
    namespace: Annotated[Optional[str], typer.Option("--namespace", "-n", help="Namespace to check (omit for cluster-wide)")] = None,
    fix: Annotated[bool, typer.Option("--fix", help="Attempt to automatically fix detected issues")] = False,
) -> None:
    """Run a comprehensive cluster health check and display a Rich report."""
    from kube_orchestrator.cli.output import print_error, print_health_report, print_info, print_warning

    print_info("Running cluster health diagnostics...")
    if fix:
        print_warning("Auto-fix mode enabled — will attempt to resolve detected issues.")

    try:
        from kube_orchestrator.core.client import KubeClient
        from kube_orchestrator.monitoring.health import ClusterHealthReporter

        client = KubeClient.get_instance()
        reporter = ClusterHealthReporter(client=client)
        report = reporter.get_cluster_health()

        if namespace:
            workload_health = reporter.get_workload_health(namespace)
            report["namespace_detail"] = workload_health

        print_health_report(report)

        score = report.get("score", 0)
        if score < 50:
            print_warning(f"Cluster health score: {score}/100 — critical issues detected.")
            raise typer.Exit(2)
        elif score < 80:
            print_warning(f"Cluster health score: {score}/100 — some issues detected.")
        else:
            from kube_orchestrator.cli.output import print_success
            print_success(f"Cluster health score: {score}/100 — cluster is healthy.")

    except typer.Exit:
        raise
    except Exception as exc:
        print_error(f"Health check failed: {exc}")
        raise typer.Exit(1)
