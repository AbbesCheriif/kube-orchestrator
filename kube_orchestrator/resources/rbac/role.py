from __future__ import annotations

from kubernetes.client import V1ClusterRole, V1ObjectMeta, V1PolicyRule, V1Role

from kube_orchestrator.resources.base import BaseResourceManager


class RoleManager(BaseResourceManager[V1Role]):

    def _get_api(self):
        return self.client.rbac_v1

    def _kind(self) -> str:
        return "Role"

    def _api_version(self) -> str:
        return "rbac.authorization.k8s.io/v1"

    def _build_rules(self, rules: list[dict]) -> list[V1PolicyRule]:
        return [
            V1PolicyRule(
                api_groups=r.get("apiGroups", [""]),
                resources=r.get("resources", []),
                verbs=r.get("verbs", []),
                resource_names=r.get("resourceNames"),
                non_resource_urls=r.get("nonResourceURLs"),
            )
            for r in rules
        ]

    def create_role(
        self,
        name: str,
        namespace: str,
        rules: list[dict],
        labels: dict | None = None,
    ) -> V1Role:
        body = V1Role(
            api_version="rbac.authorization.k8s.io/v1",
            kind="Role",
            metadata=V1ObjectMeta(name=name, namespace=namespace, labels=labels),
            rules=self._build_rules(rules),
        )
        return self._get_api().create_namespaced_role(
            namespace=namespace, body=body, dry_run=self.dry_run
        )

    def create_with_rules(
        self,
        name: str,
        namespace: str,
        api_groups: list[str],
        resources: list[str],
        verbs: list[str],
        resource_names: list[str] | None = None,
    ) -> V1Role:
        rule: dict = {"apiGroups": api_groups, "resources": resources, "verbs": verbs}
        if resource_names:
            rule["resourceNames"] = resource_names
        return self.create_role(name=name, namespace=namespace, rules=[rule])

    def add_rule(
        self,
        name: str,
        namespace: str,
        api_groups: list[str],
        resources: list[str],
        verbs: list[str],
        resource_names: list[str] | None = None,
    ) -> V1Role:
        role = self.get_role(name, namespace)
        new_rule = V1PolicyRule(
            api_groups=api_groups,
            resources=resources,
            verbs=verbs,
            resource_names=resource_names,
        )
        role.rules = (role.rules or []) + [new_rule]
        return self._get_api().replace_namespaced_role(
            name=name, namespace=namespace, body=role, dry_run=self.dry_run
        )

    def get_role(self, name: str, namespace: str) -> V1Role:
        return self._get_api().read_namespaced_role(name=name, namespace=namespace)

    def list_roles(self, namespace: str) -> list[V1Role]:
        return self._get_api().list_namespaced_role(namespace=namespace).items

    def delete_role(self, name: str, namespace: str) -> None:
        self._get_api().delete_namespaced_role(
            name=name, namespace=namespace, dry_run=self.dry_run
        )


class ClusterRoleManager(BaseResourceManager[V1ClusterRole]):

    def _get_api(self):
        return self.client.rbac_v1

    def _kind(self) -> str:
        return "ClusterRole"

    def _api_version(self) -> str:
        return "rbac.authorization.k8s.io/v1"

    def _build_rules(self, rules: list[dict]) -> list[V1PolicyRule]:
        return [
            V1PolicyRule(
                api_groups=r.get("apiGroups", [""]),
                resources=r.get("resources", []),
                verbs=r.get("verbs", []),
                resource_names=r.get("resourceNames"),
                non_resource_urls=r.get("nonResourceURLs"),
            )
            for r in rules
        ]

    def create_cluster_role(
        self,
        name: str,
        rules: list[dict],
        aggregation_rule: dict | None = None,
        labels: dict | None = None,
    ) -> V1ClusterRole:
        from kubernetes.client import V1AggregationRule

        body = V1ClusterRole(
            api_version="rbac.authorization.k8s.io/v1",
            kind="ClusterRole",
            metadata=V1ObjectMeta(name=name, labels=labels),
            rules=self._build_rules(rules),
            aggregation_rule=(
                V1AggregationRule(
                    cluster_role_selectors=aggregation_rule.get("clusterRoleSelectors")
                )
                if aggregation_rule
                else None
            ),
        )
        return self._get_api().create_cluster_role(body=body, dry_run=self.dry_run)

    def create_with_rules(
        self,
        name: str,
        api_groups: list[str],
        resources: list[str],
        verbs: list[str],
        non_resource_urls: list[str] | None = None,
    ) -> V1ClusterRole:
        rule: dict = {"apiGroups": api_groups, "resources": resources, "verbs": verbs}
        if non_resource_urls:
            rule["nonResourceURLs"] = non_resource_urls
        return self.create_cluster_role(name=name, rules=[rule])

    def add_rule(
        self,
        name: str,
        api_groups: list[str],
        resources: list[str],
        verbs: list[str],
        non_resource_urls: list[str] | None = None,
    ) -> V1ClusterRole:
        cr = self.get_cluster_role(name)
        new_rule = V1PolicyRule(
            api_groups=api_groups,
            resources=resources,
            verbs=verbs,
            non_resource_urls=non_resource_urls,
        )
        cr.rules = (cr.rules or []) + [new_rule]
        return self._get_api().replace_cluster_role(
            name=name, body=cr, dry_run=self.dry_run
        )

    def get_cluster_role(self, name: str) -> V1ClusterRole:
        return self._get_api().read_cluster_role(name=name)

    def list_cluster_roles(
        self, label_selector: str | None = None
    ) -> list[V1ClusterRole]:
        return self._get_api().list_cluster_role(label_selector=label_selector).items

    def delete_cluster_role(self, name: str) -> None:
        self._get_api().delete_cluster_role(name=name, dry_run=self.dry_run)
