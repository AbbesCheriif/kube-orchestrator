"""Complete exception hierarchy for kube-orchestrator."""

from __future__ import annotations

from typing import Any


class KubeOrchestratorError(Exception):
    """Base exception for all kube-orchestrator errors."""


# ---------------------------------------------------------------------------
# Client errors
# ---------------------------------------------------------------------------


class ClientError(KubeOrchestratorError):
    """Errors originating from the Kubernetes API client."""


class AuthenticationError(ClientError):
    """Raised when client credentials are invalid or missing."""


class AuthorizationError(ClientError):
    """Raised when the client lacks permission for the requested operation."""


class ConnectionError(ClientError):
    """Raised when the API server is unreachable."""


# ---------------------------------------------------------------------------
# Resource errors
# ---------------------------------------------------------------------------


class ResourceError(KubeOrchestratorError):
    """Base class for resource-level errors."""


class ResourceNotFoundError(ResourceError):
    """Raised when a requested Kubernetes resource does not exist."""

    def __init__(self, kind: str, name: str, namespace: str | None = None) -> None:
        self.kind = kind
        self.name = name
        self.namespace = namespace
        loc = f"{namespace}/{name}" if namespace else name
        super().__init__(f"{kind} '{loc}' not found")


class ResourceAlreadyExistsError(ResourceError):
    """Raised when trying to create a resource that already exists."""

    def __init__(self, kind: str, name: str, namespace: str | None = None) -> None:
        self.kind = kind
        self.name = name
        self.namespace = namespace
        loc = f"{namespace}/{name}" if namespace else name
        super().__init__(f"{kind} '{loc}' already exists")


class ResourceValidationError(ResourceError):
    """Raised when a resource manifest fails field-level validation."""

    def __init__(self, field: str, value: Any, message: str) -> None:
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation error on field '{field}': {message} (got {value!r})")


class ResourceConflictError(ResourceError):
    """Raised on a resource update conflict (optimistic concurrency)."""

    def __init__(self, kind: str, name: str, reason: str) -> None:
        self.kind = kind
        self.name = name
        self.reason = reason
        super().__init__(f"Conflict on {kind} '{name}': {reason}")


# ---------------------------------------------------------------------------
# Manifest errors
# ---------------------------------------------------------------------------


class ManifestError(KubeOrchestratorError):
    """Base class for manifest processing errors."""


class ManifestParseError(ManifestError):
    """Raised when a YAML/JSON manifest cannot be parsed."""

    def __init__(self, file: str, line: int | None = None) -> None:
        self.file = file
        self.line = line
        loc = f":{line}" if line is not None else ""
        super().__init__(f"Failed to parse manifest '{file}{loc}'")


class ManifestValidationError(ManifestError):
    """Raised when a parsed manifest fails schema validation."""

    def __init__(self, kind: str, errors: list[str]) -> None:
        self.kind = kind
        self.errors = errors
        super().__init__(f"Manifest validation failed for {kind}: {errors}")


class ManifestRenderError(ManifestError):
    """Raised when Jinja2 template rendering fails."""

    def __init__(self, template: str, variable: str) -> None:
        self.template = template
        self.variable = variable
        super().__init__(
            f"Render error in template '{template}': undefined variable '{variable}'"
        )


# ---------------------------------------------------------------------------
# Operation errors
# ---------------------------------------------------------------------------


class OperationError(KubeOrchestratorError):
    """Base class for runtime operation errors."""


class TimeoutError(OperationError):
    """Raised when an operation exceeds its configured timeout."""

    def __init__(self, operation: str, timeout_seconds: int) -> None:
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Operation '{operation}' timed out after {timeout_seconds}s")


class DryRunError(OperationError):
    """Raised when a dry-run request is rejected by the API server."""


class RollbackError(OperationError):
    """Raised when an automatic rollback fails."""

    def __init__(self, deployment: str, revision: int) -> None:
        self.deployment = deployment
        self.revision = revision
        super().__init__(f"Rollback of '{deployment}' to revision {revision} failed")


# ---------------------------------------------------------------------------
# API errors
# ---------------------------------------------------------------------------


class APIError(KubeOrchestratorError):
    """Wraps a raw Kubernetes API HTTP error response."""

    def __init__(self, status_code: int, reason: str, body: str = "") -> None:
        self.status_code = status_code
        self.reason = reason
        self.body = body
        super().__init__(f"Kubernetes API error {status_code}: {reason}")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def parse_api_exception(e: Any) -> KubeOrchestratorError:
    """Convert a kubernetes ApiException into the most specific typed error."""
    status_code: int = getattr(e, "status", 0)
    reason: str = getattr(e, "reason", str(e))
    body: str = getattr(e, "body", "") or ""

    if status_code == 401:
        return AuthenticationError(reason)
    if status_code == 403:
        return AuthorizationError(reason)
    if status_code == 404:
        return ResourceNotFoundError("Unknown", reason)
    if status_code == 409:
        return ResourceConflictError("Unknown", reason, "conflict")
    if status_code == 422:
        return ResourceValidationError("", None, reason)
    return APIError(status_code, reason, body)
