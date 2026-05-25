# Exports: ServiceManager, IngressManager, NetworkPolicyManager,
#          EndpointsManager, EndpointSliceManager, IngressClassManager

from kube_orchestrator.resources.networking.service import ServiceManager

__all__ = ["ServiceManager"]
