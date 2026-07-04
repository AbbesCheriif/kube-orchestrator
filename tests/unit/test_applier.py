"""Unit tests for ManifestApplier."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kube_orchestrator.manifest.applier import ManifestApplier


@pytest.fixture
def applier(mock_kube_client: MagicMock) -> ManifestApplier:
    return ManifestApplier(
        client=mock_kube_client, dry_run=False, force=False, server_side=False
    )


@pytest.fixture
def dry_run_applier(mock_kube_client: MagicMock) -> ManifestApplier:
    return ManifestApplier(
        client=mock_kube_client, dry_run=True, force=False, server_side=False
    )


@pytest.mark.unit
class TestDecideAction:
    def test_create_when_no_live(self, applier: ManifestApplier) -> None:
        desired = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "p"}}
        action = applier.decide_action(live=None, desired=desired)
        assert action == "create"

    def test_update_when_live_differs(self, applier: ManifestApplier) -> None:
        live = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "p"},
            "spec": {"replicas": 1},
        }
        desired = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "p"},
            "spec": {"replicas": 3},
        }
        action = applier.decide_action(live=live, desired=desired)
        assert action in ("update", "replace")

    def test_skip_when_identical(self, applier: ManifestApplier) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "p"},
            "spec": {},
        }
        action = applier.decide_action(live=manifest, desired=manifest)
        assert action == "skip"


@pytest.mark.unit
class TestComputeDiff:
    def test_diff_detects_changes(self, applier: ManifestApplier) -> None:
        current = {"spec": {"replicas": 1}}
        desired = {"spec": {"replicas": 3}}
        diff = applier.compute_diff(current, desired)
        assert diff != {}

    def test_diff_detects_added_and_removed_keys(
        self, applier: ManifestApplier
    ) -> None:
        current = {"spec": {"oldField": "x"}}
        desired = {"spec": {"newField": "y"}}
        diff = applier.compute_diff(current, desired)
        assert diff["added"] == {"newField": "y"}
        assert diff["removed"] == {"oldField": "x"}

    def test_diff_empty_when_identical(self, applier: ManifestApplier) -> None:
        manifest = {"spec": {"replicas": 1}}
        diff = applier.compute_diff(manifest, manifest)
        # compute_diff returns {"added": {}, "changed": {}, "removed": {}} when identical
        assert (
            not diff.get("added")
            and not diff.get("changed")
            and not diff.get("removed")
        )


@pytest.mark.unit
class TestDryRunApply:
    def test_dry_run_does_not_call_api(self, dry_run_applier: ManifestApplier) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "test-cm", "namespace": "default"},
            "data": {"key": "value"},
        }
        with patch.object(dry_run_applier, "get_live_resource", return_value=None):
            result = dry_run_applier.apply_manifest(manifest, namespace="default")
        assert result.get("action") == "create"
        assert result.get("dry_run") is True


@pytest.mark.unit
class TestDecideActionForce:
    def test_replace_when_forced_and_differs(self, mock_kube_client: MagicMock) -> None:
        applier = ManifestApplier(client=mock_kube_client, force=True)
        live = {"spec": {"replicas": 1}}
        desired = {"spec": {"replicas": 3}}
        assert applier.decide_action(live, desired) == "replace"


@pytest.mark.unit
class TestFormatDiffOutput:
    def test_formats_added_changed_removed(self, applier: ManifestApplier) -> None:
        diff = {
            "added": {"newField": "x"},
            "changed": {"replicas": {"from": 1, "to": 3}},
            "removed": {"oldField": "y"},
        }
        output = applier.format_diff_output(diff)
        assert "+ newField: x" in output
        assert "~ replicas: 1 → 3" in output
        assert "- oldField: y" in output

    def test_no_changes_message(self, applier: ManifestApplier) -> None:
        diff = {"added": {}, "changed": {}, "removed": {}}
        assert applier.format_diff_output(diff) == "(no spec changes)"


@pytest.mark.unit
class TestGetLiveResource:
    def test_returns_none_for_unknown_kind(self, applier: ManifestApplier) -> None:
        manifest = {"kind": "TotallyUnknown", "metadata": {"name": "x"}}
        assert applier.get_live_resource(manifest) is None

    def test_returns_dict_via_to_dict(self, applier: ManifestApplier) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "cm", "namespace": "default"},
        }
        resource = MagicMock()
        resource.to_dict.return_value = {"kind": "ConfigMap"}
        with patch(
            "kube_orchestrator.manifest.applier.route_by_kind"
        ) as mock_route:
            manager_cls = MagicMock()
            manager_cls.return_value.get.return_value = resource
            mock_route.return_value = manager_cls
            result = applier.get_live_resource(manifest)
        assert result == {"kind": "ConfigMap"}

    def test_returns_dict_without_to_dict(self, applier: ManifestApplier) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "cm", "namespace": "default"},
        }
        with patch(
            "kube_orchestrator.manifest.applier.route_by_kind"
        ) as mock_route:
            manager_cls = MagicMock()
            manager_cls.return_value.get.return_value = {"kind": "ConfigMap"}
            mock_route.return_value = manager_cls
            result = applier.get_live_resource(manifest)
        assert result == {"kind": "ConfigMap"}

    def test_returns_none_when_get_raises(self, applier: ManifestApplier) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "cm", "namespace": "default"},
        }
        with patch(
            "kube_orchestrator.manifest.applier.route_by_kind"
        ) as mock_route:
            manager_cls = MagicMock()
            manager_cls.return_value.get.side_effect = RuntimeError("not found")
            mock_route.return_value = manager_cls
            assert applier.get_live_resource(manifest) is None


@pytest.mark.unit
class TestApplyManifestActions:
    def _manifest(self, name: str = "cm") -> dict:
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": name, "namespace": "default"},
        }

    def test_apply_manifest_sets_namespace_on_copy(
        self, applier: ManifestApplier
    ) -> None:
        original = self._manifest()
        with (
            patch.object(applier, "get_live_resource", return_value=None),
            patch("kube_orchestrator.manifest.applier.route_by_kind") as mock_route,
        ):
            manager_cls = MagicMock()
            result_obj = MagicMock()
            result_obj.to_dict.return_value = {"kind": "ConfigMap"}
            manager_cls.return_value.create.return_value = result_obj
            mock_route.return_value = manager_cls

            applier.apply_manifest(original, namespace="prod")

        assert original["metadata"]["namespace"] == "default"
        manager_cls.return_value.create.assert_called_once()

    def test_apply_manifest_unknown_kind_raises(
        self, applier: ManifestApplier
    ) -> None:
        manifest = {"kind": "Bogus", "metadata": {"name": "x"}}
        with patch.object(applier, "get_live_resource", return_value=None):
            with pytest.raises(ValueError, match="Unknown kind"):
                applier.apply_manifest(manifest)

    def test_apply_manifest_create_action(self, applier: ManifestApplier) -> None:
        manifest = self._manifest()
        with (
            patch.object(applier, "get_live_resource", return_value=None),
            patch("kube_orchestrator.manifest.applier.route_by_kind") as mock_route,
        ):
            manager_cls = MagicMock()
            result_obj = MagicMock()
            result_obj.to_dict.return_value = {"kind": "ConfigMap"}
            manager_cls.return_value.create.return_value = result_obj
            mock_route.return_value = manager_cls

            result = applier.apply_manifest(manifest)

        assert result["action"] == "create"
        assert result["resource"] == {"kind": "ConfigMap"}

    def test_apply_manifest_update_action(self, applier: ManifestApplier) -> None:
        manifest = self._manifest()
        live = {"spec": {"a": 1}}
        with (
            patch.object(applier, "get_live_resource", return_value=live),
            patch.object(applier, "decide_action", return_value="update"),
            patch("kube_orchestrator.manifest.applier.route_by_kind") as mock_route,
        ):
            manager_cls = MagicMock()
            result_obj = {"kind": "ConfigMap"}
            manager_cls.return_value.update.return_value = result_obj
            mock_route.return_value = manager_cls

            result = applier.apply_manifest(manifest)

        assert result["action"] == "update"
        manager_cls.return_value.update.assert_called_once()

    def test_apply_manifest_replace_action(self, applier: ManifestApplier) -> None:
        manifest = self._manifest()
        with (
            patch.object(applier, "get_live_resource", return_value={"spec": {}}),
            patch.object(applier, "decide_action", return_value="replace"),
            patch("kube_orchestrator.manifest.applier.route_by_kind") as mock_route,
        ):
            manager_cls = MagicMock()
            result_obj = MagicMock()
            result_obj.to_dict.return_value = {"kind": "ConfigMap"}
            manager_cls.return_value.create.return_value = result_obj
            mock_route.return_value = manager_cls

            result = applier.apply_manifest(manifest)

        assert result["action"] == "replace"
        manager_cls.return_value.delete.assert_called_once()
        manager_cls.return_value.create.assert_called_once()

    def test_apply_manifest_skip_action(self, applier: ManifestApplier) -> None:
        manifest = self._manifest()
        with patch.object(applier, "decide_action", return_value="skip"):
            result = applier.apply_manifest(manifest)
        assert result == {"action": "skip", "name": "cm", "namespace": "default"}


@pytest.mark.unit
class TestApplyFileAndDirectory:
    def test_apply_file_without_values_uses_loader(
        self, applier: ManifestApplier
    ) -> None:
        manifest = {"kind": "ConfigMap", "metadata": {"name": "cm"}}
        with (
            patch(
                "kube_orchestrator.manifest.loader.load_file", return_value=[manifest]
            ),
            patch.object(
                applier, "apply_manifest", return_value={"action": "create"}
            ) as mock_apply,
        ):
            result = applier.apply_file("manifests.yaml")
        mock_apply.assert_called_once_with(manifest, None)
        assert result == [{"action": "create"}]

    def test_apply_file_with_values_uses_renderer(
        self, applier: ManifestApplier
    ) -> None:
        manifest = {"kind": "ConfigMap", "metadata": {"name": "cm"}}
        with (
            patch(
                "kube_orchestrator.manifest.renderer.render_file",
                return_value=[manifest],
            ) as mock_render,
            patch.object(applier, "apply_manifest", return_value={"action": "create"}),
        ):
            applier.apply_file("manifests.yaml.j2", values={"name": "cm"})
        mock_render.assert_called_once_with("manifests.yaml.j2", {"name": "cm"})

    def test_apply_directory_without_values(self, applier: ManifestApplier) -> None:
        manifests = [
            {"kind": "Deployment", "metadata": {"name": "web"}},
            {"kind": "ConfigMap", "metadata": {"name": "cm"}},
        ]
        with (
            patch(
                "kube_orchestrator.manifest.loader.load_directory",
                return_value=manifests,
            ),
            patch.object(
                applier, "apply_manifest", return_value={"action": "create"}
            ) as mock_apply,
        ):
            result = applier.apply_directory("manifests/")
        # ConfigMap must be applied before Deployment per dependency order
        first_call_manifest = mock_apply.call_args_list[0].args[0]
        assert first_call_manifest["kind"] == "ConfigMap"
        assert len(result) == 2

    def test_apply_directory_with_values(self, applier: ManifestApplier) -> None:
        manifests = [{"kind": "ConfigMap", "metadata": {"name": "cm"}}]
        with (
            patch(
                "kube_orchestrator.manifest.renderer.render_directory",
                return_value=manifests,
            ) as mock_render,
            patch.object(applier, "apply_manifest", return_value={"action": "create"}),
        ):
            applier.apply_directory("manifests/", values={"env": "prod"})
        mock_render.assert_called_once()


@pytest.mark.unit
class TestDryRunFileAndPlan:
    def test_dry_run_file_restores_original_flag(
        self, applier: ManifestApplier
    ) -> None:
        with patch.object(applier, "apply_file", return_value=[]) as mock_apply_file:
            applier.dry_run_file("manifests.yaml")
        assert applier.dry_run is False
        mock_apply_file.assert_called_once_with("manifests.yaml", values=None)

    def test_dry_run_file_restores_flag_even_on_error(
        self, applier: ManifestApplier
    ) -> None:
        with patch.object(applier, "apply_file", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                applier.dry_run_file("manifests.yaml")
        assert applier.dry_run is False

    def test_print_plan(self, applier: ManifestApplier, capsys) -> None:
        manifest = {
            "kind": "ConfigMap",
            "metadata": {"name": "cm", "namespace": "default"},
        }
        with (
            patch.object(applier, "get_live_resource", return_value=None),
            patch.object(applier, "decide_action", return_value="create"),
        ):
            applier.print_plan([manifest])
        captured = capsys.readouterr()
        assert "CREATE" in captured.out
        assert "ConfigMap/cm" in captured.out

    def test_print_plan_without_namespace(self, applier: ManifestApplier, capsys) -> None:
        manifest = {"kind": "ClusterRole", "metadata": {"name": "cr"}}
        with (
            patch.object(applier, "get_live_resource", return_value=None),
            patch.object(applier, "decide_action", return_value="create"),
        ):
            applier.print_plan([manifest])
        captured = capsys.readouterr()
        assert "ClusterRole/cr" in captured.out
        assert "(" not in captured.out

    def test_confirm_apply_yes(self, applier: ManifestApplier) -> None:
        with (
            patch.object(applier, "print_plan"),
            patch("builtins.input", return_value="y"),
        ):
            assert applier.confirm_apply([]) is True

    def test_confirm_apply_no(self, applier: ManifestApplier) -> None:
        with (
            patch.object(applier, "print_plan"),
            patch("builtins.input", return_value="n"),
        ):
            assert applier.confirm_apply([]) is False


@pytest.mark.unit
class TestIsAlreadyApplied:
    def test_true_when_skip(self, applier: ManifestApplier) -> None:
        manifest = {"kind": "ConfigMap", "metadata": {"name": "cm"}}
        with (
            patch.object(applier, "get_live_resource", return_value={"spec": {}}),
            patch.object(applier, "decide_action", return_value="skip"),
        ):
            assert applier.is_already_applied(manifest) is True

    def test_false_when_not_skip(self, applier: ManifestApplier) -> None:
        manifest = {"kind": "ConfigMap", "metadata": {"name": "cm"}}
        with (
            patch.object(applier, "get_live_resource", return_value=None),
            patch.object(applier, "decide_action", return_value="create"),
        ):
            assert applier.is_already_applied(manifest) is False
