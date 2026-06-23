"""Unit tests for the exception hierarchy."""

from __future__ import annotations

import pytest

from kube_orchestrator.core.exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ClientError,
    KubeOrchestratorError,
    ManifestParseError,
    ManifestValidationError,
    OperationError,
    ResourceAlreadyExistsError,
    ResourceError,
    ResourceNotFoundError,
    ResourceValidationError,
    RollbackError,
)


@pytest.mark.unit
class TestExceptionHierarchy:
    def test_base_is_exception(self) -> None:
        assert issubclass(KubeOrchestratorError, Exception)

    def test_client_error_inherits_base(self) -> None:
        assert issubclass(ClientError, KubeOrchestratorError)

    def test_auth_errors_inherit_client_error(self) -> None:
        assert issubclass(AuthenticationError, ClientError)
        assert issubclass(AuthorizationError, ClientError)

    def test_resource_error_inherits_base(self) -> None:
        assert issubclass(ResourceError, KubeOrchestratorError)

    def test_resource_not_found_has_fields(self) -> None:
        exc = ResourceNotFoundError(kind="Pod", name="my-pod", namespace="default")
        assert exc.kind == "Pod"
        assert exc.name == "my-pod"
        assert exc.namespace == "default"
        assert issubclass(ResourceNotFoundError, ResourceError)

    def test_resource_already_exists_fields(self) -> None:
        exc = ResourceAlreadyExistsError(
            kind="Deployment", name="my-deploy", namespace="ns"
        )
        assert exc.kind == "Deployment"
        assert issubclass(ResourceAlreadyExistsError, ResourceError)

    def test_resource_validation_error_fields(self) -> None:
        exc = ResourceValidationError(
            field="spec.replicas", value="-1", message="must be positive"
        )
        assert exc.field == "spec.replicas"
        assert issubclass(ResourceValidationError, ResourceError)

    def test_manifest_parse_error_fields(self) -> None:
        exc = ManifestParseError(file="deploy.yaml", line=10)
        assert exc.file == "deploy.yaml"
        assert exc.line == 10

    def test_manifest_validation_error_fields(self) -> None:
        exc = ManifestValidationError(
            kind="Pod", errors=["missing name", "missing image"]
        )
        assert exc.kind == "Pod"
        assert len(exc.errors) == 2

    def test_rollback_error_fields(self) -> None:
        exc = RollbackError(deployment="my-app", revision=3)
        assert exc.deployment == "my-app"
        assert exc.revision == 3
        assert issubclass(RollbackError, OperationError)

    def test_api_error_fields(self) -> None:
        exc = APIError(status_code=404, reason="Not Found", body="{}")
        assert exc.status_code == 404
        assert issubclass(APIError, KubeOrchestratorError)
