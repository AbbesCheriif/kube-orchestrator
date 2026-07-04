# GitOps workflow

`kube-orchestrator` is designed to be the "apply engine" behind a GitOps
pipeline: manifests live in Git, CI renders and validates them, and a deploy
step applies them idempotently.

## A minimal CI apply step

```yaml
# .github/workflows/deploy.yml (in your own app's repo)
- name: Apply manifests
  run: |
    pip install kube-orchestrator
    kube-orchestrator apply -f k8s/ --recursive --namespace production --wait
```

## Validate before you apply

```python
from kube_orchestrator.manifest.loader import load_directory
from kube_orchestrator.manifest.validator import validate_manifest, order_by_dependency

manifests = load_directory("k8s/", recursive=True)
ordered = order_by_dependency(manifests)

errors = []
for m in ordered:
    errors.extend(validate_manifest(m))

if errors:
    raise SystemExit("\n".join(errors))
```

`order_by_dependency` applies Namespaces, CRDs and StorageClasses before the
workloads that depend on them, matching `kubectl apply -f` ordering
conventions.

## Auto-rollback on failed deploys

Wire `AutoRollback` into your deploy step so a bad rollout reverts itself
instead of paging someone at 3am:

```python
from kube_orchestrator import KubeClient, AutoRollback
from kube_orchestrator.rollback.detector import RolloutDetector

client = KubeClient.get_instance()
detector = RolloutDetector(client)
rollback = AutoRollback(client)

if detector.detect_failed_rollout("my-app", "production"):
    rollback.trigger_rollback("my-app", "production", reason="failed rollout in CI")
    raise SystemExit(1)
```

## Take a snapshot before every deploy

```python
from kube_orchestrator.rollback.snapshot import SnapshotStore

store = SnapshotStore(client)
store.take_snapshot("my-app", "production")
```

Snapshots are what `AutoRollback` reverts to when no specific revision is
requested.
