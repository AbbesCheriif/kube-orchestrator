from __future__ import annotations

from typing import Annotated, Optional

import typer

app = typer.Typer(help="Stream or fetch pod logs")


@app.callback(invoke_without_command=True)
def logs(
    pod_name: Annotated[str, typer.Argument(help="Pod name")],
    namespace: Annotated[str, typer.Option("--namespace", "-n", help="Pod namespace")] = "default",
    container: Annotated[Optional[str], typer.Option("--container", "-c", help="Container name (required if multi-container)")] = None,
    tail: Annotated[Optional[int], typer.Option("--tail", help="Number of lines to show from the end")] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Stream logs in real time")] = False,
    since: Annotated[Optional[int], typer.Option("--since", help="Show logs from the last N seconds")] = None,
    timestamps: Annotated[bool, typer.Option("--timestamps", help="Show timestamps in log output")] = False,
) -> None:
    """Fetch or stream logs from a pod container."""
    from kube_orchestrator.cli.output import print_error

    try:
        from kube_orchestrator.core.client import KubeClient
        from kube_orchestrator.resources.workloads.pod import PodManager

        client = KubeClient.get_instance()
        manager = PodManager(kube_client=client)

        for line in manager.stream_logs(
            pod_name,
            namespace,
            container=container,
            tail_lines=tail,
            since_seconds=since,
            timestamps=timestamps,
            follow=follow,
        ):
            typer.echo(line, nl=False)

    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print_error(f"Failed to fetch logs: {exc}")
        raise typer.Exit(1)
