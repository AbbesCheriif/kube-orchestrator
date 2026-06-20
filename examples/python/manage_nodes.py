"""Node management example — list, cordon, taint and drain."""
from __future__ import annotations

from kube_orchestrator.core.client import KubeClient
from kube_orchestrator.resources.cluster.node import NodeManager

client = KubeClient.get_instance()
manager = NodeManager(kube_client=client)

nodes = manager.list_nodes()
print(f"Cluster has {len(nodes)} node(s):")
for node in nodes:
    name = node.metadata.name
    ready = "Ready" if manager.is_ready(name) else "NotReady"
    schedulable = "Schedulable" if manager.is_schedulable(name) else "Cordoned"
    alloc = manager.get_allocatable(name)
    print(f"  {name}: {ready}, {schedulable}, CPU={alloc.get('cpu')}, Memory={alloc.get('memory')}")

if nodes:
    target = nodes[-1].metadata.name
    print(f"\nCordoning node '{target}'...")
    manager.cordon(target)

    print(f"Adding taint 'maintenance=true:NoSchedule' to '{target}'...")
    manager.add_taint(target, "maintenance", "true", "NoSchedule")

    print(f"Uncordoning '{target}'...")
    manager.uncordon(target)
    manager.remove_taint(target, "maintenance")
    print("Done.")
