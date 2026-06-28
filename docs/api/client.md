# Client & Core

The `kube_orchestrator.core` package holds the pieces every resource manager
is built on: the singleton API client, kubeconfig loading, retry middleware,
structured logging and the exception hierarchy.

## KubeClient

::: kube_orchestrator.core.client.KubeClient
    options:
      show_root_heading: true
      members:
        - get_instance
        - reset
        - core_v1
        - apps_v1
        - networking_v1
        - rbac_v1
        - batch_v1
        - storage_v1
        - custom_objects

## KubeConfig

::: kube_orchestrator.core.config.KubeConfig
    options:
      show_root_heading: true

## Settings

::: kube_orchestrator.core.settings.Settings
    options:
      show_root_heading: true

## Exceptions

`KubeOrchestratorError` is the base of every exception this library raises;
catch it to handle any library failure generically, or catch a specific
subclass (`ResourceNotFoundError`, `ResourceAlreadyExistsError`,
`AuthenticationError`, `TimeoutError`, ...) to react to a precise failure mode.

::: kube_orchestrator.core.exceptions
    options:
      show_root_heading: false
      members:
        - KubeOrchestratorError
        - ResourceNotFoundError
        - ResourceAlreadyExistsError
        - ResourceValidationError
        - APIError
