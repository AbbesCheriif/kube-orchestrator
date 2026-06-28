# RBAC

Managers for Roles, ClusterRoles, their bindings, ServiceAccounts, and the
`AccessValidator` for `kubectl auth can-i`-style checks.

## RoleManager & ClusterRoleManager

::: kube_orchestrator.resources.rbac.role.RoleManager
    options:
      show_root_heading: true

::: kube_orchestrator.resources.rbac.role.ClusterRoleManager
    options:
      show_root_heading: true

## RoleBindingManager & ClusterRoleBindingManager

::: kube_orchestrator.resources.rbac.role_binding.RoleBindingManager
    options:
      show_root_heading: true

::: kube_orchestrator.resources.rbac.role_binding.ClusterRoleBindingManager
    options:
      show_root_heading: true

## ServiceAccountManager

::: kube_orchestrator.resources.rbac.service_account.ServiceAccountManager
    options:
      show_root_heading: true

## AccessValidator

::: kube_orchestrator.resources.rbac.access_validator.AccessValidator
    options:
      show_root_heading: true
