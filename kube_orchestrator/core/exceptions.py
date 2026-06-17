from __future__ import annotations

from kubernetes.client.rest import ApiException


class KubeOrchestratorError(Exception):
    pass


class ClientError(KubeOrchestratorError):
    pass


class AuthenticationError(ClientError):
    pass


class AuthorizationError(ClientError):
    pass


class ConnectionError(ClientError):
    pass


class ResourceError(KubeOrchestratorError):
    pass


class ResourceNotFoundError(ResourceError):
    def __init__(self, kind: str = "", name: str = "", namespace: str = "") -> None:
        self.kind = kind
        self.name = name
        self.namespace = namespace
        super().__init__(f"{kind} '{name}' not found" + (f" in '{namespace}'" if namespace else ""))


class ResourceAlreadyExistsError(ResourceError):
    def __init__(self, kind: str = "", name: str = "", namespace: str = "") -> None:
        self.kind = kind
        self.name = name
        self.namespace = namespace
        super().__init__(f"{kind} '{name}' already exists" + (f" in '{namespace}'" if namespace else ""))


class ResourceValidationError(ResourceError):
    def __init__(self, field: str = "", value: str = "", message: str = "") -> None:
        self.field = field
        self.value = value
        super().__init__(message or f"Validation error on field '{field}': {value}")


class ResourceConflictError(ResourceError):
    def __init__(self, kind: str = "", name: str = "", reason: str = "") -> None:
        self.kind = kind
        self.name = name
        self.reason = reason
        super().__init__(f"Conflict on {kind} '{name}': {reason}")


class ManifestError(KubeOrchestratorError):
    pass


class ManifestParseError(ManifestError):
    def __init__(self, file: str = "", line: int = 0, message: str = "") -> None:
        self.file = file
        self.line = line
        super().__init__(message or f"Parse error in {file}:{line}")


class ManifestValidationError(ManifestError):
    def __init__(self, kind: str = "", errors: list | None = None) -> None:
        self.kind = kind
        self.errors = errors or []
        super().__init__(f"Validation errors for {kind}: {self.errors}")


class ManifestRenderError(ManifestError):
    def __init__(self, template: str = "", variable: str = "") -> None:
        self.template = template
        self.variable = variable
        super().__init__(f"Render error in '{template}': missing variable '{variable}'")


class OperationError(KubeOrchestratorError):
    pass


class TimeoutError(OperationError):
    def __init__(self, operation: str = "", timeout_seconds: int = 0) -> None:
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Operation '{operation}' timed out after {timeout_seconds}s")


class DryRunError(OperationError):
    pass


class RollbackError(OperationError):
    def __init__(self, deployment: str = "", revision: int = 0) -> None:
        self.deployment = deployment
        self.revision = revision
        super().__init__(f"Rollback failed for '{deployment}' to revision {revision}")


class APIError(KubeOrchestratorError):
    def __init__(self, status_code: int = 0, reason: str = "", body: str = "") -> None:
        self.status_code = status_code
        self.reason = reason
        self.body = body
        super().__init__(f"API error {status_code}: {reason}")


def parse_api_exception(e: ApiException) -> KubeOrchestratorError:
    status = e.status
    reason = e.reason or ""
    body = str(e.body or "")
    if status == 404:
        return ResourceNotFoundError()
    if status == 409:
        return ResourceAlreadyExistsError()
    if status == 401:
        return AuthenticationError(reason)
    if status == 403:
        return AuthorizationError(reason)
    return APIError(status_code=status, reason=reason, body=body)
