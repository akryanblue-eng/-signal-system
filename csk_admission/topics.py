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
    payload declares more than one topic candidate.

    Only `payload["topic"]` is a topic source. Fields like `loop_id` and
    `supersedes` are witness-layer anchors (Stage 2 concern), not topic
    identity (Stage 1 concern) — conflating the two was what made the old
    AMBIGUOUS witness result unreachable.
    """
    if "topics" in payload:
        # Plural form is an explicit multi-topic declaration -> always ambiguous.
        return AMBIGUOUS

    topic = payload.get("topic")
    return topic if topic else None


def normalize_topic(raw: str | None | object) -> str | None | object:
    if raw is AMBIGUOUS or raw is None:
        return raw
    if not isinstance(raw, str):
        return AMBIGUOUS
    normalized = " ".join(raw.strip().lower().split())
    return normalized or None
