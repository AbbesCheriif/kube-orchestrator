# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- N/A

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

---

## [1.0.0] - 2026-06-28

### Added
- Kubernetes client engine (`KubeClient`, `KubeConfig`) with multi-context
  support, retry middleware, timeout management and structured logging.
- `BaseResourceManager` abstract base (Template Method pattern) providing
  generic CRUD, list, patch, watch and wait-for-condition operations for
  every resource manager.
- Full workload coverage: Pod, Deployment, ReplicaSet, StatefulSet,
  DaemonSet, Job, CronJob — each with a fluent builder for every spec field.
- Namespace, ResourceQuota and LimitRange managers.
- Full networking coverage: Service, Ingress, IngressClass, NetworkPolicy,
  Endpoints and EndpointSlices.
- Full storage coverage: ConfigMap, Secret, StorageClass,
  PersistentVolume and PersistentVolumeClaim.
- Full RBAC coverage: Role, ClusterRole, RoleBinding, ClusterRoleBinding,
  ServiceAccount, and an `AccessValidator` for `kubectl auth can-i` checks.
- Node management: cordon, drain, taint/untaint, affinity helpers.
- Cluster resources: HorizontalPodAutoscaler, PriorityClass,
  PodDisruptionBudget, RuntimeClass, Lease, Event querying.
- GitOps manifest engine: `ManifestLoader`, `ManifestValidator` (with
  dependency ordering and circular-dependency detection), `ManifestRenderer`
  (Jinja2 templating with a values file, mini-Helm style), `ManifestApplier`
  and `ManifestDeleter` for idempotent apply/delete.
- CRD framework: `CRDInstaller`, `CustomObjectManager` (Adapter pattern for
  any Custom Resource) and `APIDiscovery` for runtime API/CRD discovery.
- Platform engine: `ClusterHealthReporter` for cluster/workload health
  scoring, `RolloutDetector` + `SnapshotStore` + `AutoRollback` for
  automatic rollback on failed rollouts, `ScalingEngine` with pluggable
  scaling strategies (CPU, memory, custom metric) and a `ResourceWatcher`
  for event-driven watch loops.
- `kube-orchestrator` / `ko` CLI (Typer + Rich): `apply`, `delete`, `deploy`,
  `rollback`, `status`, `nodes`, `doctor`, `logs`, plus `--version`.
- Full unit and integration test suite (pytest, mocked Kubernetes API for
  unit tests, real cluster support for integration tests).
- Multi-stage Dockerfile, docker-compose for local development, and
  MkDocs documentation site with an mkdocstrings-generated API reference.
- CI/CD: lint & type-check workflow (black, isort, ruff, mypy --strict,
  bandit), test workflow (3 Python versions × 3 OS + kind integration
  tests), PR validation (commit-lint, PR size, auto-labeling), Dependabot
  auto-merge, and a release workflow publishing to PyPI via Trusted
  Publishing (OIDC) and to GHCR.

### Fixed
- Console-scripts entry points (`kube-orchestrator`, `ko`) pointed at the
  bare Typer app instead of `main()`, so no command ever registered.
- `setuptools` build-backend was set to a non-existent module, breaking
  `python -m build` entirely.
- `NamespaceScope` and `NamespaceManager.clone_namespace_config` built every
  manager with `client=` instead of the `kube_client=` constructor
  parameter, raising `TypeError` on first use.
- Fifteen resource managers (`LimitRangeManager`, `ResourceQuotaManager`,
  `PriorityClassManager`, `PodDisruptionBudgetManager`, `RuntimeClassManager`,
  `EndpointSliceManager`, `IngressClassManager`, `ClusterRoleManager`,
  `ClusterRoleBindingManager`, `ServiceAccountManager`, `ConfigMapManager`,
  `PersistentVolumeManager`, `PVCManager`, `StorageClassManager`,
  `ReplicaSetManager`) were missing the `_resource_name()` override needed
  for their generic CRUD dispatch, causing every create/get/list/update/
  delete call to 404.
- `KubeClient` was missing the `discovery_v1` and `node_v1` API group
  properties used by `EndpointSliceManager` and `RuntimeClassManager`.
- `ConfigMapManager.create_configmap` sent raw `bytes` in `binary_data`
  instead of base64-encoded strings, which the Kubernetes API rejects.
- `APIDiscovery` referenced a non-existent `KubeClient._client` attribute
  and called a method that doesn't exist on `ApisApi`; API-group resource
  discovery now uses the raw `/apis/{group}/{version}` endpoint.
- `DaemonSetManager` read a non-existent `number_mis_scheduled` status
  field (correct name is `number_misscheduled`).
- `PodManager.attach_ephemeral_container` built a `V1PodSpec` missing the
  required `containers` field.

[Unreleased]: https://github.com/AbbesCheriif/kube-orchestrator/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/AbbesCheriif/kube-orchestrator/releases/tag/v1.0.0
