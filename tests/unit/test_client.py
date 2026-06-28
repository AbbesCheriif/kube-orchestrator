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
