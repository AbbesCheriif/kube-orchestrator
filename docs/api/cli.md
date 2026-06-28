# CLI

`kube-orchestrator` (alias `ko`) is a Typer-based CLI that wraps the same
managers documented on the other API Reference pages.

```bash
kube-orchestrator --help
```

## Commands

| Command | Description |
|---|---|
| `apply` | Apply Kubernetes manifests to the cluster |
| `delete` | Delete Kubernetes resources defined in manifests |
| `deploy` | Deploy a container image to Kubernetes |
| `rollback` | Rollback a Deployment to a previous revision |
| `status` | Show cluster and workload status |
| `nodes` | Manage cluster nodes (list, cordon, uncordon, drain, taint, untaint) |
| `doctor` | Diagnose cluster health issues |
| `logs` | Stream or fetch pod logs |

See [Deploy your first app](../guides/deploy-first-app.md) and
[Manage nodes](../guides/manage-nodes.md) for worked examples of each command.
