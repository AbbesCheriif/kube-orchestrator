"""Manifest validator and kind router for Kubernetes resources."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from kube_orchestrator.resources.base import BaseResourceManager

# Maps kind → (manager_class_path, expected api_version)
KIND_REGISTRY: dict[str, dict[str, str]] = {
    "Namespace": {
        "manager": "kube_orchestrator.resources.cluster.namespace.NamespaceManager",
        "api_version": "v1",
    },
    "Pod": {
        "manager": "kube_orchestrator.resources.workloads.pod.PodManager",
        "api_version": "v1",
    },
    "Deployment": {
        "manager": "kube_orchestrator.resources.workloads.deployment.DeploymentManager",
        "api_version": "apps/v1",
    },
    "ReplicaSet": {
        "manager": "kube_orchestrator.resources.workloads.replicaset.ReplicaSetManager",
        "api_version": "apps/v1",
    },
    "StatefulSet": {
        "manager": "kube_orchestrator.resources.workloads.statefulset.StatefulSetManager",
        "api_version": "apps/v1",
    },
    "DaemonSet": {
        "manager": "kube_orchestrator.resources.workloads.daemonset.DaemonSetManager",
        "api_version": "apps/v1",
    },
    "Job": {
        "manager": "kube_orchestrator.resources.workloads.job.JobManager",
        "api_version": "batch/v1",
    },
    "CronJob": {
        "manager": "kube_orchestrator.resources.workloads.cronjob.CronJobManager",
        "api_version": "batch/v1",
    },
    "Service": {
        "manager": "kube_orchestrator.resources.networking.service.ServiceManager",
        "api_version": "v1",
    },
    "Ingress": {
        "manager": "kube_orchestrator.resources.networking.ingress.IngressManager",
        "api_version": "networking.k8s.io/v1",
    },
    "IngressClass": {
        "manager": "kube_orchestrator.resources.networking.ingress_class.IngressClassManager",
        "api_version": "networking.k8s.io/v1",
    },
    "NetworkPolicy": {
        "manager": "kube_orchestrator.resources.networking.network_policy.NetworkPolicyManager",
        "api_version": "networking.k8s.io/v1",
    },
    "ConfigMap": {
        "manager": "kube_orchestrator.resources.storage.configmap.ConfigMapManager",
        "api_version": "v1",
    },
    "Secret": {
        "manager": "kube_orchestrator.resources.storage.secret.SecretManager",
        "api_version": "v1",
    },
    "PersistentVolume": {
        "manager": "kube_orchestrator.resources.storage.persistent_volume.PersistentVolumeManager",
        "api_version": "v1",
    },
    "PersistentVolumeClaim": {
        "manager": "kube_orchestrator.resources.storage.persistent_volume_claim.PVCManager",
        "api_version": "v1",
    },
    "StorageClass": {
        "manager": "kube_orchestrator.resources.storage.storage_class.StorageClassManager",
        "api_version": "storage.k8s.io/v1",
    },
    "ServiceAccount": {
        "manager": "kube_orchestrator.resources.rbac.service_account.ServiceAccountManager",
        "api_version": "v1",
    },
    "Role": {
        "manager": "kube_orchestrator.resources.rbac.role.RoleManager",
        "api_version": "rbac.authorization.k8s.io/v1",
    },
    "ClusterRole": {
        "manager": "kube_orchestrator.resources.rbac.role.ClusterRoleManager",
        "api_version": "rbac.authorization.k8s.io/v1",
    },
    "RoleBinding": {
        "manager": "kube_orchestrator.resources.rbac.role_binding.RoleBindingManager",
        "api_version": "rbac.authorization.k8s.io/v1",
    },
    "ClusterRoleBinding": {
        "manager": "kube_orchestrator.resources.rbac.role_binding.ClusterRoleBindingManager",
        "api_version": "rbac.authorization.k8s.io/v1",
    },
    "HorizontalPodAutoscaler": {
        "manager": "kube_orchestrator.resources.cluster.hpa.HPAManager",
        "api_version": "autoscaling/v2",
    },
    "PodDisruptionBudget": {
        "manager": "kube_orchestrator.resources.cluster.pdb.PodDisruptionBudgetManager",
        "api_version": "policy/v1",
    },
    "ResourceQuota": {
        "manager": "kube_orchestrator.resources.cluster.resource_quota.ResourceQuotaManager",
        "api_version": "v1",
    },
    "LimitRange": {
        "manager": "kube_orchestrator.resources.cluster.limit_range.LimitRangeManager",
        "api_version": "v1",
    },
    "PriorityClass": {
        "manager": "kube_orchestrator.resources.cluster.priority_class.PriorityClassManager",
        "api_version": "scheduling.k8s.io/v1",
    },
    "RuntimeClass": {
        "manager": "kube_orchestrator.resources.cluster.runtime_class.RuntimeClassManager",
        "api_version": "node.k8s.io/v1",
    },
    "CustomResourceDefinition": {
        "manager": "kube_orchestrator.crd.installer.CRDInstaller",
        "api_version": "apiextensions.k8s.io/v1",
    },
}

_REQUIRED_TOP_LEVEL = ("apiVersion", "kind", "metadata")
_REQUIRED_METADATA = ("name",)


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Run all validation checks and return a list of error messages."""
    errors: list[str] = []
    errors.extend(validate_required_fields(manifest))
    if not errors:
        errors.extend(validate_spec_for_kind(manifest))
    return errors


def validate_required_fields(manifest: dict[str, Any]) -> list[str]:
    """Ensure top-level fields and metadata.name are present."""
    errors: list[str] = []
    for field in _REQUIRED_TOP_LEVEL:
        if field not in manifest:
            errors.append(f"Missing required field: '{field}'")
    if "metadata" in manifest:
        meta = manifest["metadata"]
        if not isinstance(meta, dict):
            errors.append("'metadata' must be a mapping")
        else:
            for field in _REQUIRED_METADATA:
                if field not in meta:
                    errors.append(f"Missing required metadata field: '{field}'")
    return errors


def detect_api_version(manifest: dict[str, Any]) -> str:
    """Return the apiVersion string from the manifest, or an empty string."""
    return str(manifest.get("apiVersion", ""))


def route_by_kind(
    manifest: dict[str, Any],
) -> type["BaseResourceManager[Any]"] | None:
    """Return the manager class for the manifest's kind, or None if unknown."""
    import importlib

    kind = manifest.get("kind", "")
    entry = KIND_REGISTRY.get(kind)
    if not entry:
        return None
    module_path, class_name = entry["manager"].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def validate_spec_for_kind(manifest: dict[str, Any]) -> list[str]:
    """Perform kind-specific spec validation and return error messages."""
    errors: list[str] = []
    kind = manifest.get("kind", "")
    spec = manifest.get("spec")

    if kind in ("Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"):
        if not spec:
            errors.append(f"{kind} must have a 'spec' field")
        else:
            if "selector" not in spec:
                errors.append(f"{kind}.spec must have a 'selector'")
            if "template" not in spec:
                errors.append(f"{kind}.spec must have a 'template'")

    elif kind == "Service":
        if not spec:
            errors.append("Service must have a 'spec' field")
        else:
            if "ports" not in spec:
                errors.append("Service.spec must have 'ports'")

    elif kind == "HorizontalPodAutoscaler":
        if not spec:
            errors.append("HorizontalPodAutoscaler must have a 'spec' field")
        else:
            if "scaleTargetRef" not in spec:
                errors.append("HorizontalPodAutoscaler.spec must have 'scaleTargetRef'")
            if "maxReplicas" not in spec:
                errors.append("HorizontalPodAutoscaler.spec must have 'maxReplicas'")

    elif kind == "Ingress":
        if not spec:
            errors.append("Ingress must have a 'spec' field")

    return errors
