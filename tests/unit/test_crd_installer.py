"""Unit tests for kube_orchestrator.crd.installer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import yaml
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import (
    APIError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
)
from kube_orchestrator.crd.installer import CRDInstaller

MANIFEST = {
    "apiVersion": "apiextensions.k8s.io/v1",
    "kind": "CustomResourceDefinition",
    "metadata": {"name": "foos.example.com"},
    "spec": {"group": "example.com"},
}


@pytest.fixture
def installer(mock_kube_client: MagicMock) -> CRDInstaller:
    return CRDInstaller(kube_client=mock_kube_client)


@pytest.fixture
def crd_api(mock_kube_client: MagicMock) -> MagicMock:
    return mock_kube_client.api_extensions_v1


@pytest.mark.unit
class TestIsInstalled:
    def test_true_when_read_succeeds(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd_api.read_custom_resource_definition.return_value = MagicMock()
        assert installer.is_installed("foos.example.com") is True

    def test_false_on_404(self, installer: CRDInstaller, crd_api: MagicMock) -> None:
        crd_api.read_custom_resource_definition.side_effect = ApiException(status=404)
        assert installer.is_installed("foos.example.com") is False

    def test_raises_on_other_errors(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd_api.read_custom_resource_definition.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            installer.is_installed("foos.example.com")


@pytest.mark.unit
class TestInstall:
    def test_creates_when_not_installed(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd_api.read_custom_resource_definition.side_effect = ApiException(status=404)
        crd_api.create_custom_resource_definition.return_value = MagicMock()

        result = installer.install(dict(MANIFEST))

        crd_api.create_custom_resource_definition.assert_called_once()
        assert result is crd_api.create_custom_resource_definition.return_value

    def test_replaces_when_already_installed(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        existing = MagicMock()
        existing.metadata.resource_version = "42"
        crd_api.read_custom_resource_definition.return_value = existing
        crd_api.replace_custom_resource_definition.return_value = MagicMock()

        manifest = {
            "metadata": {"name": "foos.example.com"},
            "spec": {"group": "example.com"},
        }
        installer.install(manifest)

        assert manifest["metadata"]["resourceVersion"] == "42"
        crd_api.replace_custom_resource_definition.assert_called_once()

    def test_create_error_is_parsed(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd_api.read_custom_resource_definition.side_effect = ApiException(status=404)
        crd_api.create_custom_resource_definition.side_effect = ApiException(
            status=409
        )
        with pytest.raises(ResourceAlreadyExistsError):
            installer.install(dict(MANIFEST))

    def test_install_from_file(
        self, installer: CRDInstaller, crd_api: MagicMock, tmp_path: "object"
    ) -> None:
        import pathlib

        path = pathlib.Path(str(tmp_path)) / "crd.yaml"
        path.write_text(yaml.safe_dump(MANIFEST), encoding="utf-8")
        crd_api.read_custom_resource_definition.side_effect = ApiException(status=404)
        crd_api.create_custom_resource_definition.return_value = MagicMock()

        installer.install_from_file(str(path))

        crd_api.create_custom_resource_definition.assert_called_once()


@pytest.mark.unit
class TestUninstall:
    def test_deletes(self, installer: CRDInstaller, crd_api: MagicMock) -> None:
        installer.uninstall("foos.example.com")
        crd_api.delete_custom_resource_definition.assert_called_once_with(
            "foos.example.com"
        )

    def test_raises_parsed_exception(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd_api.delete_custom_resource_definition.side_effect = ApiException(
            status=500
        )
        with pytest.raises(APIError):
            installer.uninstall("foos.example.com")


@pytest.mark.unit
class TestWaitForEstablished:
    def test_returns_true_immediately_when_established(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        condition = MagicMock()
        condition.type = "Established"
        condition.status = "True"
        crd = MagicMock()
        crd.status.conditions = [condition]
        crd_api.read_custom_resource_definition.return_value = crd

        assert installer.wait_for_established("foos.example.com", timeout_seconds=5) is True

    def test_returns_false_when_timeout_elapses(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd = MagicMock()
        crd.status.conditions = []
        crd_api.read_custom_resource_definition.return_value = crd

        assert installer.wait_for_established("foos.example.com", timeout_seconds=0) is False

    def test_ignores_api_exceptions_while_polling(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd_api.read_custom_resource_definition.side_effect = ApiException(status=404)
        with patch("kube_orchestrator.crd.installer.time.sleep"):
            assert (
                installer.wait_for_established(
                    "foos.example.com", timeout_seconds=0.05
                )
                is False
            )
        crd_api.read_custom_resource_definition.assert_called()


@pytest.mark.unit
class TestListCrds:
    def test_lists_all(self, installer: CRDInstaller, crd_api: MagicMock) -> None:
        crd_a = MagicMock()
        crd_a.spec.group = "example.com"
        crd_b = MagicMock()
        crd_b.spec.group = "other.io"
        crd_api.list_custom_resource_definition.return_value.items = [crd_a, crd_b]

        result = installer.list_crds()

        assert result == [crd_a, crd_b]

    def test_filters_by_group(self, installer: CRDInstaller, crd_api: MagicMock) -> None:
        crd_a = MagicMock()
        crd_a.spec.group = "example.com"
        crd_b = MagicMock()
        crd_b.spec.group = "other.io"
        crd_api.list_custom_resource_definition.return_value.items = [crd_a, crd_b]

        result = installer.list_crds(group="example.com")

        assert result == [crd_a]

    def test_raises_parsed_exception(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd_api.list_custom_resource_definition.side_effect = ApiException(status=500)
        with pytest.raises(APIError):
            installer.list_crds()


@pytest.mark.unit
class TestGetCrd:
    def test_returns_crd(self, installer: CRDInstaller, crd_api: MagicMock) -> None:
        crd_api.read_custom_resource_definition.return_value = "crd-object"
        assert installer.get_crd("foos.example.com") == "crd-object"

    def test_raises_parsed_exception(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        crd_api.read_custom_resource_definition.side_effect = ApiException(status=404)
        with pytest.raises(ResourceNotFoundError):
            installer.get_crd("foos.example.com")


@pytest.mark.unit
class TestGetSchema:
    def test_returns_schema_for_storage_version(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        version = MagicMock()
        version.storage = True
        version.schema.open_apiv3_schema.to_dict.return_value = {"type": "object"}
        crd = MagicMock()
        crd.spec.versions = [version]
        crd_api.read_custom_resource_definition.return_value = crd

        assert installer.get_schema("foos.example.com") == {"type": "object"}

    def test_returns_empty_dict_when_no_storage_version(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        version = MagicMock()
        version.storage = False
        crd = MagicMock()
        crd.spec.versions = [version]
        crd_api.read_custom_resource_definition.return_value = crd

        assert installer.get_schema("foos.example.com") == {}

    def test_returns_empty_dict_when_schema_missing(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        version = MagicMock()
        version.storage = True
        version.schema = None
        crd = MagicMock()
        crd.spec.versions = [version]
        crd_api.read_custom_resource_definition.return_value = crd

        assert installer.get_schema("foos.example.com") == {}


@pytest.mark.unit
class TestListVersions:
    def test_returns_version_names(
        self, installer: CRDInstaller, crd_api: MagicMock
    ) -> None:
        v1 = MagicMock()
        v1.name = "v1"
        v1beta1 = MagicMock()
        v1beta1.name = "v1beta1"
        crd = MagicMock()
        crd.spec.versions = [v1, v1beta1]
        crd_api.read_custom_resource_definition.return_value = crd

        assert installer.list_versions("foos.example.com") == ["v1", "v1beta1"]
