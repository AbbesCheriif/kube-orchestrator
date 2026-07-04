"""Unit tests for kube_orchestrator.resources.workloads._builders.probe_builder."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.workloads._builders.probe_builder import ProbeBuilder


@pytest.mark.unit
class TestProbeBuilder:
    def test_empty_builder_returns_empty_dict(self) -> None:
        assert ProbeBuilder().build() == {}

    def test_exec_probe(self) -> None:
        probe = ProbeBuilder().exec_probe(["cat", "/tmp/healthy"]).build()
        assert probe["exec"]["command"] == ["cat", "/tmp/healthy"]

    def test_http_get_probe_minimal(self) -> None:
        probe = ProbeBuilder().http_get_probe("/healthz", 8080).build()
        assert probe["httpGet"] == {"path": "/healthz", "port": 8080, "scheme": "HTTP"}

    def test_http_get_probe_with_host_and_headers(self) -> None:
        probe = (
            ProbeBuilder()
            .http_get_probe(
                "/healthz",
                8080,
                host="internal.local",
                scheme="HTTPS",
                http_headers=[{"name": "X-Check", "value": "1"}],
            )
            .build()
        )
        assert probe["httpGet"]["host"] == "internal.local"
        assert probe["httpGet"]["scheme"] == "HTTPS"
        assert probe["httpGet"]["httpHeaders"] == [{"name": "X-Check", "value": "1"}]

    def test_tcp_socket_probe_minimal(self) -> None:
        probe = ProbeBuilder().tcp_socket_probe(5432).build()
        assert probe["tcpSocket"] == {"port": 5432}

    def test_tcp_socket_probe_with_host(self) -> None:
        probe = ProbeBuilder().tcp_socket_probe(5432, host="db.internal").build()
        assert probe["tcpSocket"]["host"] == "db.internal"

    def test_grpc_probe_minimal(self) -> None:
        probe = ProbeBuilder().grpc_probe(9090).build()
        assert probe["grpc"] == {"port": 9090}

    def test_grpc_probe_with_service(self) -> None:
        probe = ProbeBuilder().grpc_probe(9090, service="health.v1.Health").build()
        assert probe["grpc"]["service"] == "health.v1.Health"

    def test_with_timing_defaults(self) -> None:
        probe = ProbeBuilder().with_timing().build()
        assert probe["initialDelaySeconds"] == 0
        assert probe["periodSeconds"] == 10
        assert probe["timeoutSeconds"] == 1
        assert probe["successThreshold"] == 1
        assert probe["failureThreshold"] == 3
        assert "terminationGracePeriodSeconds" not in probe

    def test_with_timing_custom_and_termination_grace(self) -> None:
        probe = (
            ProbeBuilder()
            .with_timing(
                initial_delay=5,
                period=20,
                timeout=3,
                success_threshold=2,
                failure_threshold=5,
                termination_grace=30,
            )
            .build()
        )
        assert probe["initialDelaySeconds"] == 5
        assert probe["terminationGracePeriodSeconds"] == 30

    def test_chained_probe_with_timing(self) -> None:
        probe = (
            ProbeBuilder()
            .http_get_probe("/healthz", 8080)
            .with_timing(initial_delay=10)
            .build()
        )
        assert probe["httpGet"]["path"] == "/healthz"
        assert probe["initialDelaySeconds"] == 10

    def test_build_returns_a_copy(self) -> None:
        builder = ProbeBuilder().exec_probe(["true"])
        probe_a = builder.build()
        probe_a["mutated"] = True
        assert "mutated" not in builder.build()
