"""Unit tests for NamespaceManager.

Namespace is a cluster-scoped resource: the real CoreV1Api only exposes
`create_namespace`/`read_namespace`/... (no `_namespaced_` variant). Since
BaseResourceManager.create()/get()/etc. probe for the namespaced method
name first via getattr(api, ..., None), and a bare MagicMock auto-vivifies
*any* attribute access (making that probe always "succeed"), tests must
explicitly delete the namespaced attribute so the generic CRUD code takes
the same fallback branch it does against the real API.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.resources.cluster.namespace import NamespaceManager


@pytest.fixture
def ns_manager(mock_kube_client: MagicMock) -> NamespaceManager:
    return NamespaceManager(kube_client=mock_kube_client)


@pytest.fixture
def core_api(mock_kube_client: MagicMock) -> MagicMock:
    api = mock_kube_client.core_v1
    for verb in ("create", "read", "list", "patch", "delete"):
        delattr(api, f"{verb}_namespaced_namespace")
    return api


@pytest.mark.unit
class TestCreateNamespace:
    def test_creates_with_minimal_fields(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns_manager.create_namespace("team-a")
        call_kwargs = core_api.create_namespace.call_args.kwargs
        assert call_kwargs["body"]["metadata"]["name"] == "team-a"

    def test_creates_with_finalizers(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns_manager.create_namespace("team-a", finalizers=["kubernetes"])
        call_kwargs = core_api.create_namespace.call_args.kwargs
        assert call_kwargs["body"]["spec"]["finalizers"] == ["kubernetes"]


@pytest.mark.unit
class TestGetListDeleteNamespace:
    def test_get_namespace(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        core_api.read_namespace.return_value = "ns-obj"
        assert ns_manager.get_namespace("team-a") == "ns-obj"

    def test_list_namespaces(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        core_api.list_namespace.return_value.items = ["a", "b"]
        assert ns_manager.list_namespaces() == ["a", "b"]

    def test_delete_namespace(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns_manager.delete_namespace("team-a")
        core_api.delete_namespace.assert_called_once()


@pytest.mark.unit
class TestLabelAndAnnotate:
    def test_label_namespace_merges_existing(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns = MagicMock()
        ns.metadata.labels = {"existing": "yes"}
        core_api.read_namespace.return_value = ns
        core_api.patch_namespace.return_value = ns

        ns_manager.label_namespace("team-a", {"tier": "gold"})

        call_body = core_api.patch_namespace.call_args.kwargs["body"]
        assert call_body["metadata"]["labels"] == {"existing": "yes", "tier": "gold"}

    def test_annotate_namespace_merges_existing(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns = MagicMock()
        ns.metadata.annotations = {"owner": "team-a"}
        core_api.read_namespace.return_value = ns
        core_api.patch_namespace.return_value = ns

        ns_manager.annotate_namespace("team-a", {"contact": "a@example.com"})

        call_body = core_api.patch_namespace.call_args.kwargs["body"]
        assert call_body["metadata"]["annotations"] == {
            "owner": "team-a",
            "contact": "a@example.com",
        }


@pytest.mark.unit
class TestFinalizers:
    def test_add_finalizer(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns = MagicMock()
        ns.spec.finalizers = ["kubernetes"]
        core_api.read_namespace.return_value = ns
        core_api.patch_namespace.return_value = ns

        ns_manager.add_finalizer("team-a", "custom.io/finalizer")

        call_body = core_api.patch_namespace.call_args.kwargs["body"]
        assert "custom.io/finalizer" in call_body["spec"]["finalizers"]

    def test_add_finalizer_is_idempotent(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns = MagicMock()
        ns.spec.finalizers = ["custom.io/finalizer"]
        core_api.read_namespace.return_value = ns
        core_api.patch_namespace.return_value = ns

        ns_manager.add_finalizer("team-a", "custom.io/finalizer")

        call_body = core_api.patch_namespace.call_args.kwargs["body"]
        assert call_body["spec"]["finalizers"].count("custom.io/finalizer") == 1

    def test_remove_finalizer(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns = MagicMock()
        ns.spec.finalizers = ["kubernetes", "custom.io/finalizer"]
        core_api.read_namespace.return_value = ns
        core_api.patch_namespace.return_value = ns

        ns_manager.remove_finalizer("team-a", "custom.io/finalizer")

        call_body = core_api.patch_namespace.call_args.kwargs["body"]
        assert call_body["spec"]["finalizers"] == ["kubernetes"]


@pytest.mark.unit
class TestPhaseAndWaiting:
    def test_get_phase(self, ns_manager: NamespaceManager, core_api: MagicMock) -> None:
        ns = MagicMock()
        ns.status.phase = "Active"
        core_api.read_namespace.return_value = ns
        assert ns_manager.get_phase("team-a") == "Active"

    def test_get_phase_defaults_to_unknown(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns = MagicMock()
        ns.status = None
        core_api.read_namespace.return_value = ns
        assert ns_manager.get_phase("team-a") == "Unknown"

    def test_wait_for_active_returns_true(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        ns = MagicMock()
        ns.status.phase = "Active"
        core_api.read_namespace.return_value = ns
        assert ns_manager.wait_for_active("team-a", timeout_seconds=5) is True

    def test_wait_for_active_ignores_not_found_and_times_out(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        from kubernetes.client.exceptions import ApiException

        core_api.read_namespace.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.resources.cluster.namespace.time.sleep"):
            assert ns_manager.wait_for_active("team-a", timeout_seconds=0.05) is False

    def test_wait_for_deletion_returns_true_when_gone(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        from kubernetes.client.exceptions import ApiException

        core_api.read_namespace.side_effect = ApiException(status=404)
        assert ns_manager.wait_for_deletion("team-a", timeout_seconds=5) is True

    def test_wait_for_deletion_times_out_while_still_present(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        core_api.read_namespace.return_value = MagicMock()
        with patch("kube_orchestrator.resources.cluster.namespace.time.sleep"):
            assert ns_manager.wait_for_deletion("team-a", timeout_seconds=0.05) is False


@pytest.mark.unit
class TestGetResourceUsage:
    def test_aggregates_quota_hard_and_used(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        quota = MagicMock()
        quota.metadata.name = "compute-quota"
        quota.status.hard = {"cpu": "4"}
        quota.status.used = {"cpu": "2"}
        core_api.list_namespaced_resource_quota.return_value.items = [quota]

        result = ns_manager.get_resource_usage("team-a")

        assert result["compute-quota"] == {"hard": {"cpu": "4"}, "used": {"cpu": "2"}}

    def test_raises_parsed_exception(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        from kubernetes.client.exceptions import ApiException

        from kube_orchestrator.core.exceptions import APIError

        core_api.list_namespaced_resource_quota.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            ns_manager.get_resource_usage("team-a")


@pytest.mark.unit
class TestGetAllResourcesAndSummary:
    def test_collects_all_resource_kinds(
        self,
        ns_manager: NamespaceManager,
        core_api: MagicMock,
        mock_kube_client: MagicMock,
    ) -> None:
        core_api.list_namespaced_pod.return_value.items = ["pod"]
        core_api.list_namespaced_service.return_value.items = []
        core_api.list_namespaced_config_map.return_value.items = []
        core_api.list_namespaced_secret.return_value.items = []
        core_api.list_namespaced_persistent_volume_claim.return_value.items = []
        core_api.list_namespaced_resource_quota.return_value.items = []
        core_api.list_namespaced_limit_range.return_value.items = []
        mock_kube_client.apps_v1.list_namespaced_deployment.return_value.items = [
            "d1",
            "d2",
        ]
        mock_kube_client.apps_v1.list_namespaced_stateful_set.return_value.items = []
        mock_kube_client.apps_v1.list_namespaced_daemon_set.return_value.items = []
        mock_kube_client.apps_v1.list_namespaced_replica_set.return_value.items = []
        mock_kube_client.batch_v1.list_namespaced_job.return_value.items = []
        mock_kube_client.batch_v1.list_namespaced_cron_job.return_value.items = []

        result = ns_manager.get_all_resources("team-a")

        assert result["pods"] == ["pod"]
        assert result["deployments"] == ["d1", "d2"]

    def test_raises_parsed_exception_on_error(
        self, ns_manager: NamespaceManager, core_api: MagicMock
    ) -> None:
        from kubernetes.client.exceptions import ApiException

        from kube_orchestrator.core.exceptions import APIError

        core_api.list_namespaced_pod.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            ns_manager.get_all_resources("team-a")

    def test_get_resource_summary_counts_each_kind(
        self,
        ns_manager: NamespaceManager,
        core_api: MagicMock,
        mock_kube_client: MagicMock,
    ) -> None:
        core_api.list_namespaced_pod.return_value.items = ["pod1", "pod2"]
        core_api.list_namespaced_service.return_value.items = []
        core_api.list_namespaced_config_map.return_value.items = []
        core_api.list_namespaced_secret.return_value.items = []
        core_api.list_namespaced_persistent_volume_claim.return_value.items = []
        core_api.list_namespaced_resource_quota.return_value.items = []
        core_api.list_namespaced_limit_range.return_value.items = []
        mock_kube_client.apps_v1.list_namespaced_deployment.return_value.items = []
        mock_kube_client.apps_v1.list_namespaced_stateful_set.return_value.items = []
        mock_kube_client.apps_v1.list_namespaced_daemon_set.return_value.items = []
        mock_kube_client.apps_v1.list_namespaced_replica_set.return_value.items = []
        mock_kube_client.batch_v1.list_namespaced_job.return_value.items = []
        mock_kube_client.batch_v1.list_namespaced_cron_job.return_value.items = []

        summary = ns_manager.get_resource_summary("team-a")
        assert summary["pods"] == 2


@pytest.mark.unit
class TestCloneNamespaceConfig:
    def test_clones_quotas_and_limit_ranges(
        self, ns_manager: NamespaceManager, mock_kube_client: MagicMock
    ) -> None:
        quota = MagicMock()
        quota.metadata.name = "compute-quota"
        quota.spec.hard = {"cpu": "4"}
        quota.spec.scopes = None
        quota.spec.scope_selector = None

        limit_range = MagicMock()
        limit_range.metadata.name = "defaults"
        item = MagicMock()
        item.to_dict.return_value = {"type": "Container"}
        limit_range.spec.limits = [item]

        with (
            patch(
                "kube_orchestrator.resources.cluster.namespace.ResourceQuotaManager"
            ) as quota_mgr_cls,
            patch(
                "kube_orchestrator.resources.cluster.namespace.LimitRangeManager"
            ) as lr_mgr_cls,
        ):
            quota_mgr_cls.return_value.list_quotas.return_value = [quota]
            lr_mgr_cls.return_value.list_limit_ranges.return_value = [limit_range]

            ns_manager.clone_namespace_config("source-ns", "dest-ns")

            quota_mgr_cls.return_value.create_quota.assert_called_once_with(
                name="compute-quota",
                namespace="dest-ns",
                hard={"cpu": "4"},
                scopes=None,
                scope_selector=None,
            )
            lr_mgr_cls.return_value.create_limit_range.assert_called_once_with(
                name="defaults", namespace="dest-ns", limits=[{"type": "Container"}]
            )

    def test_skips_resources_without_name_and_swallows_create_errors(
        self, ns_manager: NamespaceManager, mock_kube_client: MagicMock
    ) -> None:
        unnamed_quota = MagicMock()
        unnamed_quota.metadata = None

        named_quota = MagicMock()
        named_quota.metadata.name = "compute-quota"
        named_quota.spec.hard = {"cpu": "4"}
        named_quota.spec.scopes = ["Terminating"]
        named_quota.spec.scope_selector.to_dict.return_value = {"matchExpressions": []}

        with (
            patch(
                "kube_orchestrator.resources.cluster.namespace.ResourceQuotaManager"
            ) as quota_mgr_cls,
            patch(
                "kube_orchestrator.resources.cluster.namespace.LimitRangeManager"
            ) as lr_mgr_cls,
        ):
            quota_mgr_cls.return_value.list_quotas.return_value = [
                unnamed_quota,
                named_quota,
            ]
            quota_mgr_cls.return_value.create_quota.side_effect = RuntimeError("boom")
            unnamed_lr = MagicMock()
            unnamed_lr.metadata = None
            lr_mgr_cls.return_value.list_limit_ranges.return_value = [unnamed_lr]

            ns_manager.clone_namespace_config("source-ns", "dest-ns")

            quota_mgr_cls.return_value.create_quota.assert_called_once()
            lr_mgr_cls.return_value.create_limit_range.assert_not_called()


@pytest.mark.unit
class TestMeta:
    def test_kind_and_api_version(self, ns_manager: NamespaceManager) -> None:
        assert ns_manager._kind() == "Namespace"
        assert ns_manager._api_version() == "v1"
