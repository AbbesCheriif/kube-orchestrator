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

## [1.0.0] - 2026-07-04

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
- GitOps manifest engine: manifest loading (`load_file`/`load_directory`,
  multi-doc YAML, URL/stdin sources), validation (`validate_manifest`, with
  dependency ordering and circular-dependency detection), Jinja2 templating
  with a values file (`render_file`/`render_directory`, mini-Helm style),
  `ManifestApplier` and `ManifestDeleter` for idempotent apply/delete, and a
  `DependencyResolver` for ordered apply + readiness waiting.
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
  unit tests, real cluster support for integration tests). Unit test line
  coverage reaches a genuine 100%, enforced via `--cov-fail-under=100`.
  Integration tests cover the apply/rollback/manifest-engine, HPA, RBAC,
  CRD and scaling workflows end-to-end against a real cluster.
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
- `ClusterHealthReporter`'s health report used field names that didn't
  match what `print_health_report` read, so `doctor` always rendered
  blank sections; `status`/`nodes list` ignored `--output json`/`yaml`
  and always printed a Rich table.
- `apply`, `delete`, `deploy`, `logs` and `rollback` rejected
  `command arg --option value` syntax (only `command --option value arg`
  worked) because Click defaults `allow_interspersed_args=False` on
  commands added to a `Typer` group.
- `configure_logging()` crashed on the first log call:
  `structlog.stdlib.add_logger_name` requires a stdlib `logging.Logger`
  (reads `.name`), which is incompatible with the configured
  `PrintLoggerFactory`.
- `kube_orchestrator/__init__.py` and the `manifest`, `crd`,
  `resources.storage` and `resources.rbac` subpackages declared `__all__`
  without ever importing the names, so `from kube_orchestrator import
  PodManager` (and every other public name) raised `ImportError`;
  `resources.workloads` and `resources.cluster` were each missing several
  managers that already existed (`DeploymentManager`, `ReplicaSetManager`,
  `StatefulSetManager`, `HPAManager`, `NodeManager`).
- `kubernetes-stubs>=28.1.0` in the `dev` extra doesn't exist on PyPI
  (that package's own versioning tops out at `22.6.0.post1`), so
  `pip install -e ".[dev]"` — the exact command `tests.yml` and
  `lint.yml` run — failed outright; `ruff`, used by `lint.yml`, was
  also never declared as a dependency anywhere.
- `black --check .` and `isort --check-only .` both failed (53 and 1
  files respectively, mostly the test suite added this cycle); `bandit
  -r kube_orchestrator/ -ll` failed the "security" job with a Medium
  (unvalidated URL scheme in `load_url`) and a High (Jinja2
  `autoescape=False`) finding, now fixed/documented.
- `release.yml`'s `publish-ghcr` job used `github.repository_owner`
  (`AbbesCheriif`) directly in the image tag; Docker/OCI repository
  names must be lowercase, so every build failed with
  "repository name must be lowercase".
- The Docker image built inside `release.yml` had no `.git` directory
  in its build context, so `setuptools-scm` couldn't derive a version
  and silently fell back to `0.0.0`; `kube-orchestrator --version`
  inside the published `:1.0.0` image would have reported `0.0.0`.
  The real tag version is now passed in via a `VERSION` build-arg.
- `--cov-fail-under=100` was set globally in `pytest.ini`/`pyproject.toml`
  `addopts`, so it also applied to `pytest tests/integration/` in CI —
  which only exercises a handful of workflows against a real cluster and
  can never reach 100% — failing the `integration-tests` job regardless
  of whether the tests themselves passed. The gate now lives only on the
  `unit-tests` job's own command line.
- `test_discovery_finds_installed_crd` reused the same CRD name as the
  previous test in its class; CRD deletion is asynchronous (finalizers),
  so recreating it immediately raced with the prior test's still-pending
  deletion and produced an empty discovery result. It now uses its own
  CRD name.

[Unreleased]: https://github.com/AbbesCheriif/kube-orchestrator/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/AbbesCheriif/kube-orchestrator/releases/tag/v1.0.0
