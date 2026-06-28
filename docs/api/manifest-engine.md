# Manifest Engine

The GitOps engine: load YAML/JSON manifests, validate and order them by
dependency, render Jinja2 templates with a values file (mini Helm), then
apply, diff or delete them idempotently.

## Loader

::: kube_orchestrator.manifest.loader
    options:
      show_root_heading: false
      members:
        - load_file
        - load_directory
        - load_string
        - load_url
        - load_stdin

## Validator

::: kube_orchestrator.manifest.validator
    options:
      show_root_heading: false
      members:
        - validate_manifest
        - validate_required_fields
        - route_by_kind
        - order_by_dependency
        - detect_circular_deps

## Renderer

::: kube_orchestrator.manifest.renderer
    options:
      show_root_heading: false
      members:
        - render_file
        - render_directory
        - merge_values
        - override_values

## ManifestApplier

::: kube_orchestrator.manifest.applier.ManifestApplier
    options:
      show_root_heading: true

## ManifestDeleter

::: kube_orchestrator.manifest.deleter.ManifestDeleter
    options:
      show_root_heading: true
