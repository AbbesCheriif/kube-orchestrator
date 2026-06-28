# kube-orchestrator

[![PyPI version](https://img.shields.io/pypi/v/kube-orchestrator.svg)](https://pypi.org/project/kube-orchestrator/)
[![PyPI downloads](https://img.shields.io/pypi/dm/kube-orchestrator.svg)](https://pypi.org/project/kube-orchestrator/)
[![Python versions](https://img.shields.io/pypi/pyversions/kube-orchestrator.svg)](https://pypi.org/project/kube-orchestrator/)
[![Tests](https://github.com/AbbesCheriif/kube-orchestrator/actions/workflows/tests.yml/badge.svg)](https://github.com/AbbesCheriif/kube-orchestrator/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/codecov/c/github/AbbesCheriif/kube-orchestrator)](https://codecov.io/gh/AbbesCheriif/kube-orchestrator)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/AbbesCheriif/kube-orchestrator/blob/main/LICENSE)

> A full-featured Python SDK for Kubernetes — programmatic kubectl, GitOps engine, platform engineering SDK.

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
- **CLI DevOps Tool** — `ko` command for terminal workflows
- **Fully typed** — PEP 561 compliant, works with mypy and pyright
- **Python 3.10+** — modern Python, full type hints

---

## Installation

```bash
pip install kube-orchestrator
```

See [Installation](installation.md) for Docker and from-source options, and
[Quickstart](quickstart.md) for a five-minute tour of the API.

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
└── cli/                # ko CLI tool
```

---

## Contributing

Contributions are welcome! See [Contributing](contributing.md) for the
development setup, branch/commit conventions and PR process.

---

## License

This project is licensed under the MIT License — see [LICENSE](https://github.com/AbbesCheriif/kube-orchestrator/blob/main/LICENSE) for details.
