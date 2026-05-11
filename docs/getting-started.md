# Getting Started

## Installation

Install kube-orchestrator from PyPI:

```bash
pip install kube-orchestrator
```

For development dependencies:

```bash
pip install "kube-orchestrator[dev]"
```

For documentation dependencies:

```bash
pip install "kube-orchestrator[docs]"
```

---

## Prerequisites

- Python 3.10 or higher
- A running Kubernetes cluster (local or remote)
- A valid kubeconfig file (usually at `~/.kube/config`)

---

## Quick Start

### Connect to your cluster

```python
from kube_orchestrator import KubeClient

client = KubeClient.get_instance()
```

By default, kube-orchestrator auto-detects your kubeconfig. You can also specify a path:

```python
from kube_orchestrator.core import KubeConfig

config = KubeConfig()
config.load_from_file("~/.kube/config")
```

---

### List pods

```python
from kube_orchestrator import KubeClient, PodManager

client = KubeClient.get_instance()
pod_manager = PodManager(client)

pods = pod_manager.list(namespace="default")
for pod in pods:
    print(pod.metadata.name, pod.status.phase)
```

---

### Create a deployment

```python
from kube_orchestrator import KubeClient, DeploymentManager

client = KubeClient.get_instance()
deploy_manager = DeploymentManager(client)

manifest = {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {"name": "my-app", "namespace": "default"},
    "spec": {
        "replicas": 3,
        "selector": {"matchLabels": {"app": "my-app"}},
        "template": {
            "metadata": {"labels": {"app": "my-app"}},
            "spec": {
                "containers": [
                    {"name": "my-app", "image": "nginx:latest"}
                ]
            },
        },
    },
}

deploy_manager.apply(manifest, namespace="default")
```

---

### Apply a manifest file

```python
from kube_orchestrator import KubeClient, ManifestApplier

client = KubeClient.get_instance()
applier = ManifestApplier(client)

applier.apply_file("manifests/deployment.yaml")
```

---

### Auto rollback on failure

```python
from kube_orchestrator import KubeClient, AutoRollback

client = KubeClient.get_instance()
rollback = AutoRollback(client)

rollback.watch(name="my-app", namespace="default", timeout=300)
```

---

## CLI Usage

kube-orchestrator ships with a CLI tool available as `ko` or `kube-orchestrator`:

```bash
ko get pods --namespace default
ko apply -f manifests/deployment.yaml
ko rollback deployment my-app --namespace default
```

---

## Configuration

You can configure kube-orchestrator via environment variables or a `.env` file:

```bash
KUBECONFIG=~/.kube/config
KUBE_CONTEXT=
KUBE_NAMESPACE=default
LOG_LEVEL=INFO
LOG_FORMAT=json
```

See [`.env.example`](https://github.com/AbbesCheriif/kube-orchestrator/blob/main/.env.example) for all available options.
