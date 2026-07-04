"""Unit tests for the exception hierarchy."""

from __future__ import annotations

import pytest
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ClientError,
    ConnectionError,
    DryRunError,
    KubeOrchestratorError,
    ManifestError,
    ManifestParseError,
    ManifestRenderError,
    ManifestValidationError,
    OperationError,
    ResourceAlreadyExistsError,
    ResourceConflictError,
    ResourceError,
    ResourceNotFoundError,
    ResourceValidationError,
    RollbackError,
    TimeoutError,
    parse_api_exception,
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

    def test_connection_error_inherits_client_error(self) -> None:
        assert issubclass(ConnectionError, ClientError)

    def test_resource_conflict_error_fields(self) -> None:
        exc = ResourceConflictError(kind="Pod", name="web", reason="version mismatch")
        assert exc.kind == "Pod"
        assert exc.name == "web"
        assert exc.reason == "version mismatch"
        assert issubclass(ResourceConflictError, ResourceError)

    def test_manifest_error_inherits_base(self) -> None:
        assert issubclass(ManifestError, KubeOrchestratorError)

    def test_manifest_render_error_fields(self) -> None:
        exc = ManifestRenderError(template="deploy.yaml.j2", variable="image")
        assert exc.template == "deploy.yaml.j2"
        assert exc.variable == "image"
        assert issubclass(ManifestRenderError, ManifestError)

    def test_timeout_error_fields(self) -> None:
        exc = TimeoutError(operation="wait_for_rollout", timeout_seconds=300)
        assert exc.operation == "wait_for_rollout"
        assert exc.timeout_seconds == 300
        assert issubclass(TimeoutError, OperationError)

    def test_dry_run_error_inherits_operation_error(self) -> None:
        assert issubclass(DryRunError, OperationError)

    def test_defaults_for_all_field_exceptions(self) -> None:
        assert ResourceNotFoundError().kind == ""
        assert ResourceAlreadyExistsError().kind == ""
        assert ResourceValidationError().field == ""
        assert ResourceConflictError().kind == ""
        assert ManifestParseError().file == ""
        assert ManifestValidationError().errors == []
        assert ManifestRenderError().template == ""
        assert TimeoutError().operation == ""
        assert RollbackError().deployment == ""
        assert APIError().status_code == 0


@pytest.mark.unit
class TestParseApiException:
    def test_404_maps_to_not_found(self) -> None:
        exc = parse_api_exception(ApiException(status=404))
        assert isinstance(exc, ResourceNotFoundError)

    def test_409_maps_to_already_exists(self) -> None:
        exc = parse_api_exception(ApiException(status=409))
        assert isinstance(exc, ResourceAlreadyExistsError)

    def test_401_maps_to_authentication_error(self) -> None:
        exc = parse_api_exception(ApiException(status=401, reason="Unauthorized"))
        assert isinstance(exc, AuthenticationError)
        assert "Unauthorized" in str(exc)

    def test_403_maps_to_authorization_error(self) -> None:
        exc = parse_api_exception(ApiException(status=403, reason="Forbidden"))
        assert isinstance(exc, AuthorizationError)

    def test_other_status_maps_to_api_error(self) -> None:
        exc = parse_api_exception(ApiException(status=500, reason="Internal"))
        assert isinstance(exc, APIError)
        assert exc.status_code == 500
        assert exc.reason == "Internal"

    def test_handles_missing_reason_and_body(self) -> None:
        api_exc = ApiException(status=500)
        api_exc.reason = None
        api_exc.body = None
        exc = parse_api_exception(api_exc)
        assert isinstance(exc, APIError)
        assert exc.reason == ""
