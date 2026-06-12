"""
Evidence Gate runner.
Executes Input Trace → RI-0 Replay → CT-0 Verdict → Certificate chain.
"""
import hashlib
import pathlib
import sys

from .types import WitnessPacket304
from .ri0 import ri0_replay
from .ct0 import ct0_evaluate


def build_synthetic_trace() -> WitnessPacket304:
    return WitnessPacket304(
        run_id="TRACE-V05-0001",
        prev_state_bytes=bytes(64),
        frozen_batch_bytes=bytes([0xAB, 0xCD, 0xEF] * 16),
        bundle_hash=hashlib.sha256(b"simulation-os-bundle-v0.5").digest(),
        bundle_version=5,
        validator_pubkey=hashlib.sha256(b"validator-pubkey-ri0-ct0").digest(),
        signals=[
            ("signal.alpha", 1),
            ("signal.beta", 2),
            ("signal.gamma", 3),
            ("signal.alpha", 99),  # duplicate — deduped to 99 by canonical encoding
        ],
    )


def _build_id() -> str:
    src = pathlib.Path(__file__).parent
    h = hashlib.sha256()
    for f in sorted(src.glob("*.py")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16].upper()


def run_evidence_gate() -> dict:
    packet = build_synthetic_trace()
    build_id = _build_id()

    trace_id = hashlib.sha256(
        packet.run_id.encode("utf-8") + packet.bundle_hash
    ).hexdigest()[:16].upper()

    # RI-0: two independent replays must produce identical output
    authoritative_commit = ri0_replay(packet)
    replay_commit = ri0_replay(packet)

    # Determinism self-check (fail-closed: halt if non-deterministic)
    if authoritative_commit != replay_commit:
        print("FATAL: RI-0 non-determinism detected", file=sys.stderr)
        sys.exit(1)

    verdict, certificate = ct0_evaluate(
        authoritative_commit=authoritative_commit,
        replay_commit=replay_commit,
        run_id=packet.run_id,
    )

    result = {
        "run_id": packet.run_id,
        "build_id": build_id,
        "trace_id": trace_id,
        "ri0_replay_result": replay_commit.hex(),
        "ct0_verdict": verdict.status,
        "certificate_id": certificate.certificate_id,
    }

    print(f"run_id:      {result['run_id']}")
    print(f"build_id:    {result['build_id']}")
    print(f"trace_id:    {result['trace_id']}")
    print(f"commit:      {result['ri0_replay_result']}")
    print(f"certificate: {result['certificate_id']}")
    print(f"verdict:     {result['ct0_verdict']}")

    return result


if __name__ == "__main__":
    run_evidence_gate()
