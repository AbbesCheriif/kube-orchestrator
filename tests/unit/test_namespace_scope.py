"""Unit tests for kube_orchestrator.resources.cluster.namespace_scope."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kube_orchestrator.resources.cluster.namespace_scope import NamespaceScope
from kube_orchestrator.resources.workloads.cronjob import CronJobManager
from kube_orchestrator.resources.workloads.daemonset import DaemonSetManager
from kube_orchestrator.resources.workloads.deployment import DeploymentManager
from kube_orchestrator.resources.workloads.job import JobManager
from kube_orchestrator.resources.workloads.pod import PodManager
from kube_orchestrator.resources.workloads.statefulset import StatefulSetManager


@pytest.fixture
def scope(mock_kube_client: MagicMock) -> NamespaceScope:
    return NamespaceScope("production", mock_kube_client)


@pytest.mark.unit
class TestNamespaceScopeManagers:
    def test_pods_returns_scoped_pod_manager(self, scope: NamespaceScope) -> None:
        manager = scope.pods()
        assert isinstance(manager, PodManager)
        assert manager.default_namespace == "production"

    def test_deployments_returns_scoped_deployment_manager(
        self, scope: NamespaceScope
    ) -> None:
        manager = scope.deployments()
        assert isinstance(manager, DeploymentManager)
        assert manager.default_namespace == "production"

    def test_statefulsets_returns_scoped_statefulset_manager(
        self, scope: NamespaceScope
    ) -> None:
        manager = scope.statefulsets()
        assert isinstance(manager, StatefulSetManager)
        assert manager.default_namespace == "production"

    def test_daemonsets_returns_scoped_daemonset_manager(
        self, scope: NamespaceScope
    ) -> None:
        manager = scope.daemonsets()
        assert isinstance(manager, DaemonSetManager)
        assert manager.default_namespace == "production"

    def test_jobs_returns_scoped_job_manager(self, scope: NamespaceScope) -> None:
        manager = scope.jobs()
        assert isinstance(manager, JobManager)
        assert manager.default_namespace == "production"

    def test_cronjobs_returns_scoped_cronjob_manager(
        self, scope: NamespaceScope
    ) -> None:
        manager = scope.cronjobs()
        assert isinstance(manager, CronJobManager)
        assert manager.default_namespace == "production"

    def test_services_returns_scoped_service_manager(
        self, scope: NamespaceScope
    ) -> None:
        from kube_orchestrator.resources.networking.service import ServiceManager

        manager = scope.services()
        assert isinstance(manager, ServiceManager)
        assert manager.default_namespace == "production"

    def test_configmaps_returns_scoped_configmap_manager(
        self, scope: NamespaceScope
    ) -> None:
        from kube_orchestrator.resources.storage.configmap import ConfigMapManager

        manager = scope.configmaps()
        assert isinstance(manager, ConfigMapManager)
        assert manager.default_namespace == "production"

    def test_secrets_returns_scoped_secret_manager(
        self, scope: NamespaceScope
    ) -> None:
        from kube_orchestrator.resources.storage.secret import SecretManager

        manager = scope.secrets()
        assert isinstance(manager, SecretManager)
        assert manager.default_namespace == "production"

    def test_pvcs_returns_scoped_pvc_manager(self, scope: NamespaceScope) -> None:
        from kube_orchestrator.resources.storage.persistent_volume_claim import (
            PVCManager,
        )

        manager = scope.pvcs()
        assert isinstance(manager, PVCManager)
        assert manager.default_namespace == "production"


@pytest.mark.unit
class TestNamespaceScopeContextManager:
    def test_enter_returns_self(
        self, scope: NamespaceScope, mock_kube_client: MagicMock
    ) -> None:
        with scope as entered:
            assert entered is scope

    def test_exit_does_not_suppress_exceptions(self, scope: NamespaceScope) -> None:
        with pytest.raises(ValueError, match="boom"):
            with scope:
                raise ValueError("boom")
