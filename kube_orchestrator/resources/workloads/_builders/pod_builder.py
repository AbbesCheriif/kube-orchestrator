"""Fluent builder for Kubernetes Pod manifests."""

from __future__ import annotations

from typing import Any


class PodBuilder:
    """Fluent interface for constructing Pod manifests covering all spec fields."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
        generate_name: str | None = None,
    ) -> None:
        self._name = name
        self._namespace = namespace
        self._labels: dict[str, str] = labels or {}
        self._annotations: dict[str, str] = annotations or {}
        self._generate_name = generate_name
        self._containers: dict[str, dict[str, Any]] = {}
        self._init_containers: dict[str, dict[str, Any]] = {}
        self._volumes: list[dict[str, Any]] = []
        self._spec: dict[str, Any] = {}
        self._pod_security_context: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Container helpers
    # ------------------------------------------------------------------

    def with_container(
        self,
        name: str,
        image: str,
        command: list[str] | None = None,
        args: list[str] | None = None,
        working_dir: str | None = None,
        image_pull_policy: str = "IfNotPresent",
    ) -> "PodBuilder":
        container: dict[str, Any] = {
            "name": name,
            "image": image,
            "imagePullPolicy": image_pull_policy,
        }
        if command:
            container["command"] = command
        if args:
            container["args"] = args
        if working_dir:
            container["workingDir"] = working_dir
        self._containers[name] = container
        return self

    def with_env(self, container_name: str, name: str, value: str) -> "PodBuilder":
        self._containers[container_name].setdefault("env", []).append(
            {"name": name, "value": value}
        )
        return self

    def with_env_from_configmap(
        self, container_name: str, env_name: str, configmap_name: str, key: str
    ) -> "PodBuilder":
        self._containers[container_name].setdefault("env", []).append(
            {
                "name": env_name,
                "valueFrom": {"configMapKeyRef": {"name": configmap_name, "key": key}},
            }
        )
        return self

    def with_env_from_secret(
        self, container_name: str, env_name: str, secret_name: str, key: str
    ) -> "PodBuilder":
        self._containers[container_name].setdefault("env", []).append(
            {
                "name": env_name,
                "valueFrom": {"secretKeyRef": {"name": secret_name, "key": key}},
            }
        )
        return self

    def with_env_from(
        self,
        container_name: str,
        configmap_name: str | None = None,
        secret_name: str | None = None,
        prefix: str | None = None,
    ) -> "PodBuilder":
        entry: dict[str, Any] = {}
        if configmap_name:
            entry["configMapRef"] = {"name": configmap_name}
        if secret_name:
            entry["secretRef"] = {"name": secret_name}
        if prefix:
            entry["prefix"] = prefix
        self._containers[container_name].setdefault("envFrom", []).append(entry)
        return self

    def with_ports(self, container_name: str, ports: list[dict]) -> "PodBuilder":
        self._containers[container_name]["ports"] = ports
        return self

    def with_resources(
        self,
        container_name: str,
        cpu_request: str | None = None,
        memory_request: str | None = None,
        cpu_limit: str | None = None,
        memory_limit: str | None = None,
        ephemeral_storage_limit: str | None = None,
    ) -> "PodBuilder":
        requests: dict[str, str] = {}
        limits: dict[str, str] = {}
        if cpu_request:
            requests["cpu"] = cpu_request
        if memory_request:
            requests["memory"] = memory_request
        if cpu_limit:
            limits["cpu"] = cpu_limit
        if memory_limit:
            limits["memory"] = memory_limit
        if ephemeral_storage_limit:
            limits["ephemeral-storage"] = ephemeral_storage_limit
        resources: dict[str, Any] = {}
        if requests:
            resources["requests"] = requests
        if limits:
            resources["limits"] = limits
        self._containers[container_name]["resources"] = resources
        return self

    def with_volume_mount(
        self,
        container_name: str,
        name: str,
        mount_path: str,
        sub_path: str | None = None,
        read_only: bool = False,
        mount_propagation: str | None = None,
        sub_path_expr: str | None = None,
    ) -> "PodBuilder":
        mount: dict[str, Any] = {
            "name": name,
            "mountPath": mount_path,
            "readOnly": read_only,
        }
        if sub_path:
            mount["subPath"] = sub_path
        if sub_path_expr:
            mount["subPathExpr"] = sub_path_expr
        if mount_propagation:
            mount["mountPropagation"] = mount_propagation
        self._containers[container_name].setdefault("volumeMounts", []).append(mount)
        return self

    def with_liveness_probe(
        self,
        container_name: str,
        exec_command: list | None = None,
        http_get: dict | None = None,
        tcp_socket: dict | None = None,
        grpc: dict | None = None,
        initial_delay: int = 0,
        period: int = 10,
        timeout: int = 1,
        success_threshold: int = 1,
        failure_threshold: int = 3,
    ) -> "PodBuilder":
        self._containers[container_name]["livenessProbe"] = self._build_probe(
            exec_command, http_get, tcp_socket, grpc,
            initial_delay, period, timeout, success_threshold, failure_threshold,
        )
        return self

    def with_readiness_probe(
        self,
        container_name: str,
        exec_command: list | None = None,
        http_get: dict | None = None,
        tcp_socket: dict | None = None,
        grpc: dict | None = None,
        initial_delay: int = 0,
        period: int = 10,
        timeout: int = 1,
        success_threshold: int = 1,
        failure_threshold: int = 3,
    ) -> "PodBuilder":
        self._containers[container_name]["readinessProbe"] = self._build_probe(
            exec_command, http_get, tcp_socket, grpc,
            initial_delay, period, timeout, success_threshold, failure_threshold,
        )
        return self

    def with_startup_probe(
        self,
        container_name: str,
        exec_command: list | None = None,
        http_get: dict | None = None,
        tcp_socket: dict | None = None,
        grpc: dict | None = None,
        initial_delay: int = 0,
        period: int = 10,
        timeout: int = 1,
        success_threshold: int = 1,
        failure_threshold: int = 3,
    ) -> "PodBuilder":
        self._containers[container_name]["startupProbe"] = self._build_probe(
            exec_command, http_get, tcp_socket, grpc,
            initial_delay, period, timeout, success_threshold, failure_threshold,
        )
        return self

    def _build_probe(
        self,
        exec_command: list | None,
        http_get: dict | None,
        tcp_socket: dict | None,
        grpc: dict | None,
        initial_delay: int,
        period: int,
        timeout: int,
        success_threshold: int,
        failure_threshold: int,
    ) -> dict[str, Any]:
        probe: dict[str, Any] = {
            "initialDelaySeconds": initial_delay,
            "periodSeconds": period,
            "timeoutSeconds": timeout,
            "successThreshold": success_threshold,
            "failureThreshold": failure_threshold,
        }
        if exec_command:
            probe["exec"] = {"command": exec_command}
        elif http_get:
            probe["httpGet"] = http_get
        elif tcp_socket:
            probe["tcpSocket"] = tcp_socket
        elif grpc:
            probe["grpc"] = grpc
        return probe

    def with_lifecycle(
        self,
        container_name: str,
        post_start: dict | None = None,
        pre_stop: dict | None = None,
    ) -> "PodBuilder":
        lifecycle: dict[str, Any] = {}
        if post_start:
            lifecycle["postStart"] = post_start
        if pre_stop:
            lifecycle["preStop"] = pre_stop
        self._containers[container_name]["lifecycle"] = lifecycle
        return self

    def with_security_context(
        self,
        container_name: str,
        run_as_user: int | None = None,
        run_as_group: int | None = None,
        run_as_non_root: bool | None = None,
        read_only_root_fs: bool | None = None,
        allow_privilege_escalation: bool | None = None,
        privileged: bool | None = None,
        capabilities_add: list | None = None,
        capabilities_drop: list | None = None,
        proc_mount: str | None = None,
    ) -> "PodBuilder":
        ctx: dict[str, Any] = {}
        if run_as_user is not None:
            ctx["runAsUser"] = run_as_user
        if run_as_group is not None:
            ctx["runAsGroup"] = run_as_group
        if run_as_non_root is not None:
            ctx["runAsNonRoot"] = run_as_non_root
        if read_only_root_fs is not None:
            ctx["readOnlyRootFilesystem"] = read_only_root_fs
        if allow_privilege_escalation is not None:
            ctx["allowPrivilegeEscalation"] = allow_privilege_escalation
        if privileged is not None:
            ctx["privileged"] = privileged
        if proc_mount:
            ctx["procMount"] = proc_mount
        caps: dict[str, list] = {}
        if capabilities_add:
            caps["add"] = capabilities_add
        if capabilities_drop:
            caps["drop"] = capabilities_drop
        if caps:
            ctx["capabilities"] = caps
        self._containers[container_name]["securityContext"] = ctx
        return self

    def with_init_container(
        self,
        name: str,
        image: str,
        command: list[str] | None = None,
        args: list[str] | None = None,
        working_dir: str | None = None,
        image_pull_policy: str = "IfNotPresent",
    ) -> "PodBuilder":
        container: dict[str, Any] = {
            "name": name,
            "image": image,
            "imagePullPolicy": image_pull_policy,
        }
        if command:
            container["command"] = command
        if args:
            container["args"] = args
        if working_dir:
            container["workingDir"] = working_dir
        self._init_containers[name] = container
        return self

    # ------------------------------------------------------------------
    # Volume helpers
    # ------------------------------------------------------------------

    def with_volume(
        self,
        name: str,
        config_map: str | None = None,
        secret: str | None = None,
        pvc: str | None = None,
        empty_dir: dict | None = None,
        host_path: dict | None = None,
        projected: dict | None = None,
    ) -> "PodBuilder":
        vol: dict[str, Any] = {"name": name}
        if config_map:
            vol["configMap"] = {"name": config_map}
        elif secret:
            vol["secret"] = {"secretName": secret}
        elif pvc:
            vol["persistentVolumeClaim"] = {"claimName": pvc}
        elif empty_dir is not None:
            vol["emptyDir"] = empty_dir
        elif host_path:
            vol["hostPath"] = host_path
        elif projected:
            vol["projected"] = projected
        self._volumes.append(vol)
        return self

    # ------------------------------------------------------------------
    # Pod-level spec helpers
    # ------------------------------------------------------------------

    def with_node_selector(self, labels: dict) -> "PodBuilder":
        self._spec["nodeSelector"] = labels
        return self

    def with_node_name(self, name: str) -> "PodBuilder":
        self._spec["nodeName"] = name
        return self

    def with_affinity(
        self,
        node_affinity: dict | None = None,
        pod_affinity: dict | None = None,
        pod_anti_affinity: dict | None = None,
    ) -> "PodBuilder":
        affinity: dict[str, Any] = {}
        if node_affinity:
            affinity["nodeAffinity"] = node_affinity
        if pod_affinity:
            affinity["podAffinity"] = pod_affinity
        if pod_anti_affinity:
            affinity["podAntiAffinity"] = pod_anti_affinity
        self._spec["affinity"] = affinity
        return self

    def with_tolerations(self, tolerations: list[dict]) -> "PodBuilder":
        self._spec["tolerations"] = tolerations
        return self

    def with_topology_spread(self, constraints: list[dict]) -> "PodBuilder":
        self._spec["topologySpreadConstraints"] = constraints
        return self

    def with_image_pull_secrets(self, secrets: list[str]) -> "PodBuilder":
        self._spec["imagePullSecrets"] = [{"name": s} for s in secrets]
        return self

    def with_service_account(
        self, name: str, automount: bool = True
    ) -> "PodBuilder":
        self._spec["serviceAccountName"] = name
        self._spec["automountServiceAccountToken"] = automount
        return self

    def with_dns_config(
        self,
        nameservers: list | None = None,
        searches: list | None = None,
        options: list | None = None,
    ) -> "PodBuilder":
        dns: dict[str, Any] = {}
        if nameservers:
            dns["nameservers"] = nameservers
        if searches:
            dns["searches"] = searches
        if options:
            dns["options"] = options
        self._spec["dnsConfig"] = dns
        return self

    def with_dns_policy(self, policy: str) -> "PodBuilder":
        self._spec["dnsPolicy"] = policy
        return self

    def with_host_network(self, enabled: bool) -> "PodBuilder":
        self._spec["hostNetwork"] = enabled
        return self

    def with_host_pid(self, enabled: bool) -> "PodBuilder":
        self._spec["hostPID"] = enabled
        return self

    def with_host_ipc(self, enabled: bool) -> "PodBuilder":
        self._spec["hostIPC"] = enabled
        return self

    def with_hostname(
        self,
        hostname: str,
        subdomain: str | None = None,
        set_hostname_as_fqdn: bool = False,
    ) -> "PodBuilder":
        self._spec["hostname"] = hostname
        if subdomain:
            self._spec["subdomain"] = subdomain
        self._spec["setHostnameAsFQDN"] = set_hostname_as_fqdn
        return self

    def with_restart_policy(self, policy: str) -> "PodBuilder":
        self._spec["restartPolicy"] = policy
        return self

    def with_termination_grace_period(self, seconds: int) -> "PodBuilder":
        self._spec["terminationGracePeriodSeconds"] = seconds
        return self

    def with_active_deadline(self, seconds: int) -> "PodBuilder":
        self._spec["activeDeadlineSeconds"] = seconds
        return self

    def with_priority(self, priority_class_name: str) -> "PodBuilder":
        self._spec["priorityClassName"] = priority_class_name
        return self

    def with_runtime_class(self, name: str) -> "PodBuilder":
        self._spec["runtimeClassName"] = name
        return self

    def with_scheduler(self, name: str) -> "PodBuilder":
        self._spec["schedulerName"] = name
        return self

    def with_pod_security_context(
        self,
        run_as_user: int | None = None,
        run_as_group: int | None = None,
        run_as_non_root: bool | None = None,
        fs_group: int | None = None,
        fs_group_change_policy: str | None = None,
        supplemental_groups: list | None = None,
        sysctls: list | None = None,
    ) -> "PodBuilder":
        ctx: dict[str, Any] = {}
        if run_as_user is not None:
            ctx["runAsUser"] = run_as_user
        if run_as_group is not None:
            ctx["runAsGroup"] = run_as_group
        if run_as_non_root is not None:
            ctx["runAsNonRoot"] = run_as_non_root
        if fs_group is not None:
            ctx["fsGroup"] = fs_group
        if fs_group_change_policy:
            ctx["fsGroupChangePolicy"] = fs_group_change_policy
        if supplemental_groups:
            ctx["supplementalGroups"] = supplemental_groups
        if sysctls:
            ctx["sysctls"] = sysctls
        self._pod_security_context = ctx
        return self

    def with_readiness_gate(self, condition_type: str) -> "PodBuilder":
        self._spec.setdefault("readinessGates", []).append(
            {"conditionType": condition_type}
        )
        return self

    def with_scheduling_gate(self, name: str) -> "PodBuilder":
        self._spec.setdefault("schedulingGates", []).append({"name": name})
        return self

    def with_share_process_namespace(self, enabled: bool) -> "PodBuilder":
        self._spec["shareProcessNamespace"] = enabled
        return self

    def with_os(self, name: str) -> "PodBuilder":
        self._spec["os"] = {"name": name}
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> dict:
        metadata: dict[str, Any] = {
            "name": self._name,
            "namespace": self._namespace,
        }
        if self._labels:
            metadata["labels"] = self._labels
        if self._annotations:
            metadata["annotations"] = self._annotations
        if self._generate_name:
            metadata["generateName"] = self._generate_name

        spec: dict[str, Any] = dict(self._spec)
        spec["containers"] = list(self._containers.values())
        if self._init_containers:
            spec["initContainers"] = list(self._init_containers.values())
        if self._volumes:
            spec["volumes"] = self._volumes
        if self._pod_security_context:
            spec["securityContext"] = self._pod_security_context

        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": metadata,
            "spec": spec,
        }
