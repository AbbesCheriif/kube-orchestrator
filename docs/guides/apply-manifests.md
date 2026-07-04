# Apply manifests like kubectl

## A single file

```bash
kube-orchestrator apply -f manifests/deployment.yaml --namespace default
```

```python
from kube_orchestrator import KubeClient, ManifestApplier

client = KubeClient.get_instance()
applier = ManifestApplier(client=client)
results = applier.apply_file("manifests/deployment.yaml", namespace="default")
for r in results:
    print(r["action"], r.get("resource", {}).get("kind"))
```

## A whole directory

```bash
kube-orchestrator apply -f manifests/ --recursive --namespace default
```

```python
applier.apply_directory("manifests/", namespace="default", recursive=True)
```

## Dry-run first

```bash
kube-orchestrator apply -f manifests/ --dry-run
```

```python
plan = applier.dry_run_file("manifests/deployment.yaml")
for step in plan:
    print(step["action"], step["manifest"].get("kind"))
```

## Templated manifests with a values file

```bash
kube-orchestrator apply -f manifests/deployment.yaml.j2 --values values.yaml
```

```python
applier.apply_file("manifests/deployment.yaml.j2", values={"replicas": 3, "image": "nginx:1.25"})
```

See [GitOps workflow](gitops.md) for wiring this into a CI/CD pipeline.
