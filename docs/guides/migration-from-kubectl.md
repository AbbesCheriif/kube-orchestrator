# Migrating from kubectl

`kube-orchestrator` mirrors the kubectl commands you already know, both as a
CLI and as a Python API.

| kubectl | kube-orchestrator CLI | kube-orchestrator Python |
|---|---|---|
| `kubectl apply -f manifest.yaml` | `kube-orchestrator apply -f manifest.yaml` | `ManifestApplier(client=client).apply_file("manifest.yaml")` |
| `kubectl delete -f manifest.yaml` | `kube-orchestrator delete -f manifest.yaml` | `ManifestDeleter(client=client).delete_file("manifest.yaml")` |
| `kubectl get pods -n default` | `kube-orchestrator status -n default` | `PodManager(kube_client=client).list_pods(namespace="default")` |
| `kubectl rollout undo deployment/app` | `kube-orchestrator rollback app` | `AutoRollback(client).rollback_to_revision("app", "default", revision)` |
| `kubectl cordon node1` | `kube-orchestrator nodes cordon node1` | `NodeManager(kube_client=client).cordon("node1")` |
| `kubectl drain node1` | `kube-orchestrator nodes drain node1` | `NodeManager(kube_client=client).drain("node1")` |
| `kubectl taint nodes node1 k=v:NoSchedule` | `kube-orchestrator nodes taint node1 k v NoSchedule` | `NodeManager(kube_client=client).add_taint("node1", "k", "v", "NoSchedule")` |
| `kubectl auth can-i create pods` | — | `AccessValidator(client).can_i("create", "pods")` |

## Why go beyond kubectl?

- **Composable in Python** — build manifests programmatically with the
  fluent builders instead of templating YAML strings by hand.
- **Typed** — every manager is fully typed (PEP 561, `py.typed` included),
  so your editor autocompletes fields instead of you guessing at
  `kubectl explain` output.
- **Built-in health & rollback** — `ClusterHealthReporter` and
  `AutoRollback` give you monitoring and self-healing without writing a
  separate controller.
- **One dependency** — `pip install kube-orchestrator` gives you the same
  coverage as kubectl + helm + a bit of kubectl-plugin glue, from Python.
