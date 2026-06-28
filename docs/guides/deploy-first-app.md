# Deploy your first app

## With the CLI

```bash
kube-orchestrator deploy nginx:1.25 \
  --name my-app \
  --namespace default \
  --replicas 3 \
  --port 80 \
  --cpu-request 100m \
  --memory-request 128Mi
```

Add `--dry-run` to preview the generated Deployment without creating it.

Check the rollout:

```bash
kube-orchestrator status --namespace default
```

Roll it back if something goes wrong:

```bash
kube-orchestrator rollback my-app --namespace default
```

## With Python

```python
from kube_orchestrator import KubeClient, DeploymentManager
from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder
from kube_orchestrator.resources.workloads._builders.deployment_builder import DeploymentBuilder

client = KubeClient.get_instance()

pod_template = (
    PodBuilder("my-app")
    .with_container("my-app", "nginx:1.25")
    .with_ports("my-app", [{"containerPort": 80}])
    .with_resources("my-app", cpu_request="100m", memory_request="128Mi")
    .build()
)

builder = (
    DeploymentBuilder(name="my-app", namespace="default")
    .with_replicas(3)
    .with_selector({"app": "my-app"})
    .with_pod_template(pod_template)
)

deployments = DeploymentManager(kube_client=client)
deployment = deployments.create_deployment(builder=builder, namespace="default")
deployments.wait_for_rollout("my-app", "default", timeout_seconds=120)
```
