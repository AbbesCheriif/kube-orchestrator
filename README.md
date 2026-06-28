# kube-orchestrator

[![PyPI version](https://img.shields.io/pypi/v/kube-orchestrator.svg)](https://pypi.org/project/kube-orchestrator/)
[![PyPI downloads](https://img.shields.io/pypi/dm/kube-orchestrator.svg)](https://pypi.org/project/kube-orchestrator/)
[![Python versions](https://img.shields.io/pypi/pyversions/kube-orchestrator.svg)](https://pypi.org/project/kube-orchestrator/)
[![Tests](https://github.com/AbbesCheriif/kube-orchestrator/actions/workflows/tests.yml/badge.svg)](https://github.com/AbbesCheriif/kube-orchestrator/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/codecov/c/github/AbbesCheriif/kube-orchestrator)](https://codecov.io/gh/AbbesCheriif/kube-orchestrator)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A full-featured Python SDK for Kubernetes — programmatic kubectl, GitOps engine, platform engineering SDK.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Supported Resources](#supported-resources)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Features

- **Full Kubernetes resource coverage** — Pods, Deployments, StatefulSets, DaemonSets, Jobs, CronJobs, and more
- **Programmatic kubectl** — apply, delete, get, list, patch any resource from Python
- **GitOps engine** — load and apply YAML/JSON manifests with full validation
- **Manifest Renderer** — lightweight Helm-like templating engine
- **Auto Rollback** — detect failures and roll back deployments automatically
- **Scaling Engine** — HPA management and custom scaling watchers
- **RBAC management** — Roles, ClusterRoles, Bindings, ServiceAccounts
- **Network management** — Services, Ingress, NetworkPolicies, Endpoints
- **Storage management** — ConfigMaps, Secrets, PVs, PVCs, StorageClasses
- **CRD Framework** — install and manage Custom Resource Definitions
- **CLI DevOps Tool** — `kube-orch` command for terminal workflows
- **Fully typed** — PEP 561 compliant, works with mypy and pyright
- **Python 3.10+** — modern Python, full type hints

---

## Installation

```bash
pip install kube-orchestrator
```

---

## Quick Start

```python
from kube_orchestrator import KubeClient, PodManager

# Connect to cluster
client = KubeClient.from_kubeconfig()

# List all pods in a namespace
pod_manager = PodManager(client)
pods = pod_manager.list(namespace="default")
for pod in pods:
    print(pod.name, pod.status.phase)
```

```python
from kube_orchestrator import KubeClient, DeploymentManager

client = KubeClient.from_kubeconfig()
deploy_manager = DeploymentManager(client)

# Scale a deployment
deploy_manager.scale(name="my-app", namespace="default", replicas=5)
```

```python
from kube_orchestrator import KubeClient, ManifestApplier

client = KubeClient.from_kubeconfig()
applier = ManifestApplier(client)

# Apply a manifest file (like kubectl apply -f)
applier.apply_file("manifests/deployment.yaml")
```

```python
from kube_orchestrator import KubeClient, AutoRollback

client = KubeClient.from_kubeconfig()
rollback = AutoRollback(client)

# Watch a deployment and auto-rollback on failure
rollback.watch(name="my-app", namespace="default", timeout=300)
```

```python
from kube_orchestrator import KubeClient, ClusterHealthReporter

client = KubeClient.from_kubeconfig()
reporter = ClusterHealthReporter(client)

# Get a full cluster health report
report = reporter.full_report()
print(report.summary())
```

---

## Architecture

```
kube-orchestrator
├── core/               # KubeClient, KubeConfig, logging, errors
├── resources/
│   ├── workloads/      # Pod, Deployment, StatefulSet, DaemonSet, Job, CronJob
│   ├── networking/     # Service, Ingress, NetworkPolicy, Endpoints
│   ├── storage/        # ConfigMap, Secret, PV, PVC, StorageClass
│   ├── rbac/           # Role, ClusterRole, Bindings, ServiceAccount
│   └── cluster/        # Namespace, Node, HPA, ResourceQuota, LimitRange
├── manifest/           # Loader, Validator, Renderer, Applier
├── crd/                # CRD installer and custom object manager
├── monitoring/         # ClusterHealthReporter
├── rollback/           # AutoRollback system
├── scaling/            # ScalingEngine, ResourceWatcher
└── cli/                # kube-orch CLI tool
```

---

## Supported Resources

| Resource | List | Get | Create | Update | Delete | Patch |
|---|---|---|---|---|---|---|
| Pod | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Deployment | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| StatefulSet | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| DaemonSet | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ReplicaSet | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Job | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CronJob | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Service | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ingress | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| NetworkPolicy | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ConfigMap | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Secret | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| PersistentVolume | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| PersistentVolumeClaim | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| StorageClass | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Namespace | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Node | ✅ | ✅ | — | ✅ | — | ✅ |
| Role / ClusterRole | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| RoleBinding / ClusterRoleBinding | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ServiceAccount | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HPA | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ResourceQuota | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CRD | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Documentation

Full documentation, including the API reference and guides, lives in the
[`docs/`](docs/) folder — start at [`docs/index.md`](docs/index.md).

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a PR.

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [kubernetes-client/python](https://github.com/kubernetes-client/python) — official Kubernetes Python client
- [kubectl](https://kubernetes.io/docs/reference/kubectl/) — inspiration for the CLI design
