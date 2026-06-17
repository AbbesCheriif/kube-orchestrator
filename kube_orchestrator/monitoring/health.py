from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.core.logging import get_logger

if TYPE_CHECKING:
    pass


class ClusterHealthReporter:
    def __init__(self, client: KubeClient | None = None) -> None:
        self._client = client or KubeClient.get_instance()
        self._logger = get_logger(__name__)

    def get_cluster_health(self) -> dict:
        nodes = self.check_node_health()
        control_plane = self.check_control_plane()
        score = self._compute_global_score(nodes, control_plane)
        return {
            "score": score,
            "nodes": nodes,
            "control_plane": control_plane,
            "workloads": {},
            "storage": {},
            "networking": {},
            "checked_at": datetime.utcnow().isoformat() + "Z",
        }

    def check_node_health(self) -> dict:
        try:
            nodes = self._client.core_v1.list_node()
        except Exception as exc:
            self._logger.error("node_health_check_failed", error=str(exc))
            return {"error": str(exc), "ready": 0, "not_ready": 0, "total": 0}

        ready = 0
        not_ready = 0
        details: list[dict] = []

        for node in nodes.items:
            name = node.metadata.name
            is_ready = False
            conditions = node.status.conditions or []
            for cond in conditions:
                if cond.type == "Ready" and cond.status == "True":
                    is_ready = True
                    break
            if is_ready:
                ready += 1
            else:
                not_ready += 1
            details.append({"name": name, "ready": is_ready})

        return {"total": ready + not_ready, "ready": ready, "not_ready": not_ready, "nodes": details}

    def check_control_plane(self) -> dict:
        result: dict = {"api_server": False, "scheduler": False, "controller_manager": False}
        try:
            self._client.core_v1.list_namespace(limit=1)
            result["api_server"] = True
        except Exception:
            pass

        try:
            statuses = self._client.core_v1.list_component_status()
            for cs in statuses.items:
                name = cs.metadata.name
                healthy = any(
                    c.type == "Healthy" and c.status == "True"
                    for c in (cs.conditions or [])
                )
                if "scheduler" in name:
                    result["scheduler"] = healthy
                elif "controller" in name:
                    result["controller_manager"] = healthy
        except Exception:
            pass

        return result

    def get_health_score(self, namespace: str | None = None) -> int:
        score = 100
        try:
            nodes = self.check_node_health()
            total = nodes.get("total", 0)
            not_ready = nodes.get("not_ready", 0)
            if total > 0:
                score -= int((not_ready / total) * 50)
        except Exception:
            score -= 20

        if namespace:
            try:
                crash_loops = self.detect_crash_loops(namespace)
                score -= min(len(crash_loops) * 5, 30)
                pending = self.get_pending_pods(namespace)
                score -= min(len(pending) * 2, 20)
            except Exception:
                pass

        return max(0, score)

    def get_workload_health(self, namespace: str) -> dict:
        result: dict = {
            "namespace": namespace,
            "deployments": {"total": 0, "available": 0, "degraded": 0},
            "pods": {"total": 0, "running": 0, "pending": 0, "failed": 0},
        }
        try:
            pods = self._client.core_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                result["pods"]["total"] += 1
                phase = (pod.status.phase or "Unknown").lower()
                if phase == "running":
                    result["pods"]["running"] += 1
                elif phase == "pending":
                    result["pods"]["pending"] += 1
                elif phase == "failed":
                    result["pods"]["failed"] += 1
        except Exception as exc:
            self._logger.warning("workload_health_pods_failed", namespace=namespace, error=str(exc))

        try:
            deploys = self._client.apps_v1.list_namespaced_deployment(namespace)
            for d in deploys.items:
                result["deployments"]["total"] += 1
                desired = d.spec.replicas or 1
                available = d.status.available_replicas or 0
                if available >= desired:
                    result["deployments"]["available"] += 1
                else:
                    result["deployments"]["degraded"] += 1
        except Exception as exc:
            self._logger.warning("workload_health_deploys_failed", namespace=namespace, error=str(exc))

        return result

    def analyze_readiness(self, namespace: str) -> dict:
        ready: list[str] = []
        not_ready: list[str] = []
        try:
            pods = self._client.core_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                name = pod.metadata.name
                pod_ready = False
                for cond in (pod.status.conditions or []):
                    if cond.type == "Ready" and cond.status == "True":
                        pod_ready = True
                        break
                if pod_ready:
                    ready.append(name)
                else:
                    not_ready.append(name)
        except Exception as exc:
            self._logger.error("analyze_readiness_failed", namespace=namespace, error=str(exc))

        return {"ready": ready, "not_ready": not_ready, "total": len(ready) + len(not_ready)}

    def detect_crash_loops(self, namespace: str) -> list[dict]:
        crash_loops: list[dict] = []
        try:
            pods = self._client.core_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                for cs in (pod.status.container_statuses or []):
                    if cs.restart_count and cs.restart_count >= 3:
                        reason = ""
                        last_msg = ""
                        if cs.last_state and cs.last_state.terminated:
                            reason = cs.last_state.terminated.reason or ""
                            last_msg = cs.last_state.terminated.message or ""
                        crash_loops.append(
                            {
                                "pod": pod.metadata.name,
                                "container": cs.name,
                                "restart_count": cs.restart_count,
                                "reason": reason,
                                "last_message": last_msg,
                            }
                        )
        except Exception as exc:
            self._logger.error("detect_crash_loops_failed", namespace=namespace, error=str(exc))

        return crash_loops

    def get_pending_pods(self, namespace: str) -> list[dict]:
        pending: list[dict] = []
        try:
            pods = self._client.core_v1.list_namespaced_pod(
                namespace, field_selector="status.phase=Pending"
            )
            now = datetime.utcnow()
            for pod in pods.items:
                reason = ""
                for cond in (pod.status.conditions or []):
                    if cond.type == "PodScheduled" and cond.status != "True":
                        reason = cond.reason or ""
                        break
                duration = ""
                if pod.metadata.creation_timestamp:
                    delta = now - pod.metadata.creation_timestamp.replace(tzinfo=None)
                    duration = str(delta)
                pending.append({"pod": pod.metadata.name, "reason": reason, "duration": duration})
        except Exception as exc:
            self._logger.error("get_pending_pods_failed", namespace=namespace, error=str(exc))

        return pending

    def get_failed_deployments(self, namespace: str) -> list[dict]:
        failed: list[dict] = []
        try:
            deploys = self._client.apps_v1.list_namespaced_deployment(namespace)
            for d in deploys.items:
                desired = d.spec.replicas or 1
                available = d.status.available_replicas or 0
                if available < desired:
                    failed.append(
                        {
                            "name": d.metadata.name,
                            "desired": desired,
                            "available": available,
                        }
                    )
        except Exception as exc:
            self._logger.error("get_failed_deployments_failed", namespace=namespace, error=str(exc))

        return failed

    def get_oom_killed_pods(self, namespace: str) -> list[dict]:
        oom: list[dict] = []
        try:
            pods = self._client.core_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                for cs in (pod.status.container_statuses or []):
                    terminated = None
                    if cs.state and cs.state.terminated:
                        terminated = cs.state.terminated
                    elif cs.last_state and cs.last_state.terminated:
                        terminated = cs.last_state.terminated
                    if terminated and terminated.reason == "OOMKilled":
                        oom.append({"pod": pod.metadata.name, "container": cs.name})
        except Exception as exc:
            self._logger.error("get_oom_killed_pods_failed", namespace=namespace, error=str(exc))

        return oom

    def generate_health_report(self, namespace: str | None = None, format: str = "json") -> str:
        report: dict = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "cluster": self.get_cluster_health(),
        }
        if namespace:
            report["namespace"] = namespace
            report["workloads"] = self.get_workload_health(namespace)
            report["crash_loops"] = self.detect_crash_loops(namespace)
            report["pending_pods"] = self.get_pending_pods(namespace)
            report["failed_deployments"] = self.get_failed_deployments(namespace)
            report["oom_killed"] = self.get_oom_killed_pods(namespace)
            report["health_score"] = self.get_health_score(namespace)

        if format == "json":
            return json.dumps(report, indent=2)
        elif format == "markdown":
            return self._to_markdown(report)
        return self._to_text(report)

    def _to_text(self, report: dict) -> str:
        lines = [f"Health Report — {report.get('generated_at', '')}"]
        score = report.get("cluster", {}).get("score", "N/A")
        lines.append(f"Global score : {score}/100")
        nodes = report.get("cluster", {}).get("nodes", {})
        lines.append(f"Nodes        : {nodes.get('ready', 0)}/{nodes.get('total', 0)} ready")
        return "\n".join(lines)

    def _to_markdown(self, report: dict) -> str:
        lines = [
            f"# Health Report",
            f"**Generated at**: {report.get('generated_at', '')}",
            "",
            f"## Cluster Score: {report.get('cluster', {}).get('score', 'N/A')}/100",
            "",
        ]
        nodes = report.get("cluster", {}).get("nodes", {})
        lines.append(f"### Nodes: {nodes.get('ready', 0)}/{nodes.get('total', 0)} ready")
        return "\n".join(lines)

    def _compute_global_score(self, nodes: dict, control_plane: dict) -> int:
        score = 100
        total = nodes.get("total", 0)
        not_ready = nodes.get("not_ready", 0)
        if total > 0:
            score -= int((not_ready / total) * 60)
        if not control_plane.get("api_server", True):
            score -= 30
        return max(0, score)
