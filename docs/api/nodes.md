# Nodes & Cluster Resources

Managers for Node lifecycle (cordon/drain/taint), Namespaces, and the
cluster-scoped resources that constrain them (ResourceQuota, LimitRange,
PriorityClass, PodDisruptionBudget, HPA, RuntimeClass).

## NodeManager

::: kube_orchestrator.resources.cluster.node.NodeManager
    options:
      show_root_heading: true

## NamespaceManager

::: kube_orchestrator.resources.cluster.namespace.NamespaceManager
    options:
      show_root_heading: true

## ResourceQuotaManager & LimitRangeManager

::: kube_orchestrator.resources.cluster.resource_quota.ResourceQuotaManager
    options:
      show_root_heading: true

::: kube_orchestrator.resources.cluster.limit_range.LimitRangeManager
    options:
      show_root_heading: true

## HPAManager

::: kube_orchestrator.resources.cluster.hpa.HPAManager
    options:
      show_root_heading: true

## PodDisruptionBudgetManager & PriorityClassManager

::: kube_orchestrator.resources.cluster.pdb.PodDisruptionBudgetManager
    options:
      show_root_heading: true

::: kube_orchestrator.resources.cluster.priority_class.PriorityClassManager
    options:
      show_root_heading: true
