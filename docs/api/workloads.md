# Workloads

Managers for every workload-shaped resource, plus the fluent builders used to
construct their manifests field by field.

| Resource | Manager | Builder |
|---|---|---|
| Pod | `PodManager` | `PodBuilder` |
| Deployment | `DeploymentManager` | `DeploymentBuilder` |
| ReplicaSet | `ReplicaSetManager` | — |
| StatefulSet | `StatefulSetManager` | `StatefulSetBuilder` |
| DaemonSet | `DaemonSetManager` | — |
| Job | `JobManager` | — |
| CronJob | `CronJobManager` | — |

## PodManager

::: kube_orchestrator.resources.workloads.pod.PodManager
    options:
      show_root_heading: true

## DeploymentManager

::: kube_orchestrator.resources.workloads.deployment.DeploymentManager
    options:
      show_root_heading: true

## StatefulSetManager

::: kube_orchestrator.resources.workloads.statefulset.StatefulSetManager
    options:
      show_root_heading: true

## DaemonSetManager

::: kube_orchestrator.resources.workloads.daemonset.DaemonSetManager
    options:
      show_root_heading: true

## JobManager & CronJobManager

::: kube_orchestrator.resources.workloads.job.JobManager
    options:
      show_root_heading: true

::: kube_orchestrator.resources.workloads.cronjob.CronJobManager
    options:
      show_root_heading: true
