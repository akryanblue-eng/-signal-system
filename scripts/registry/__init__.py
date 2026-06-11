"""
registry — Registry Binding Block (RBB) package v0.1

Single-import surface for artifact identity locking and RCC enforcement.

Typical usage:
    from registry import build_registry_binding, inject_rbb, Gatekeeper
    from registry import default_registry_snapshot, default_move_set
    from sipmg import compute_vcl_hash

    vcl_hash = compute_vcl_hash()
    binding  = build_registry_binding(
        default_registry_snapshot(), default_move_set(), vcl_hash
    )
    artifact_with_rbb = inject_rbb(my_artifact_dict, binding)

    gk = Gatekeeper()
    result = gk.enforce_cssr_input(cert_list)
    if result.blocked:
        raise RuntimeError(result.violations[0].message)
"""

from registry.binding import (
    RegistryBinding,
    build_registry_binding,
    inject_rbb,
    dumps_artifact_json,
)
from registry.gatekeeper import Gatekeeper, GatekeeperResult, GatekeeperViolation
from registry.runtime import RegistrySnapshot
from registry.snapshot import default_registry_snapshot, default_move_set

__all__ = [
    "RegistryBinding",
    "build_registry_binding",
    "inject_rbb",
    "dumps_artifact_json",
    "Gatekeeper",
    "GatekeeperResult",
    "GatekeeperViolation",
    "RegistrySnapshot",
    "default_registry_snapshot",
    "default_move_set",
]
