# syntax=docker/dockerfile:1

# ---- Stage 1: builder ----------------------------------------------------
FROM python:3.14-slim AS builder

# No .git in this build context, so setuptools-scm can't derive a version
# on its own; the release workflow passes the real tag version through.
ARG VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

WORKDIR /src

COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY kube_orchestrator/ kube_orchestrator/

RUN pip install --no-cache-dir build && \
    python -m build --wheel

# ---- Stage 2: runtime -----------------------------------------------------
FROM python:3.14-slim AS runtime

LABEL org.opencontainers.image.title="kube-orchestrator" \
      org.opencontainers.image.description="A full-featured Python SDK for Kubernetes" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/AbbesCheriif/kube-orchestrator"

RUN groupadd --gid 1000 orchestrator && \
    useradd --uid 1000 --gid orchestrator --shell /bin/bash --create-home orchestrator

COPY --from=builder /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

USER orchestrator
WORKDIR /home/orchestrator

ENTRYPOINT ["kube-orchestrator"]
CMD ["--help"]
