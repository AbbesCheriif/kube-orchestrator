# Architecture

```
kube-orchestrator
├── core/               KubeClient (singleton), KubeConfig, retry middleware,
│                       structured logging, Settings, exception hierarchy
├── resources/
│   ├── base.py         BaseResourceManager — Template Method for CRUD
│   ├── workloads/      Pod, Deployment, StatefulSet, DaemonSet, ReplicaSet,
│   │                   Job, CronJob (+ fluent builders in _builders/)
│   ├── networking/     Service, Ingress, NetworkPolicy, Endpoints/Slices
│   ├── storage/        ConfigMap, Secret, PV, PVC, StorageClass
│   ├── rbac/           Role, ClusterRole, Bindings, ServiceAccount,
│   │                   AccessValidator
│   └── cluster/        Namespace, Node, ResourceQuota, LimitRange, HPA,
│                       PriorityClass, PodDisruptionBudget, RuntimeClass
├── manifest/           Loader, Validator, Renderer, ManifestApplier,
│                       ManifestDeleter — the GitOps engine
├── crd/                CRDInstaller, CustomObjectManager, APIDiscovery
├── monitoring/         ClusterHealthReporter
├── rollback/           RolloutDetector, SnapshotStore, AutoRollback
├── scaling/            ScalingEngine, scaling strategies
├── controllers/        ResourceWatcher (event-driven watch loops)
└── cli/                Typer CLI (kube-orchestrator / ko)
```

## Design patterns

- **Singleton** — `KubeClient` holds one `ApiClient` per process and lazily
  builds each typed API group (`core_v1`, `apps_v1`, ...) from it.
- **Template Method** — `BaseResourceManager` implements `get`/`list`/
  `create`/`update`/`patch`/`delete`/`watch` once, generically, by looking up
  the right `kubernetes-client` method name at runtime
  (`list_namespaced_<resource_name>`, `create_<resource_name>`, ...).
  Concrete managers only implement `_get_api()`, `_kind()` and
  `_api_version()` (and `_resource_name()` when the Kind doesn't map
  losslessly to snake_case, e.g. `ClusterRoleBinding` → `cluster_role_binding`).
- **Builder** — `PodBuilder`, `DeploymentBuilder`, `StatefulSetBuilder` and
  friends provide a fluent, chainable API over the dozens of optional fields
  each Kubernetes spec supports.
- **Adapter** — `CustomObjectManager` wraps the generic `CustomObjectsApi`
  behind the same interface as the built-in resource managers, so any CRD
  can be driven without hand-written bindings.

## Request flow

```
your code
   │
   ▼
BaseResourceManager subclass (e.g. PodManager)
   │  _get_api() → typed kubernetes-client API object
   │  _resource_name() → snake_case name used to build the method name
   ▼
kubernetes-client (ApiClient + urllib3)
   │
   ▼
Kubernetes API server
```

Retries, timeouts and rate-limit handling live in `core/middleware.py` and
wrap every outbound call; `core/exceptions.py` translates raw
`ApiException`s into the library's own exception hierarchy so callers can
catch `ResourceNotFoundError` instead of checking `exc.status == 404`
themselves.
