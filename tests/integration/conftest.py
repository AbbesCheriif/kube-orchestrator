"""Integration test fixtures — require a real Kubernetes cluster (kind)."""
from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if no cluster is reachable."""
    skip_integration = pytest.mark.skip(reason="No Kubernetes cluster available (set KUBECONFIG or run kind create cluster)")
    for item in items:
        if "integration" in item.keywords:
            try:
                from kubernetes import config as k8s_config

                k8s_config.load_kube_config()
            except Exception:
                item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def kube_client():
    """Real KubeClient for integration tests."""
    pytest.importorskip("kubernetes")
    from kube_orchestrator.core.client import KubeClient

    KubeClient.reset()
    return KubeClient.get_instance()


@pytest.fixture
def test_namespace(kube_client) -> str:
    """Create and yield a unique temporary namespace, then delete it."""
    import uuid

    from kube_orchestrator.resources.cluster.namespace import NamespaceManager

    ns_name = f"ko-test-{uuid.uuid4().hex[:8]}"
    manager = NamespaceManager(kube_client=kube_client)
    try:
        manager.create_namespace(ns_name)
    except Exception:
        pass
    yield ns_name
    try:
        manager.delete_namespace(ns_name)
    except Exception:
        pass
