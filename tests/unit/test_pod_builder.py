"""Unit tests for kube_orchestrator.resources.workloads._builders.pod_builder."""

from __future__ import annotations

import pytest

from kube_orchestrator.resources.workloads._builders.pod_builder import PodBuilder


@pytest.mark.unit
class TestPodBuilderMetadata:
    def test_minimal_build(self) -> None:
        manifest = PodBuilder("web").build()
        assert manifest["apiVersion"] == "v1"
        assert manifest["kind"] == "Pod"
        assert manifest["metadata"] == {"name": "web", "namespace": "default"}
        assert manifest["spec"]["containers"] == []

    def test_full_metadata(self) -> None:
        manifest = PodBuilder(
            "web",
            namespace="prod",
            labels={"app": "web"},
            annotations={"team": "core"},
            generate_name="web-",
        ).build()
        assert manifest["metadata"]["namespace"] == "prod"
        assert manifest["metadata"]["labels"] == {"app": "web"}
        assert manifest["metadata"]["annotations"] == {"team": "core"}
        assert manifest["metadata"]["generateName"] == "web-"


@pytest.mark.unit
class TestContainerHelpers:
    def test_with_container_minimal(self) -> None:
        manifest = PodBuilder("web").with_container("app", "nginx:latest").build()
        container = manifest["spec"]["containers"][0]
        assert container == {
            "name": "app",
            "image": "nginx:latest",
            "imagePullPolicy": "IfNotPresent",
        }

    def test_with_container_full(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container(
                "app",
                "nginx:latest",
                command=["nginx"],
                args=["-g", "daemon off;"],
                working_dir="/app",
                image_pull_policy="Always",
            )
            .build()
        )
        container = manifest["spec"]["containers"][0]
        assert container["command"] == ["nginx"]
        assert container["args"] == ["-g", "daemon off;"]
        assert container["workingDir"] == "/app"
        assert container["imagePullPolicy"] == "Always"

    def test_with_env(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_env("app", "FOO", "bar")
            .build()
        )
        assert manifest["spec"]["containers"][0]["env"] == [{"name": "FOO", "value": "bar"}]

    def test_with_env_from_configmap(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_env_from_configmap("app", "DB_HOST", "app-config", "host")
            .build()
        )
        env = manifest["spec"]["containers"][0]["env"][0]
        assert env["valueFrom"]["configMapKeyRef"] == {"name": "app-config", "key": "host"}

    def test_with_env_from_secret(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_env_from_secret("app", "DB_PASS", "app-secret", "password")
            .build()
        )
        env = manifest["spec"]["containers"][0]["env"][0]
        assert env["valueFrom"]["secretKeyRef"] == {"name": "app-secret", "key": "password"}

    def test_with_env_from_all_fields(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_env_from("app", configmap_name="cfg", secret_name="sec", prefix="APP_")
            .build()
        )
        env_from = manifest["spec"]["containers"][0]["envFrom"][0]
        assert env_from == {
            "configMapRef": {"name": "cfg"},
            "secretRef": {"name": "sec"},
            "prefix": "APP_",
        }

    def test_with_env_from_empty(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_env_from("app")
            .build()
        )
        assert manifest["spec"]["containers"][0]["envFrom"] == [{}]

    def test_with_ports(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_ports("app", [{"containerPort": 80}])
            .build()
        )
        assert manifest["spec"]["containers"][0]["ports"] == [{"containerPort": 80}]

    def test_with_resources_full(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_resources(
                "app",
                cpu_request="100m",
                memory_request="128Mi",
                cpu_limit="500m",
                memory_limit="512Mi",
                ephemeral_storage_limit="1Gi",
            )
            .build()
        )
        resources = manifest["spec"]["containers"][0]["resources"]
        assert resources["requests"] == {"cpu": "100m", "memory": "128Mi"}
        assert resources["limits"] == {
            "cpu": "500m",
            "memory": "512Mi",
            "ephemeral-storage": "1Gi",
        }

    def test_with_resources_empty(self) -> None:
        manifest = (
            PodBuilder("web").with_container("app", "nginx").with_resources("app").build()
        )
        assert manifest["spec"]["containers"][0]["resources"] == {}

    def test_with_volume_mount_full(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_volume_mount(
                "app",
                "data",
                "/data",
                sub_path="sub",
                read_only=True,
                mount_propagation="Bidirectional",
                sub_path_expr="$(POD_NAME)",
            )
            .build()
        )
        mount = manifest["spec"]["containers"][0]["volumeMounts"][0]
        assert mount["subPath"] == "sub"
        assert mount["subPathExpr"] == "$(POD_NAME)"
        assert mount["mountPropagation"] == "Bidirectional"
        assert mount["readOnly"] is True

    def test_with_volume_mount_minimal(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_volume_mount("app", "data", "/data")
            .build()
        )
        mount = manifest["spec"]["containers"][0]["volumeMounts"][0]
        assert mount == {"name": "data", "mountPath": "/data", "readOnly": False}


@pytest.mark.unit
class TestProbes:
    def test_liveness_probe_with_exec(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_liveness_probe("app", exec_command=["cat", "/tmp/ok"])
            .build()
        )
        probe = manifest["spec"]["containers"][0]["livenessProbe"]
        assert probe["exec"]["command"] == ["cat", "/tmp/ok"]

    def test_readiness_probe_with_http_get(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_readiness_probe("app", http_get={"path": "/", "port": 80})
            .build()
        )
        probe = manifest["spec"]["containers"][0]["readinessProbe"]
        assert probe["httpGet"] == {"path": "/", "port": 80}

    def test_startup_probe_with_tcp_socket(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_startup_probe("app", tcp_socket={"port": 80})
            .build()
        )
        probe = manifest["spec"]["containers"][0]["startupProbe"]
        assert probe["tcpSocket"] == {"port": 80}

    def test_probe_with_grpc(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_liveness_probe("app", grpc={"port": 9090})
            .build()
        )
        probe = manifest["spec"]["containers"][0]["livenessProbe"]
        assert probe["grpc"] == {"port": 9090}

    def test_probe_without_handler(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_liveness_probe("app")
            .build()
        )
        probe = manifest["spec"]["containers"][0]["livenessProbe"]
        assert "exec" not in probe
        assert probe["periodSeconds"] == 10


@pytest.mark.unit
class TestLifecycleAndSecurityContext:
    def test_with_lifecycle_both_hooks(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_lifecycle(
                "app",
                post_start={"exec": {"command": ["echo", "start"]}},
                pre_stop={"exec": {"command": ["echo", "stop"]}},
            )
            .build()
        )
        lifecycle = manifest["spec"]["containers"][0]["lifecycle"]
        assert "postStart" in lifecycle
        assert "preStop" in lifecycle

    def test_with_lifecycle_empty(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_lifecycle("app")
            .build()
        )
        assert manifest["spec"]["containers"][0]["lifecycle"] == {}

    def test_with_security_context_full(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_security_context(
                "app",
                run_as_user=1000,
                run_as_group=1000,
                run_as_non_root=True,
                read_only_root_fs=True,
                allow_privilege_escalation=False,
                privileged=False,
                capabilities_add=["NET_ADMIN"],
                capabilities_drop=["ALL"],
                proc_mount="Default",
            )
            .build()
        )
        ctx = manifest["spec"]["containers"][0]["securityContext"]
        assert ctx["runAsUser"] == 1000
        assert ctx["capabilities"] == {"add": ["NET_ADMIN"], "drop": ["ALL"]}
        assert ctx["procMount"] == "Default"

    def test_with_security_context_empty(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_container("app", "nginx")
            .with_security_context("app")
            .build()
        )
        assert manifest["spec"]["containers"][0]["securityContext"] == {}

    def test_with_init_container_full(self) -> None:
        manifest = (
            PodBuilder("web")
            .with_init_container(
                "init",
                "busybox",
                command=["sh"],
                args=["-c", "echo hi"],
                working_dir="/tmp",
                image_pull_policy="Always",
            )
            .build()
        )
        init = manifest["spec"]["initContainers"][0]
        assert init["command"] == ["sh"]
        assert init["workingDir"] == "/tmp"


@pytest.mark.unit
class TestVolumes:
    def test_with_volume_config_map(self) -> None:
        manifest = PodBuilder("web").with_volume("cfg", config_map="app-config").build()
        assert manifest["spec"]["volumes"][0]["configMap"] == {"name": "app-config"}

    def test_with_volume_secret(self) -> None:
        manifest = PodBuilder("web").with_volume("sec", secret="app-secret").build()
        assert manifest["spec"]["volumes"][0]["secret"] == {"secretName": "app-secret"}

    def test_with_volume_pvc(self) -> None:
        manifest = PodBuilder("web").with_volume("data", pvc="data-pvc").build()
        assert manifest["spec"]["volumes"][0]["persistentVolumeClaim"] == {
            "claimName": "data-pvc"
        }

    def test_with_volume_empty_dir(self) -> None:
        manifest = PodBuilder("web").with_volume("scratch", empty_dir={}).build()
        assert manifest["spec"]["volumes"][0]["emptyDir"] == {}

    def test_with_volume_host_path(self) -> None:
        manifest = PodBuilder("web").with_volume(
            "hostvol", host_path={"path": "/mnt"}
        ).build()
        assert manifest["spec"]["volumes"][0]["hostPath"] == {"path": "/mnt"}

    def test_with_volume_projected(self) -> None:
        manifest = PodBuilder("web").with_volume(
            "proj", projected={"sources": []}
        ).build()
        assert manifest["spec"]["volumes"][0]["projected"] == {"sources": []}

    def test_with_volume_no_source_is_bare(self) -> None:
        manifest = PodBuilder("web").with_volume("bare").build()
        assert manifest["spec"]["volumes"][0] == {"name": "bare"}


@pytest.mark.unit
class TestPodLevelSpecHelpers:
    def test_with_node_selector(self) -> None:
        manifest = PodBuilder("web").with_node_selector({"disktype": "ssd"}).build()
        assert manifest["spec"]["nodeSelector"] == {"disktype": "ssd"}

    def test_with_node_name(self) -> None:
        manifest = PodBuilder("web").with_node_name("worker-1").build()
        assert manifest["spec"]["nodeName"] == "worker-1"

    def test_with_affinity_all_types(self) -> None:
        manifest = PodBuilder("web").with_affinity(
            node_affinity={"a": 1}, pod_affinity={"b": 2}, pod_anti_affinity={"c": 3}
        ).build()
        assert manifest["spec"]["affinity"] == {
            "nodeAffinity": {"a": 1},
            "podAffinity": {"b": 2},
            "podAntiAffinity": {"c": 3},
        }

    def test_with_affinity_empty(self) -> None:
        manifest = PodBuilder("web").with_affinity().build()
        assert manifest["spec"]["affinity"] == {}

    def test_with_tolerations(self) -> None:
        tolerations = [{"key": "k", "operator": "Exists"}]
        manifest = PodBuilder("web").with_tolerations(tolerations).build()
        assert manifest["spec"]["tolerations"] == tolerations

    def test_with_topology_spread(self) -> None:
        constraints = [{"maxSkew": 1}]
        manifest = PodBuilder("web").with_topology_spread(constraints).build()
        assert manifest["spec"]["topologySpreadConstraints"] == constraints

    def test_with_image_pull_secrets(self) -> None:
        manifest = PodBuilder("web").with_image_pull_secrets(["cred1", "cred2"]).build()
        assert manifest["spec"]["imagePullSecrets"] == [
            {"name": "cred1"},
            {"name": "cred2"},
        ]

    def test_with_service_account(self) -> None:
        manifest = PodBuilder("web").with_service_account("my-sa", automount=False).build()
        assert manifest["spec"]["serviceAccountName"] == "my-sa"
        assert manifest["spec"]["automountServiceAccountToken"] is False

    def test_with_dns_config_full(self) -> None:
        manifest = PodBuilder("web").with_dns_config(
            nameservers=["8.8.8.8"], searches=["svc.cluster.local"], options=[{"name": "ndots"}]
        ).build()
        dns = manifest["spec"]["dnsConfig"]
        assert dns["nameservers"] == ["8.8.8.8"]
        assert dns["searches"] == ["svc.cluster.local"]
        assert dns["options"] == [{"name": "ndots"}]

    def test_with_dns_config_empty(self) -> None:
        manifest = PodBuilder("web").with_dns_config().build()
        assert manifest["spec"]["dnsConfig"] == {}

    def test_with_dns_policy(self) -> None:
        manifest = PodBuilder("web").with_dns_policy("ClusterFirst").build()
        assert manifest["spec"]["dnsPolicy"] == "ClusterFirst"

    def test_with_host_network(self) -> None:
        assert PodBuilder("web").with_host_network(True).build()["spec"]["hostNetwork"] is True

    def test_with_host_pid(self) -> None:
        assert PodBuilder("web").with_host_pid(True).build()["spec"]["hostPID"] is True

    def test_with_host_ipc(self) -> None:
        assert PodBuilder("web").with_host_ipc(True).build()["spec"]["hostIPC"] is True

    def test_with_hostname_full(self) -> None:
        manifest = PodBuilder("web").with_hostname(
            "web-1", subdomain="svc", set_hostname_as_fqdn=True
        ).build()
        assert manifest["spec"]["hostname"] == "web-1"
        assert manifest["spec"]["subdomain"] == "svc"
        assert manifest["spec"]["setHostnameAsFQDN"] is True

    def test_with_hostname_minimal(self) -> None:
        manifest = PodBuilder("web").with_hostname("web-1").build()
        assert "subdomain" not in manifest["spec"]

    def test_with_restart_policy(self) -> None:
        manifest = PodBuilder("web").with_restart_policy("Never").build()
        assert manifest["spec"]["restartPolicy"] == "Never"

    def test_with_termination_grace_period(self) -> None:
        manifest = PodBuilder("web").with_termination_grace_period(30).build()
        assert manifest["spec"]["terminationGracePeriodSeconds"] == 30

    def test_with_active_deadline(self) -> None:
        manifest = PodBuilder("web").with_active_deadline(600).build()
        assert manifest["spec"]["activeDeadlineSeconds"] == 600

    def test_with_priority(self) -> None:
        manifest = PodBuilder("web").with_priority("high").build()
        assert manifest["spec"]["priorityClassName"] == "high"

    def test_with_runtime_class(self) -> None:
        manifest = PodBuilder("web").with_runtime_class("gvisor").build()
        assert manifest["spec"]["runtimeClassName"] == "gvisor"

    def test_with_scheduler(self) -> None:
        manifest = PodBuilder("web").with_scheduler("custom-scheduler").build()
        assert manifest["spec"]["schedulerName"] == "custom-scheduler"

    def test_with_pod_security_context_full(self) -> None:
        manifest = PodBuilder("web").with_pod_security_context(
            run_as_user=1000,
            run_as_group=1000,
            run_as_non_root=True,
            fs_group=2000,
            fs_group_change_policy="OnRootMismatch",
            supplemental_groups=[3000],
            sysctls=[{"name": "net.core.somaxconn", "value": "1024"}],
        ).build()
        ctx = manifest["spec"]["securityContext"]
        assert ctx["fsGroup"] == 2000
        assert ctx["fsGroupChangePolicy"] == "OnRootMismatch"
        assert ctx["supplementalGroups"] == [3000]
        assert ctx["sysctls"] == [{"name": "net.core.somaxconn", "value": "1024"}]

    def test_with_pod_security_context_empty_is_not_set(self) -> None:
        manifest = PodBuilder("web").with_pod_security_context().build()
        assert "securityContext" not in manifest["spec"]

    def test_with_readiness_gate(self) -> None:
        manifest = PodBuilder("web").with_readiness_gate("www.example.com/ready").build()
        assert manifest["spec"]["readinessGates"] == [
            {"conditionType": "www.example.com/ready"}
        ]

    def test_with_scheduling_gate(self) -> None:
        manifest = PodBuilder("web").with_scheduling_gate("example.com/gate").build()
        assert manifest["spec"]["schedulingGates"] == [{"name": "example.com/gate"}]

    def test_with_share_process_namespace(self) -> None:
        manifest = PodBuilder("web").with_share_process_namespace(True).build()
        assert manifest["spec"]["shareProcessNamespace"] is True

    def test_with_os(self) -> None:
        manifest = PodBuilder("web").with_os("linux").build()
        assert manifest["spec"]["os"] == {"name": "linux"}


@pytest.mark.unit
class TestBuildAssembly:
    def test_full_chain(self) -> None:
        manifest = (
            PodBuilder("web", namespace="prod", labels={"app": "web"})
            .with_container("app", "nginx:latest")
            .with_init_container("init", "busybox")
            .with_volume("data", empty_dir={})
            .with_pod_security_context(run_as_user=1000)
            .build()
        )
        assert manifest["spec"]["containers"][0]["name"] == "app"
        assert manifest["spec"]["initContainers"][0]["name"] == "init"
        assert manifest["spec"]["volumes"][0]["name"] == "data"
        assert manifest["spec"]["securityContext"]["runAsUser"] == 1000
