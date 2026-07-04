"""Abstract BaseResourceManager implementing the Template Method pattern."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any, Generic, TypeVar, cast

from kubernetes import (  # type: ignore[attr-defined]  # kubernetes-stubs has no watch submodule stub
    client,
    watch,
)
from kubernetes.client.exceptions import ApiException

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.exceptions import (
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    parse_api_exception,
)
from kube_orchestrator.core.logging import get_logger

T = TypeVar("T")
BoundLogger = Any


class BaseResourceManager(ABC, Generic[T]):
    """Template Method base for all Kubernetes resource managers."""

    def __init__(
        self,
        kube_client: KubeClient | None = None,
        default_namespace: str = "default",
        dry_run: bool = False,
    ) -> None:
        self.client = kube_client or KubeClient.get_instance()
        self.logger: BoundLogger = get_logger(self.__class__.__name__)
        self.default_namespace = default_namespace
        self.dry_run: str | None = "All" if dry_run else None

    # ------------------------------------------------------------------
    # Template Methods (must be implemented by subclasses)
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_api(self) -> Any:
        """Return the kubernetes API object (CoreV1Api, AppsV1Api, etc.)."""

    @abstractmethod
    def _kind(self) -> str:
        """Return the resource kind string, e.g. 'Pod', 'Deployment'."""

    @abstractmethod
    def _api_version(self) -> str:
        """Return the API version string, e.g. 'v1', 'apps/v1'."""

    # ------------------------------------------------------------------
    # Concrete CRUD methods
    # ------------------------------------------------------------------

    def exists(self, name: str, namespace: str | None = None) -> bool:
        """Return True if the resource exists, False otherwise."""
        try:
            self.get(name, namespace)
            return True
        except ResourceNotFoundError:
            return False

    def get(self, name: str, namespace: str | None = None) -> T:
        """Fetch a single resource by name."""
        ns = namespace or self.default_namespace
        try:
            api = self._get_api()
            read_fn = getattr(api, f"read_namespaced_{self._resource_name()}", None)
            if read_fn is not None:
                return cast("T", read_fn(name=name, namespace=ns))
            return cast("T", getattr(api, f"read_{self._resource_name()}")(name=name))
        except ApiException as exc:
            if exc.status == 404:
                raise ResourceNotFoundError(self._kind(), name, ns) from exc
            raise parse_api_exception(exc) from exc

    def list(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
        field_selector: str | None = None,
        limit: int | None = None,
        continue_token: str | None = None,
    ) -> list[T]:
        """List resources with optional filtering."""
        ns = namespace or self.default_namespace
        kwargs: dict[str, Any] = {}
        if label_selector:
            kwargs["label_selector"] = label_selector
        if field_selector:
            kwargs["field_selector"] = field_selector
        if limit:
            kwargs["limit"] = limit
        if continue_token:
            kwargs["_continue"] = continue_token
        try:
            api = self._get_api()
            list_fn = getattr(api, f"list_namespaced_{self._resource_name()}", None)
            if list_fn is not None:
                result = list_fn(namespace=ns, **kwargs)
            else:
                result = getattr(api, f"list_{self._resource_name()}")(**kwargs)
            return cast("list[T]", result.items)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def create(self, manifest: dict[str, Any], namespace: str | None = None) -> T:
        """Create a resource from a manifest dict."""
        ns = namespace or self.default_namespace
        kwargs: dict[str, Any] = {"body": manifest}
        if self.dry_run:
            kwargs["dry_run"] = self.dry_run
        try:
            api = self._get_api()
            create_fn = getattr(api, f"create_namespaced_{self._resource_name()}", None)
            if create_fn is not None:
                return cast("T", create_fn(namespace=ns, **kwargs))
            return cast("T", getattr(api, f"create_{self._resource_name()}")(**kwargs))
        except ApiException as exc:
            if exc.status == 409:
                raise ResourceAlreadyExistsError(
                    self._kind(),
                    manifest.get("metadata", {}).get("name", ""),
                    ns,
                ) from exc
            raise parse_api_exception(exc) from exc

    def update(
        self, name: str, manifest: dict[str, Any], namespace: str | None = None
    ) -> T:
        """Replace an existing resource (PUT)."""
        ns = namespace or self.default_namespace
        kwargs: dict[str, Any] = {"name": name, "body": manifest}
        if self.dry_run:
            kwargs["dry_run"] = self.dry_run
        try:
            api = self._get_api()
            replace_fn = getattr(
                api, f"replace_namespaced_{self._resource_name()}", None
            )
            if replace_fn is not None:
                return cast("T", replace_fn(namespace=ns, **kwargs))
            return cast("T", getattr(api, f"replace_{self._resource_name()}")(**kwargs))
        except ApiException as exc:
            if exc.status == 404:
                raise ResourceNotFoundError(self._kind(), name, ns) from exc
            raise parse_api_exception(exc) from exc

    def patch(
        self,
        name: str,
        patch: dict[str, Any],
        namespace: str | None = None,
        patch_type: str = "strategic",
    ) -> T:
        """Patch a resource. patch_type: 'strategic', 'merge', or 'json'."""
        ns = namespace or self.default_namespace
        kwargs: dict[str, Any] = {
            "name": name,
            "body": patch,
        }
        if self.dry_run:
            kwargs["dry_run"] = self.dry_run
        try:
            api = self._get_api()
            patch_fn = getattr(api, f"patch_namespaced_{self._resource_name()}", None)
            if patch_fn is not None:
                return cast("T", patch_fn(namespace=ns, **kwargs))
            return cast("T", getattr(api, f"patch_{self._resource_name()}")(**kwargs))
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def apply(self, manifest: dict[str, Any], namespace: str | None = None) -> T:
        """Create the resource if absent, otherwise replace it."""
        name: str = manifest.get("metadata", {}).get("name", "")
        if self.exists(name, namespace):
            return self.update(name, manifest, namespace)
        return self.create(manifest, namespace)

    def delete(
        self,
        name: str,
        namespace: str | None = None,
        grace_period_seconds: int | None = None,
        propagation_policy: str = "Background",
    ) -> None:
        """Delete a resource by name."""
        ns = namespace or self.default_namespace
        body = client.V1DeleteOptions(
            grace_period_seconds=grace_period_seconds,
            propagation_policy=propagation_policy,
        )
        kwargs: dict[str, Any] = {"name": name, "body": body}
        if self.dry_run:
            kwargs["dry_run"] = self.dry_run
        try:
            api = self._get_api()
            delete_fn = getattr(api, f"delete_namespaced_{self._resource_name()}", None)
            if delete_fn is not None:
                delete_fn(namespace=ns, **kwargs)
            else:
                getattr(api, f"delete_{self._resource_name()}")(**kwargs)
        except ApiException as exc:
            if exc.status == 404:
                raise ResourceNotFoundError(self._kind(), name, ns) from exc
            raise parse_api_exception(exc) from exc

    def delete_collection(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
    ) -> None:
        """Delete all resources matching an optional label selector."""
        ns = namespace or self.default_namespace
        kwargs: dict[str, Any] = {}
        if label_selector:
            kwargs["label_selector"] = label_selector
        if self.dry_run:
            kwargs["dry_run"] = self.dry_run
        try:
            api = self._get_api()
            del_coll_fn = getattr(
                api, f"delete_collection_namespaced_{self._resource_name()}", None
            )
            if del_coll_fn is not None:
                del_coll_fn(namespace=ns, **kwargs)
            else:
                getattr(api, f"delete_collection_{self._resource_name()}")(**kwargs)
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def watch(
        self,
        namespace: str | None = None,
        label_selector: str | None = None,
        timeout_seconds: int = 60,
        callback: Callable[[str, T], None] | None = None,
    ) -> None:
        """Stream resource events and invoke callback(event_type, resource)."""
        ns = namespace or self.default_namespace
        kwargs: dict[str, Any] = {"timeout_seconds": timeout_seconds}
        if label_selector:
            kwargs["label_selector"] = label_selector
        api = self._get_api()
        list_fn = getattr(api, f"list_namespaced_{self._resource_name()}", None)
        if list_fn is None:
            list_fn = getattr(api, f"list_{self._resource_name()}")
        w = watch.Watch()
        for event in w.stream(list_fn, namespace=ns, **kwargs):
            event_type: str = event["type"]
            resource: T = event["object"]
            self.logger.debug("watch_event", kind=self._kind(), event_type=event_type)
            if callback:
                callback(event_type, resource)

    def wait_for_condition(
        self,
        name: str,
        namespace: str | None = None,
        condition_type: str = "Ready",
        timeout_seconds: int = 120,
    ) -> bool:
        """Poll until the resource reaches the given condition or timeout expires."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                resource = self.get(name, namespace)
                conditions = (
                    getattr(getattr(resource, "status", None), "conditions", None) or []
                )
                for cond in conditions:
                    ctype = getattr(cond, "type", None) or cond.get("type", "")
                    cstatus = getattr(cond, "status", None) or cond.get("status", "")
                    if ctype == condition_type and cstatus == "True":
                        return True
            except ResourceNotFoundError:
                pass
            time.sleep(2)
        return False

    def get_events(self, name: str, namespace: str | None = None) -> Sequence[Any]:
        """Return core events related to this resource."""
        ns = namespace or self.default_namespace
        try:
            field_selector = (
                f"involvedObject.name={name},involvedObject.kind={self._kind()}"
            )
            result = self.client.core_v1.list_namespaced_event(
                namespace=ns, field_selector=field_selector
            )
            return result.items
        except ApiException as exc:
            raise parse_api_exception(exc) from exc

    def set_dry_run(self, enabled: bool) -> None:
        """Toggle dry-run mode at runtime."""
        self.dry_run = "All" if enabled else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resource_name(self) -> str:
        """Return the snake_case name used in kubernetes-client method names."""
        return self._kind().lower().replace("-", "_")
