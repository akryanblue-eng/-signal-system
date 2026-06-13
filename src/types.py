from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WitnessPacket304:
    run_id: str
    prev_state_bytes: bytes
    frozen_batch_bytes: bytes
    bundle_hash: bytes        # exactly 32 bytes
    bundle_version: int
    validator_pubkey: bytes   # exactly 32 bytes
    signals: list             # list of (signal_key: str, value: int)


@dataclass
class CFRFailureRecord:
    CFR_id: str
    failure_code: str
    scope: str
    outcome: str
    evidence_hash: str
    priority_rank: int


@dataclass
class Verdict:
    status: str               # "OK" or "FAIL"
    cfr: Optional[CFRFailureRecord] = None


@dataclass
class Certificate:
    certificate_id: str
    run_id: str
    replay_commit: str        # hex
    verdict_status: str
    issued_at_ns: int
