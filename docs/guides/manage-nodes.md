# Manage nodes

## Inspect nodes

```bash
kube-orchestrator nodes list
```

```python
from kube_orchestrator import KubeClient, NodeManager

client = KubeClient.get_instance()
nodes = NodeManager(kube_client=client)

for node in nodes.list_nodes():
    print(node.metadata.name, nodes.get_node_info(node.metadata.name))
```

## Cordon, drain and uncordon for maintenance

```bash
kube-orchestrator nodes cordon my-node
kube-orchestrator nodes drain my-node --ignore-daemonsets
# ... perform maintenance ...
kube-orchestrator nodes uncordon my-node
```

```python
nodes.cordon("my-node")
evicted = nodes.drain("my-node", ignore_daemonsets=True, force=False)
print(f"Evicted {len(evicted)} pods")
nodes.uncordon("my-node")
```

## Taints

```bash
kube-orchestrator nodes taint my-node dedicated gpu NoSchedule
kube-orchestrator nodes untaint my-node dedicated
```

```python
nodes.add_taint("my-node", key="dedicated", value="gpu", effect="NoSchedule")
nodes.remove_taint("my-node", key="dedicated")
print(nodes.has_taint("my-node", key="dedicated"))
```
