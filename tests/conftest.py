"""Root test fixtures shared across all test modules."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.core.context import ExecutionContext


@pytest.fixture
def mock_kube_client() -> MagicMock:
    # Managers access APIs as properties (self.client.core_v1), not as calls.
    # MagicMock auto-creates attributes, so no setup needed.
    return MagicMock()


@pytest.fixture
def mock_core_v1(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.core_v1


@pytest.fixture
def mock_apps_v1(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.apps_v1


@pytest.fixture
def mock_networking_v1(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.networking_v1


@pytest.fixture
def mock_rbac_v1(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.rbac_v1


@pytest.fixture
def mock_batch_v1(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.batch_v1


@pytest.fixture
def mock_storage_v1(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.storage_v1


@pytest.fixture
def sample_pod_manifest() -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "test-pod", "namespace": "default"},
        "spec": {
            "containers": [
                {"name": "app", "image": "nginx:latest", "ports": [{"containerPort": 80}]}
            ]
        },
    }


@pytest.fixture
def sample_deployment_manifest() -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "test-deploy", "namespace": "default"},
        "spec": {
            "replicas": 2,
            "selector": {"matchLabels": {"app": "test"}},
            "template": {
                "metadata": {"labels": {"app": "test"}},
                "spec": {
                    "containers": [{"name": "app", "image": "nginx:latest"}]
                },
            },
        },
    }


@pytest.fixture
def fake_namespace() -> str:
    return "test-namespace"


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(namespace="default", dry_run=False, timeout=30)
