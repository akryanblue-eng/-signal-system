"""
Topic extraction + normalization.

topicKey = normalize_topic(extract_topic(payload))

Rules (per Event Admission Gate spec, stage 1.3):
  - must resolve to a deterministic string
  - must not be null
  - must not be ambiguous (multi-topic events rejected in v1)
"""
from __future__ import annotations

AMBIGUOUS = object()  # sentinel: payload declares more than one topic candidate


def extract_topic(payload: dict) -> str | None | object:
    """
    Returns the raw topic candidate, None if absent, or AMBIGUOUS if the
    payload declares more than one topic-bearing field.
    """
    if "topics" in payload:
        # Plural form is an explicit multi-topic declaration -> always ambiguous.
        return AMBIGUOUS

    candidates = [
        payload[key] for key in ("topic", "loop_id") if payload.get(key)
    ]
    if len(candidates) > 1:
        return AMBIGUOUS
    if not candidates:
        return None
    return candidates[0]


def normalize_topic(raw: str | None | object) -> str | None | object:
    if raw is AMBIGUOUS or raw is None:
        return raw
    if not isinstance(raw, str):
        return AMBIGUOUS
    normalized = " ".join(raw.strip().lower().split())
    return normalized or None
