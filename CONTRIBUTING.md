# Contributing to kube-orchestrator

Thank you for your interest in contributing! This document explains how to get
started and how to submit contributions.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Branch Naming Convention](#branch-naming-convention)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Code Review Guidelines](#code-review-guidelines)
- [Running Tests](#running-tests)
- [Running Linters](#running-linters)
- [Adding a New Resource Manager](#adding-a-new-resource-manager)

---

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/kube-orchestrator.git
   cd kube-orchestrator
   ```
3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/AbbesCheriif/kube-orchestrator.git
   ```

---

## Development Setup

Run the setup script to install all dependencies and pre-commit hooks:

```bash
bash scripts/install_dev.sh
```

Or manually:

```bash
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

pip install -e ".[dev,docs]"
pre-commit install
pre-commit install --hook-type commit-msg
```

Verify your setup:

```bash
python -c "import kube_orchestrator; print(kube_orchestrator.__version__)"
kube-orchestrator --version
```

---

## Branch Naming Convention

All branches must be created from `develop`, never from `main`.

| Type        | Pattern                         | Example                        |
|-------------|---------------------------------|--------------------------------|
| Feature     | `feat/<short-description>`      | `feat/pod-manager`             |
| Bug fix     | `fix/<short-description>`       | `fix/namespace-delete-timeout` |
| Docs        | `docs/<short-description>`      | `docs/add-hpa-guide`           |
| Tests       | `test/<short-description>`      | `test/statefulset-unit`        |
| CI/CD       | `ci/<short-description>`        | `ci/add-coverage-badge`        |
| Refactor    | `refactor/<short-description>`  | `refactor/base-manager`        |

```bash
git checkout develop
git pull upstream develop
git checkout -b feat/my-feature
```

---

## Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
Every commit message **must** follow this format:

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

### Types

| Type       | When to use                                      |
|------------|--------------------------------------------------|
| `feat`     | A new feature or resource manager                |
| `fix`      | A bug fix                                        |
| `docs`     | Documentation changes only                       |
| `test`     | Adding or updating tests                         |
| `ci`       | CI/CD configuration changes                      |
| `chore`    | Maintenance tasks (deps update, config, etc.)    |
| `refactor` | Code refactoring without behavior change         |
| `perf`     | Performance improvement                          |

### Examples

```bash
feat(pod): add exec_command and stream_logs methods
fix(deployment): handle rollout timeout correctly
docs(readme): add quick start examples
test(statefulset): add ordered scale unit tests
ci(release): add pypi trusted publishing workflow
chore(deps): bump kubernetes to 29.0.0
```

Pre-commit will automatically reject commits that don't follow this format.

---

## Pull Request Process

1. Make sure all tests pass locally before opening a PR
2. Make sure linters pass: `ruff check . && mypy kube_orchestrator/`
3. Update `CHANGELOG.md` under `[Unreleased]` with a summary of your changes
4. Open a PR **targeting `develop`**, never `main`
5. Fill in the PR template completely
6. Request a review from a maintainer
7. Address all review comments before merge

PRs that don't pass CI checks will not be merged.

---

## Code Review Guidelines

As a reviewer:

- Be constructive and specific in feedback
- Approve only if you have read and understood all changes
- Check that new code has corresponding tests
- Verify that public methods have docstrings

As an author:

- Respond to all comments before requesting re-review
- Don't force-push after a review has started
- Keep PRs focused — one feature or fix per PR

---

## Running Tests

```bash
# All unit tests
pytest tests/unit/ -v

# All tests with coverage report
pytest tests/ --cov=kube_orchestrator --cov-report=term-missing

# A specific test file
pytest tests/unit/test_pod_manager.py -v

# Only fast tests (skip slow/integration)
pytest tests/unit/ -m "not slow" -v
```

Integration tests require a running Kubernetes cluster (e.g. `kind`):

```bash
kind create cluster --name kube-orchestrator-test
pytest tests/integration/ -v -m integration
kind delete cluster --name kube-orchestrator-test
```

---

## Running Linters

```bash
# Format code
black .
isort .

# Lint
ruff check .

# Type checking
mypy kube_orchestrator/

# Security scan
bandit -r kube_orchestrator/ -ll

# Run all pre-commit hooks manually
pre-commit run --all-files
```

---

## Adding a New Resource Manager

Every new Kubernetes resource manager must follow this template:

1. **Create the file** in the correct subpackage:
   ```
   kube_orchestrator/resources/<category>/<resource_name>.py
   ```

2. **Inherit from `BaseResourceManager`**:
   ```python
   from kube_orchestrator.resources.base import BaseResourceManager
   from kubernetes.client import CoreV1Api   # use the right API group

   class MyResourceManager(BaseResourceManager):

       def _get_api(self):
           return self.client.core_v1()

       def _kind(self) -> str:
           return "MyResource"

       def _api_version(self) -> str:
           return "v1"
   ```

3. **Type all method signatures** — no untyped parameters allowed

4. **Add a Google-style docstring** to every public method:
   ```python
   def create_resource(self, name: str, namespace: str) -> V1MyResource:
       """Create a MyResource in the given namespace.

       Args:
           name: The name of the resource.
           namespace: The Kubernetes namespace.

       Returns:
           The created V1MyResource object.

       Raises:
           ResourceAlreadyExistsError: If the resource already exists.
       """
   ```

5. **Export from the subpackage `__init__.py`**:
   ```python
   # kube_orchestrator/resources/<category>/__init__.py
   from kube_orchestrator.resources.<category>.<resource_name> import MyResourceManager

   __all__ = ["MyResourceManager"]
   ```

6. **Write unit tests** in `tests/unit/test_<resource_name>_manager.py`

7. **Update `CHANGELOG.md`** under `[Unreleased] > Added`

---

## Questions?

Open a [GitHub Discussion](https://github.com/AbbesCheriif/kube-orchestrator/discussions)
or file an issue using the Question template.
