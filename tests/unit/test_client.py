"""Unit tests for KubeClient singleton."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.core.client import KubeClient


@pytest.mark.unit
class TestKubeClientSingleton:
    def setup_method(self) -> None:
        KubeClient.reset()

    def teardown_method(self) -> None:
        KubeClient.reset()

    def test_get_instance_returns_same_object(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeConfig"),
            patch("kube_orchestrator.core.client.client"),
        ):
            inst1 = KubeClient.get_instance()
            inst2 = KubeClient.get_instance()
            assert inst1 is inst2

    def test_reset_clears_instance(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeConfig"),
            patch("kube_orchestrator.core.client.client"),
        ):
            inst1 = KubeClient.get_instance()
            KubeClient.reset()
            inst2 = KubeClient.get_instance()
            assert inst1 is not inst2

    def test_core_v1_returns_api(self) -> None:
        mock_api = MagicMock()
        with (
            patch("kube_orchestrator.core.client.KubeConfig"),
            patch("kube_orchestrator.core.client.client") as mock_client_mod,
        ):
            mock_client_mod.CoreV1Api.return_value = mock_api
            inst = KubeClient.get_instance()
            result = inst.core_v1
            assert result is mock_api

    def test_apps_v1_returns_api(self) -> None:
        mock_api = MagicMock()
        with (
            patch("kube_orchestrator.core.client.KubeConfig"),
            patch("kube_orchestrator.core.client.client") as mock_client_mod,
        ):
            mock_client_mod.AppsV1Api.return_value = mock_api
            inst = KubeClient.get_instance()
            result = inst.apps_v1
            assert result is mock_api

    def test_networking_v1_returns_api(self) -> None:
        mock_api = MagicMock()
        with (
            patch("kube_orchestrator.core.client.KubeConfig"),
            patch("kube_orchestrator.core.client.client") as mock_client_mod,
        ):
            mock_client_mod.NetworkingV1Api.return_value = mock_api
            inst = KubeClient.get_instance()
            result = inst.networking_v1
            assert result is mock_api

    def test_batch_v1_returns_api(self) -> None:
        mock_api = MagicMock()
        with (
            patch("kube_orchestrator.core.client.KubeConfig"),
            patch("kube_orchestrator.core.client.client") as mock_client_mod,
        ):
            mock_client_mod.BatchV1Api.return_value = mock_api
            inst = KubeClient.get_instance()
            result = inst.batch_v1
            assert result is mock_api

    @pytest.mark.parametrize(
        ("property_name", "client_attr"),
        [
            ("rbac_v1", "RbacAuthorizationV1Api"),
            ("autoscaling_v2", "AutoscalingV2Api"),
            ("storage_v1", "StorageV1Api"),
            ("scheduling_v1", "SchedulingV1Api"),
            ("policy_v1", "PolicyV1Api"),
            ("custom_objects", "CustomObjectsApi"),
            ("api_extensions_v1", "ApiextensionsV1Api"),
            ("coordination_v1", "CoordinationV1Api"),
            ("events_v1", "EventsV1Api"),
            ("discovery_v1", "DiscoveryV1Api"),
            ("node_v1", "NodeV1Api"),
        ],
    )
    def test_api_group_properties_return_api(
        self, property_name: str, client_attr: str
    ) -> None:
        mock_api = MagicMock()
        with (
            patch("kube_orchestrator.core.client.KubeConfig"),
            patch("kube_orchestrator.core.client.client") as mock_client_mod,
        ):
            getattr(mock_client_mod, client_attr).return_value = mock_api
            inst = KubeClient.get_instance()
            assert getattr(inst, property_name) is mock_api

    def test_init_loads_default_config_when_no_active_context(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeConfig") as mock_config_cls,
            patch("kube_orchestrator.core.client.client"),
        ):
            mock_cfg = mock_config_cls.return_value
            mock_cfg._active_context = None
            KubeClient()
            mock_cfg.load_default.assert_called_once()

    def test_init_skips_load_default_when_context_already_active(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeConfig") as mock_config_cls,
            patch("kube_orchestrator.core.client.client"),
        ):
            mock_cfg = mock_config_cls.return_value
            mock_cfg._active_context = "some-context"
            KubeClient()
            mock_cfg.load_default.assert_not_called()

    def test_init_accepts_explicit_kube_config(self) -> None:
        with patch("kube_orchestrator.core.client.client"):
            explicit_cfg = MagicMock()
            explicit_cfg._active_context = "ctx"
            KubeClient(kube_config=explicit_cfg)
            explicit_cfg.load_default.assert_not_called()

    def test_reset_clears_pool_manager_when_instance_exists(self) -> None:
        with (
            patch("kube_orchestrator.core.client.KubeConfig"),
            patch("kube_orchestrator.core.client.client"),
        ):
            inst = KubeClient.get_instance()
            pool_manager = inst._api_client.rest_client.pool_manager
            KubeClient.reset()
            pool_manager.clear.assert_called_once()

    def test_reset_without_existing_instance_is_noop(self) -> None:
        KubeClient.reset()  # no instance yet — must not raise
