"""Data shapes frozen in docs/eiac-schema-v1.0.md.

Every class here maps directly to a named shape in that document and
exposes `to_canon()`, which returns a plain dict/list/str/int/bytes/None
structure ready for `eiac.canon.canon()`. List fields that the schema marks
"canon-sorted" are sorted here, since `canon()` itself only ever preserves
declared array order (schema §1.4.1) -- it never re-sorts.

No field here carries admissibility meaning. This module is shapes only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Union

_ID_RE = re.compile(r"^[a-zA-Z0-9._/\-]+$")


def _require_id(value: str, what: str) -> str:
    if not isinstance(value, str) or not value or not _ID_RE.match(value):
        raise ValueError(f"{what} is not a valid Id: {value!r}")
    return value


# --------------------------------------------------------------------------
# §2 Environment schema
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CapEdge:
    from_: str
    to: str
    cap: str

    def to_canon(self) -> dict:
        return {"from": self.from_, "to": self.to, "cap": self.cap}


@dataclass(frozen=True)
class CapSet:
    edges: tuple[CapEdge, ...] = ()
    schema_tag: str = "EIAC/CAPS/v1"

    def to_canon(self) -> dict:
        ordered = sorted(self.edges, key=lambda e: (e.from_, e.to, e.cap))
        return {"schema_tag": self.schema_tag, "edges": [e.to_canon() for e in ordered]}


@dataclass(frozen=True)
class Budget:
    name: str
    limit: int

    def to_canon(self) -> dict:
        if self.limit < 0:
            raise ValueError("Budget.limit must be a non-negative u64")
        return {"name": self.name, "limit": self.limit}


@dataclass(frozen=True)
class BudgetSet:
    items: tuple[Budget, ...] = ()
    schema_tag: str = "EIAC/BUDGETS/v1"

    def to_canon(self) -> dict:
        ordered = sorted(self.items, key=lambda b: b.name)
        return {"schema_tag": self.schema_tag, "items": [b.to_canon() for b in ordered]}


@dataclass(frozen=True)
class ZoneSelector:
    type: str  # "match_adapter" | "match_resource" | "match_tag"
    value: str

    def to_canon(self) -> dict:
        if self.type not in ("match_adapter", "match_resource", "match_tag"):
            raise ValueError(f"invalid ZoneSelector.type: {self.type!r}")
        return {"type": self.type, "value": self.value}


@dataclass(frozen=True)
class ZoneRule:
    zone: str
    selector: ZoneSelector

    def to_canon(self) -> dict:
        return {"zone": self.zone, "selector": self.selector.to_canon()}


@dataclass(frozen=True)
class ZoneSet:
    rules: tuple[ZoneRule, ...] = ()
    schema_tag: str = "EIAC/ZONES/v1"

    def to_canon(self) -> dict:
        ordered = sorted(self.rules, key=lambda r: (r.zone, r.selector.type, r.selector.value))
        return {"schema_tag": self.schema_tag, "rules": [r.to_canon() for r in ordered]}


@dataclass(frozen=True)
class Env:
    env_id: str
    caps: CapSet = field(default_factory=CapSet)
    budgets: BudgetSet = field(default_factory=BudgetSet)
    zones: ZoneSet = field(default_factory=ZoneSet)
    schema_tag: str = "EIAC/ENV/v1"

    def to_canon(self) -> dict:
        return {
            "schema_tag": self.schema_tag,
            "env_id": self.env_id,
            "caps": self.caps.to_canon(),
            "budgets": self.budgets.to_canon(),
            "zones": self.zones.to_canon(),
        }


# --------------------------------------------------------------------------
# §3 Execution bundle schema
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceRef:
    resource_ns: str
    resource_id: str

    def to_canon(self) -> dict:
        return {"resource_ns": self.resource_ns, "resource_id": self.resource_id}


@dataclass(frozen=True)
class Op:
    op_id: str
    adapter: str
    principal: str
    action: str
    resources: tuple[ResourceRef, ...] = ()
    params: object = None  # any canon-encodable value
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_id(self.op_id, "Op.op_id")

    def to_canon(self) -> dict:
        ordered_resources = sorted(self.resources, key=lambda r: (r.resource_ns, r.resource_id))
        return {
            "op_id": self.op_id,
            "adapter": self.adapter,
            "principal": self.principal,
            "action": self.action,
            "resources": [r.to_canon() for r in ordered_resources],
            "params": self.params,
            "tags": sorted(self.tags),
        }


@dataclass(frozen=True)
class ExecutionBundle:
    bundle_id: str
    ops: tuple[Op, ...] = ()
    schema_tag: str = "EIAC/P/v1"

    def __post_init__(self) -> None:
        op_ids = [op.op_id for op in self.ops]
        if len(set(op_ids)) != len(op_ids):
            raise ValueError("ExecutionBundle.ops contains duplicate op_id values")

    def to_canon(self) -> dict:
        ordered = sorted(self.ops, key=lambda op: op.op_id)
        return {
            "schema_tag": self.schema_tag,
            "bundle_id": self.bundle_id,
            "ops": [op.to_canon() for op in ordered],
        }


# --------------------------------------------------------------------------
# §4 Local proof
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalProof:
    adapter: str
    payload_tag: str
    payload: bytes
    schema_tag: str = "EIAC/LOCAL_PROOF/v1"

    def to_canon(self) -> dict:
        return {
            "schema_tag": self.schema_tag,
            "adapter": self.adapter,
            "payload_tag": self.payload_tag,
            "payload": self.payload,
        }


# --------------------------------------------------------------------------
# §5 Coupling witness universe (K)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BudgetWitness:
    budget: str
    observed: int
    op_ids: tuple[str, ...] = ()
    schema_tag: str = "EIAC/K/BUDGET/v1"

    def sort_key(self) -> tuple:
        return (self.schema_tag, self.budget)

    def to_canon(self) -> dict:
        if self.observed < 0:
            raise ValueError("BudgetWitness.observed must be a non-negative u64")
        return {
            "schema_tag": self.schema_tag,
            "budget": self.budget,
            "observed": self.observed,
            "op_ids": sorted(self.op_ids),
        }


@dataclass(frozen=True)
class ResourceLockWitness:
    lock_ns: str
    lock_id: str
    op_ids: tuple[str, ...] = ()
    schema_tag: str = "EIAC/K/LOCK/v1"

    def sort_key(self) -> tuple:
        return (self.schema_tag, self.lock_ns, self.lock_id)

    def to_canon(self) -> dict:
        return {
            "schema_tag": self.schema_tag,
            "lock_ns": self.lock_ns,
            "lock_id": self.lock_id,
            "op_ids": sorted(self.op_ids),
        }


@dataclass(frozen=True)
class ZoneWitness:
    zone: str
    claim: str  # "allowed" | "not_applicable"
    op_ids: tuple[str, ...] = ()
    schema_tag: str = "EIAC/K/ZONE/v1"

    def sort_key(self) -> tuple:
        return (self.schema_tag, self.zone)

    def to_canon(self) -> dict:
        if self.claim not in ("allowed", "not_applicable"):
            raise ValueError(f"invalid ZoneWitness.claim: {self.claim!r}")
        return {
            "schema_tag": self.schema_tag,
            "zone": self.zone,
            "claim": self.claim,
            "op_ids": sorted(self.op_ids),
        }


@dataclass(frozen=True)
class GovEdgeWitness:
    from_adapter: str
    to_adapter: str
    edge: str
    op_ids: tuple[str, ...] = ()
    schema_tag: str = "EIAC/K/EDGE/v1"

    def sort_key(self) -> tuple:
        return (self.schema_tag, self.from_adapter, self.to_adapter, self.edge)

    def to_canon(self) -> dict:
        return {
            "schema_tag": self.schema_tag,
            "from_adapter": self.from_adapter,
            "to_adapter": self.to_adapter,
            "edge": self.edge,
            "op_ids": sorted(self.op_ids),
        }


CouplingWitness = Union[BudgetWitness, ResourceLockWitness, ZoneWitness, GovEdgeWitness]
KNOWN_WITNESS_TAGS = {
    "EIAC/K/BUDGET/v1",
    "EIAC/K/LOCK/v1",
    "EIAC/K/ZONE/v1",
    "EIAC/K/EDGE/v1",
}


# --------------------------------------------------------------------------
# §6 Proof object schema
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GlueTrace:
    adapters: tuple[str, ...]
    op_partition: tuple[dict, ...]  # [{adapter, op_ids}]
    notes: Optional[str] = None
    schema_tag: str = "EIAC/GLUE/v1"

    def to_canon(self) -> dict:
        ordered_partition = sorted(self.op_partition, key=lambda p: p["adapter"])
        return {
            "schema_tag": self.schema_tag,
            "adapters": sorted(self.adapters),
            "op_partition": [
                {"adapter": p["adapter"], "op_ids": sorted(p["op_ids"])}
                for p in ordered_partition
            ],
            "notes": self.notes,
        }


@dataclass(frozen=True)
class Proof:
    env_hash: bytes
    bundle_hash: bytes
    local: tuple[LocalProof, ...]
    coupling: tuple[CouplingWitness, ...]
    glue: GlueTrace
    schema_tag: str = "EIAC/PROOF/v1"

    def to_canon(self) -> dict:
        ordered_local = sorted(self.local, key=lambda lp: lp.adapter)
        ordered_coupling = sorted(self.coupling, key=lambda w: w.sort_key())
        return {
            "schema_tag": self.schema_tag,
            "env_hash": self.env_hash,
            "bundle_hash": self.bundle_hash,
            "local": [lp.to_canon() for lp in ordered_local],
            "coupling": [w.to_canon() for w in ordered_coupling],
            "glue": self.glue.to_canon(),
        }
