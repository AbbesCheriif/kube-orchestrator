"""Fluent builder for Kubernetes Probe manifests."""

from __future__ import annotations

from typing import Any


class ProbeBuilder:
    """Fluent interface for building Kubernetes probe specifications."""

    def __init__(self) -> None:
        self._probe: dict[str, Any] = {}

    def exec_probe(self, command: list[str]) -> ProbeBuilder:
        self._probe["exec"] = {"command": command}
        return self

    def http_get_probe(
        self,
        path: str,
        port: int,
        host: str | None = None,
        scheme: str = "HTTP",
        http_headers: list[Any] | None = None,
    ) -> ProbeBuilder:
        http_get: dict[str, Any] = {"path": path, "port": port, "scheme": scheme}
        if host:
            http_get["host"] = host
        if http_headers:
            http_get["httpHeaders"] = http_headers
        self._probe["httpGet"] = http_get
        return self

    def tcp_socket_probe(self, port: int, host: str | None = None) -> ProbeBuilder:
        tcp: dict[str, Any] = {"port": port}
        if host:
            tcp["host"] = host
        self._probe["tcpSocket"] = tcp
        return self

    def grpc_probe(self, port: int, service: str | None = None) -> ProbeBuilder:
        grpc: dict[str, Any] = {"port": port}
        if service:
            grpc["service"] = service
        self._probe["grpc"] = grpc
        return self

    def with_timing(
        self,
        initial_delay: int = 0,
        period: int = 10,
        timeout: int = 1,
        success_threshold: int = 1,
        failure_threshold: int = 3,
        termination_grace: int | None = None,
    ) -> ProbeBuilder:
        self._probe.update(
            {
                "initialDelaySeconds": initial_delay,
                "periodSeconds": period,
                "timeoutSeconds": timeout,
                "successThreshold": success_threshold,
                "failureThreshold": failure_threshold,
            }
        )
        if termination_grace is not None:
            self._probe["terminationGracePeriodSeconds"] = termination_grace
        return self

    def build(self) -> dict[str, Any]:
        return dict(self._probe)
