from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal


# ── Epistemic output types ───────────────────────────────────────────────────

@dataclass
class ForkCertificate:
    scenario_id: str
    fork_axis: str
    conflicting_writes: list[dict]
    certificate_hash: str = field(init=False)

    def __post_init__(self) -> None:
        payload = json.dumps(self.conflicting_writes, sort_keys=True).encode()
        self.certificate_hash = hashlib.sha256(payload).hexdigest()


@dataclass
class HealingTranscript:
    scenario_id: str
    pre_state: dict
    post_state: dict
    healing_steps: list[str]
    convergent: bool


@dataclass
class CannotExpress:
    scenario_id: str
    reason: str
    partial_observations: list[dict]


VRefOutput = ForkCertificate | HealingTranscript | CannotExpress


# ── Canonical Event Record ───────────────────────────────────────────────────

GENESIS_HASH = "0" * 64
VALID_CER_TYPES: frozenset[str] = frozenset({"write", "read", "delete"})


@dataclass(frozen=True)
class CER:
    """
    Canonical, typed, ordered, Merkle-committed event record.

    merkle_hash = sha256(json of all fields except merkle_hash, sort_keys=True)
    The hash chain is: CER[n].parent_hash == CER[n-1].merkle_hash
    CER[0].parent_hash == GENESIS_HASH
    """
    event_id: str
    event_type: Literal["write", "read", "delete"]
    key: str
    value: Any
    node: str
    clock: dict[str, int]
    sequence: int
    parent_hash: str
    merkle_hash: str = field(init=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        payload = {
            "clock": self.clock,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "key": self.key,
            "node": self.node,
            "parent_hash": self.parent_hash,
            "sequence": self.sequence,
            "value": self.value,
        }
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        object.__setattr__(self, "merkle_hash", h)
