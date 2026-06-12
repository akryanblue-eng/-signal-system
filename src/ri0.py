"""
RI-0: Reference Interpreter Zero

Deterministic replay engine. Given identical inputs, produces byte-for-byte
identical CommitHash32. No floating point, no non-deterministic operations.
"""
import hashlib
import struct

from .types import WitnessPacket304


def _encode_signals(signals: list) -> bytes:
    """
    Canonical signal encoding:
    - Dedup by signal_key, keeping last value (stable over identical input ordering)
    - Sort by signal_key lexicographically (canonical ordering)
    - Encode each as: uint16(key_len) || key_utf8 || int64(value) big-endian
    """
    deduped: dict[str, int] = {}
    for key, value in signals:
        deduped[key] = value
    parts = []
    for key in sorted(deduped):
        key_bytes = key.encode("utf-8")
        parts.append(struct.pack(">H", len(key_bytes)))
        parts.append(key_bytes)
        parts.append(struct.pack(">q", deduped[key]))
    return b"".join(parts)


def ri0_replay(packet: WitnessPacket304) -> bytes:
    """
    Canonical replay of a WitnessPacket304. Returns 32-byte CommitHash.
    Fields encoded in fixed order; lengths length-prefixed; no implicit padding.
    """
    if len(packet.bundle_hash) != 32:
        raise ValueError("bundle_hash must be exactly 32 bytes")
    if len(packet.validator_pubkey) != 32:
        raise ValueError("validator_pubkey must be exactly 32 bytes")

    h = hashlib.sha256()

    run_id_b = packet.run_id.encode("utf-8")
    h.update(struct.pack(">H", len(run_id_b)))
    h.update(run_id_b)

    h.update(struct.pack(">I", len(packet.prev_state_bytes)))
    h.update(packet.prev_state_bytes)

    h.update(struct.pack(">I", len(packet.frozen_batch_bytes)))
    h.update(packet.frozen_batch_bytes)

    h.update(packet.bundle_hash)                          # fixed 32 bytes
    h.update(struct.pack(">I", packet.bundle_version))    # uint32 big-endian

    h.update(packet.validator_pubkey)                     # fixed 32 bytes

    signal_b = _encode_signals(packet.signals)
    h.update(struct.pack(">I", len(signal_b)))
    h.update(signal_b)

    return h.digest()  # 32 bytes = CommitHash32
