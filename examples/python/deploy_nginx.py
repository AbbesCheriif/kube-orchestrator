"""Deploy nginx with health checks, resource limits and HPA."""
from __future__ import annotations

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.resources.cluster.hpa import HPAManager
from kube_orchestrator.resources.workloads._builders.deployment_builder import DeploymentBuilder
from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder
from kube_orchestrator.resources.workloads.deployment import DeploymentManager

client = KubeClient.get_instance()

pod = (
    PodBuilder("nginx")
    .with_container("nginx", "nginx:1.25")
    .with_ports("nginx", [{"containerPort": 80}])
    .with_resources("nginx", cpu_request="100m", memory_request="128Mi", cpu_limit="200m", memory_limit="256Mi")
    .with_liveness_probe("nginx", http_get={"path": "/", "port": 80}, initial_delay=10, period=10)
    .with_readiness_probe("nginx", http_get={"path": "/", "port": 80}, initial_delay=5, period=5)
)

builder = (
    DeploymentBuilder("nginx", "default")
    .with_replicas(2)
    .with_selector({"app": "nginx"})
    .with_rolling_update(max_surge=1, max_unavailable=0)
    .with_pod_template(pod)
)

dep_manager = DeploymentManager(kube_client=client)
deployment = dep_manager.create_deployment(builder=builder, namespace="default")
print(f"Deployment created: {deployment.metadata.name}")

dep_manager.wait_for_rollout("nginx", "default", timeout_seconds=120)
print("Rollout complete!")

hpa_manager = HPAManager(kube_client=client)
hpa = hpa_manager.create_cpu_hpa(
    name="nginx-hpa",
    namespace="default",
    target_kind="Deployment",
    target_name="nginx",
    min_replicas=2,
    max_replicas=10,
    target_cpu_utilization=70,
)
print(f"HPA created: {hpa.metadata.name} (min={hpa.spec.min_replicas}, max={hpa.spec.max_replicas})")
