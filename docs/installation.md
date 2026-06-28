# Installation

## From PyPI

```bash
pip install kube-orchestrator
```

Add the `dev` extra if you want to run the test suite and linters locally:

```bash
pip install kube-orchestrator[dev]
```

Add the `docs` extra if you want to build this documentation site locally:

```bash
pip install kube-orchestrator[docs]
```

## From Docker

```bash
docker pull ghcr.io/username/kube-orchestrator
docker run --rm -v ~/.kube/config:/home/orchestrator/.kube/config:ro \
  ghcr.io/username/kube-orchestrator doctor
```

## From source

```bash
git clone https://github.com/username/kube-orchestrator.git
cd kube-orchestrator
pip install -e ".[dev]"
pre-commit install
```

## Verify the installation

```bash
python -c "import kube_orchestrator; print(kube_orchestrator.__version__)"
kube-orchestrator --version
```

## Requirements

- Python 3.10, 3.11 or 3.12
- Access to a Kubernetes cluster (via `~/.kube/config` or in-cluster service account)
