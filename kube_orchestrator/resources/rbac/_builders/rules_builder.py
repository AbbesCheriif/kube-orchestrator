from __future__ import annotations

from typing import Any

_READ = ["get", "list", "watch"]
_WRITE = [*_READ, "create", "update", "patch"]
_ADMIN = [*_WRITE, "delete", "deletecollection"]
_ALL = _ADMIN


class RulesBuilder:

    def __init__(self) -> None:
        self._rules: list[dict[str, Any]] = []

    def _add(
        self,
        api_groups: list[str],
        resources: list[str],
        verbs: list[str],
        resource_names: list[str] | None = None,
    ) -> RulesBuilder:
        rule: dict[str, Any] = {
            "apiGroups": api_groups,
            "resources": resources,
            "verbs": verbs,
        }
        if resource_names:
            rule["resourceNames"] = resource_names
        self._rules.append(rule)
        return self

    def allow_pods(self, verbs: list[str] = _READ) -> RulesBuilder:
        return self._add([""], ["pods", "pods/log", "pods/exec", "pods/status"], verbs)

    def allow_deployments(self, verbs: list[str] = _READ) -> RulesBuilder:
        return self._add(["apps"], ["deployments", "deployments/scale"], verbs)

    def allow_services(self, verbs: list[str] = _READ) -> RulesBuilder:
        return self._add([""], ["services", "endpoints"], verbs)

    def allow_configmaps(self, verbs: list[str] = _READ) -> RulesBuilder:
        return self._add([""], ["configmaps"], verbs)

    def allow_secrets(self, verbs: list[str] = _READ) -> RulesBuilder:
        return self._add([""], ["secrets"], verbs)

    def allow_all(self, verbs: list[str] = _ALL) -> RulesBuilder:
        return self._add(["*"], ["*"], verbs)

    def custom(
        self,
        api_groups: list[str],
        resources: list[str],
        verbs: list[str],
        resource_names: list[str] | None = None,
    ) -> RulesBuilder:
        return self._add(api_groups, resources, verbs, resource_names)

    def read_only(self) -> RulesBuilder:
        return self._add(["*"], ["*"], _READ)

    def read_write(self) -> RulesBuilder:
        return self._add(["*"], ["*"], _WRITE)

    def admin(self) -> RulesBuilder:
        return self._add(["*"], ["*"], _ADMIN)

    def build(self) -> list[dict[str, Any]]:
        return list(self._rules)
