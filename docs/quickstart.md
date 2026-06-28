# Quickstart

## Connect to a cluster

```python
from kube_orchestrator import KubeClient

client = KubeClient.get_instance()
```

`KubeClient` auto-detects your kubeconfig (`~/.kube/config`) or, when running
inside a cluster, the in-cluster service account.

## List and inspect resources

```python
from kube_orchestrator import PodManager

pods = PodManager(kube_client=client)
for pod in pods.list_pods(namespace="default"):
    print(pod.metadata.name, pods.get_phase(pod.metadata.name, "default"))
```

## Deploy a workload

```python
from kube_orchestrator import DeploymentManager
from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder
from kube_orchestrator.resources.workloads._builders.deployment_builder import DeploymentBuilder

pod_template = (
    PodBuilder("web")
    .with_container("web", "nginx:1.25")
    .with_ports("web", [{"containerPort": 80}])
    .build()
)

builder = (
    DeploymentBuilder(name="web", namespace="default")
    .with_replicas(3)
    .with_selector({"app": "web"})
    .with_pod_template(pod_template)
)

deployments = DeploymentManager(kube_client=client)
deployments.create_deployment(builder=builder, namespace="default")
```

## Apply a YAML manifest (kubectl apply, but from Python)

```python
from kube_orchestrator import ManifestApplier

applier = ManifestApplier(client=client)
applier.apply_file("manifests/deployment.yaml")
```

## Watch for failed rollouts and auto-rollback

```python
from kube_orchestrator import AutoRollback

rollback = AutoRollback(client=client)
rollback.trigger_rollback("web", "default", reason="manual test")
```

## Use the CLI

```bash
kube-orchestrator apply -f manifests/ --namespace default
kube-orchestrator status --namespace default
kube-orchestrator nodes list
ko doctor
```

## Next steps

- [Deploy your first app](guides/deploy-first-app.md)
- [Apply manifests like kubectl](guides/apply-manifests.md)
- [API Reference](api/client.md)
