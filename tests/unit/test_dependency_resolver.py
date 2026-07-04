"""Unit tests for kube_orchestrator.manifest.dependency_resolver."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.manifest.dependency_resolver import DependencyResolver


@pytest.fixture
def resolver(mock_kube_client: MagicMock) -> DependencyResolver:
    return DependencyResolver(client=mock_kube_client, default_timeout=5)


@pytest.mark.unit
class TestResolve:
    def test_orders_manifests_by_dependency(self, resolver: DependencyResolver) -> None:
        manifests = [
            {"kind": "Deployment", "metadata": {"name": "web"}},
            {"kind": "Namespace", "metadata": {"name": "ns"}},
        ]
        ordered = resolver.resolve(manifests)
        assert [m["kind"] for m in ordered] == ["Namespace", "Deployment"]


@pytest.fixture
def core_api_no_namespaced_namespace(mock_kube_client: MagicMock) -> MagicMock:
    # Namespace is cluster-scoped: the real CoreV1Api only has read_namespace
    # (no `_namespaced_` variant). Delete the auto-vivified shadow attribute so
    # NamespaceManager.get_namespace() takes the same fallback branch it does
    # against the real API.
    api = mock_kube_client.core_v1
    delattr(api, "read_namespaced_namespace")
    return api


@pytest.mark.unit
class TestWaitForNamespaceReady:
    def test_returns_true_when_active(
        self,
        resolver: DependencyResolver,
        core_api_no_namespaced_namespace: MagicMock,
    ) -> None:
        ns = MagicMock()
        ns.status.phase = "Active"
        core_api_no_namespaced_namespace.read_namespace.return_value = ns
        assert resolver.wait_for_namespace_ready("team-a", timeout=5) is True

    def test_swallows_errors_and_times_out(
        self,
        resolver: DependencyResolver,
        core_api_no_namespaced_namespace: MagicMock,
    ) -> None:
        core_api_no_namespaced_namespace.read_namespace.side_effect = RuntimeError(
            "boom"
        )
        with patch("kube_orchestrator.manifest.dependency_resolver.time.sleep"):
            assert resolver.wait_for_namespace_ready("team-a", timeout=0.05) is False

    def test_uses_default_timeout_when_not_given(
        self,
        resolver: DependencyResolver,
        core_api_no_namespaced_namespace: MagicMock,
    ) -> None:
        ns = MagicMock()
        ns.status.phase = "Terminating"
        core_api_no_namespaced_namespace.read_namespace.return_value = ns
        with (
            patch(
                "kube_orchestrator.manifest.dependency_resolver.time.monotonic",
                side_effect=[0, 0, 999],
            ),
            patch("kube_orchestrator.manifest.dependency_resolver.time.sleep"),
        ):
            assert resolver.wait_for_namespace_ready("team-a") is False


@pytest.mark.unit
class TestWaitForCrdReady:
    def test_returns_true_when_established(
        self, resolver: DependencyResolver, mock_kube_client: MagicMock
    ) -> None:
        cond = MagicMock(type="Established", status="True")
        crd = MagicMock()
        crd.status.conditions = [cond]
        mock_kube_client.api_extensions_v1.read_custom_resource_definition.return_value = (
            crd
        )
        assert resolver.wait_for_crd_ready("foos.example.com", timeout=5) is True

    def test_swallows_errors_and_times_out(
        self, resolver: DependencyResolver, mock_kube_client: MagicMock
    ) -> None:
        mock_kube_client.api_extensions_v1.read_custom_resource_definition.side_effect = RuntimeError(
            "boom"
        )
        with patch("kube_orchestrator.manifest.dependency_resolver.time.sleep"):
            assert (
                resolver.wait_for_crd_ready("foos.example.com", timeout=0.05) is False
            )


@pytest.mark.unit
class TestWaitForResourceReady:
    def test_dispatches_to_namespace_wait(self, resolver: DependencyResolver) -> None:
        manifest = {"kind": "Namespace", "metadata": {"name": "team-a"}}
        with patch.object(
            resolver, "wait_for_namespace_ready", return_value=True
        ) as mock_wait:
            assert resolver.wait_for_resource_ready(manifest) is True
            mock_wait.assert_called_once_with("team-a", None)

    def test_dispatches_to_crd_wait(self, resolver: DependencyResolver) -> None:
        manifest = {
            "kind": "CustomResourceDefinition",
            "metadata": {"name": "foos.example.com"},
        }
        with patch.object(
            resolver, "wait_for_crd_ready", return_value=True
        ) as mock_wait:
            assert resolver.wait_for_resource_ready(manifest) is True
            mock_wait.assert_called_once_with("foos.example.com", None)

    def test_returns_true_for_unrecognized_kind(
        self, resolver: DependencyResolver
    ) -> None:
        manifest = {"kind": "TotallyUnknown", "metadata": {"name": "x"}}
        assert resolver.wait_for_resource_ready(manifest) is True

    def test_generic_wait_returns_true_when_resource_found(
        self, resolver: DependencyResolver
    ) -> None:
        manifest = {
            "kind": "ConfigMap",
            "metadata": {"name": "cm", "namespace": "default"},
        }
        with patch("kube_orchestrator.manifest.validator.route_by_kind") as mock_route:
            manager_cls = MagicMock()
            manager_cls.return_value.get.return_value = MagicMock()
            mock_route.return_value = manager_cls

            assert resolver.wait_for_resource_ready(manifest, timeout=5) is True

    def test_generic_wait_swallows_errors_and_times_out(
        self, resolver: DependencyResolver
    ) -> None:
        manifest = {
            "kind": "ConfigMap",
            "metadata": {"name": "cm", "namespace": "default"},
        }
        with patch("kube_orchestrator.manifest.validator.route_by_kind") as mock_route:
            manager_cls = MagicMock()
            manager_cls.return_value.get.side_effect = RuntimeError("boom")
            mock_route.return_value = manager_cls

            with patch("kube_orchestrator.manifest.dependency_resolver.time.sleep"):
                assert resolver.wait_for_resource_ready(manifest, timeout=0.05) is False
