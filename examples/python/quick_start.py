"""Quick start example — deploy nginx and expose it as a Service."""

from __future__ import annotations

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.resources.networking.service import ServiceManager
from kube_orchestrator.resources.workloads._builders.deployment_builder import (
    DeploymentBuilder,
)
from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder
from kube_orchestrator.resources.workloads.deployment import DeploymentManager

client = KubeClient.get_instance()

pod = (
    PodBuilder("nginx")
    .with_container("nginx", "nginx:1.25")
    .with_ports("nginx", [{"containerPort": 80}])
    .with_resources("nginx", cpu_request="100m", memory_request="128Mi")
)

builder = (
    DeploymentBuilder("nginx", "default")
    .with_replicas(2)
    .with_selector({"app": "nginx"})
    .with_pod_template(pod)
)

dep_manager = DeploymentManager(kube_client=client)
deployment = dep_manager.create_deployment(builder=builder, namespace="default")
print(f"Created: {deployment.metadata.name}")

svc_manager = ServiceManager(kube_client=client)
service = svc_manager.create_clusterip(
    name="nginx",
    namespace="default",
    selector={"app": "nginx"},
    ports=[{"port": 80, "targetPort": 80}],
)
print(f"Service ClusterIP: {service.spec.cluster_ip}")
