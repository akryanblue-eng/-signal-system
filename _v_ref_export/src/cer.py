"""
CER dispatch: scenario events -> ordered, typed, Merkle-committed CER chain.

Dispatch is exhaustive — any unrecognized event type raises ValueError.
The Merkle root is the final CER's merkle_hash; it is deterministic and
reproducible across machines given the same input.
"""
from __future__ import annotations

from .types import CER, GENESIS_HASH, VALID_CER_TYPES


def dispatch(scenario: dict) -> tuple[list[CER], str]:
    """
    Dispatch all events in the scenario to a CER chain.

    Returns (cer_chain, merkle_root).
    Raises ValueError for any event whose type is not in VALID_CER_TYPES.
    """
    chain: list[CER] = []
    parent_hash = GENESIS_HASH

    for seq, event in enumerate(scenario.get("events", [])):
        etype = event.get("type")
        if etype not in VALID_CER_TYPES:
            raise ValueError(
                f"CER_DISPATCH_INCOMPLETE: unrecognized event type {etype!r} "
                f"at sequence {seq} (event_id={event.get('event_id')!r}). "
                f"Valid types: {sorted(VALID_CER_TYPES)}"
            )
        cer = CER(
            event_id=event["event_id"],
            event_type=etype,
            key=event["key"],
            value=event.get("value"),
            node=event["node"],
            clock=dict(event["clock"]),
            sequence=seq,
            parent_hash=parent_hash,
        )
        chain.append(cer)
        parent_hash = cer.merkle_hash

    merkle_root = parent_hash  # GENESIS_HASH if no events
    return chain, merkle_root


def verify_chain(chain: list[CER]) -> None:
    """Verify that the CER chain is internally consistent (no gaps or reorderings)."""
    expected_parent = GENESIS_HASH
    for cer in chain:
        if cer.parent_hash != expected_parent:
            raise ValueError(
                f"CER_CHAIN_BROKEN at sequence {cer.sequence}: "
                f"expected parent={expected_parent!r}, got {cer.parent_hash!r}"
            )
        if cer.sequence != chain.index(cer):
            raise ValueError(
                f"CER_SEQUENCE_GAP: CER {cer.event_id!r} has sequence {cer.sequence} "
                f"but is at position {chain.index(cer)}"
            )
        expected_parent = cer.merkle_hash
