from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(
    help="Deploy a container image to Kubernetes",
    context_settings={"allow_interspersed_args": True},
)


@app.callback(invoke_without_command=True)
def deploy(
    image: Annotated[
        str, typer.Argument(help="Container image to deploy (e.g. nginx:latest)")
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", help="Deployment name (defaults to image name)"),
    ] = None,
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Target namespace")
    ] = "default",
    replicas: Annotated[int, typer.Option("--replicas", help="Number of replicas")] = 1,
    port: Annotated[
        int | None, typer.Option("--port", help="Container port to expose")
    ] = None,
    env: Annotated[
        list[str] | None,
        typer.Option("--env", "-e", help="Environment variables (KEY=VALUE)"),
    ] = None,
    cpu_request: Annotated[
        str | None, typer.Option("--cpu-request", help="CPU request (e.g. 100m)")
    ] = None,
    memory_request: Annotated[
        str | None, typer.Option("--memory-request", help="Memory request (e.g. 128Mi)")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without deploying")
    ] = False,
) -> None:
    """Deploy a container image as a Kubernetes Deployment."""
    from kube_orchestrator.cli.output import (
        print_error,
        print_info,
        print_success,
        print_warning,
    )

    deployment_name = name or image.split("/")[-1].split(":")[0]

    if dry_run:
        print_warning("[DRY-RUN] No resources will be created.")

    env_vars: dict[str, str] = {}
    if env:
        for pair in env:
            if "=" in pair:
                k, v = pair.split("=", 1)
                env_vars[k] = v

    print_info(
        f"Deploying image '{image}' as '{deployment_name}' in namespace '{namespace}'..."
    )

    try:
        from kube_orchestrator.core.client import KubeClient
        from kube_orchestrator.resources.workloads._builders.deployment_builder import (
            DeploymentBuilder,
        )
        from kube_orchestrator.resources.workloads._builders.pod_builder import (
            PodBuilder,
        )
        from kube_orchestrator.resources.workloads.deployment import DeploymentManager

        client = KubeClient.get_instance()
        pod_builder = PodBuilder(name=deployment_name).with_container(
            name=deployment_name, image=image
        )
        if cpu_request or memory_request:
            pod_builder = pod_builder.with_resources(
                deployment_name,
                cpu_request=cpu_request,
                memory_request=memory_request,
            )
        for k, v in env_vars.items():
            pod_builder = pod_builder.with_env(deployment_name, k, v)
        if port:
            pod_builder = pod_builder.with_ports(
                deployment_name, [{"containerPort": port}]
            )

        builder = (
            DeploymentBuilder(name=deployment_name, namespace=namespace)
            .with_replicas(replicas)
            .with_selector({"app": deployment_name})
            .with_pod_template(pod_builder)
        )

        manager = DeploymentManager(kube_client=client)
        manager.create_deployment(builder=builder, namespace=namespace)
        if not dry_run:
            print_success(
                f"Deployment '{deployment_name}' created in namespace '{namespace}' with {replicas} replica(s)."
            )
        else:
            print_info("Dry-run manifest generated successfully.")
    except Exception as exc:
        print_error(f"Deploy failed: {exc}")
        raise typer.Exit(1) from exc
