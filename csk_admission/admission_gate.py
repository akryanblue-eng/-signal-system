"""
Stage 1 — Event Admission Gate (EAG).

Goal: reject malformed or non-replayable events before they enter the system.
Order of checks matches the spec: structural validation, type registry,
topic extraction/normalization.
"""
from __future__ import annotations

import re

from .registry import is_known_type
from .topics import AMBIGUOUS, extract_topic, normalize_topic
from .types import AdmissionResult, AdmissionStatus

SCHEMA_VERSION = 1
REQUIRED_FIELDS = ("v", "id", "type", "ts", "payload")
ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _reject(reasons: list[str]) -> AdmissionResult:
    return AdmissionResult(status=AdmissionStatus.REJECTED, reasons=reasons)


def admit(event: dict, seen_ids: set[str]) -> AdmissionResult:
    """
    Run the full admission gate against one raw event envelope.
    `seen_ids` is the set of event ids already admitted in this ledger; it is
    not mutated here — the caller commits the id only after admission.
    """
    # 2.1 — structural validation (hard fail)
    missing = [f for f in REQUIRED_FIELDS if f not in event]
    if missing:
        return _reject([f"missing field(s): {missing}"])

    if event["v"] != SCHEMA_VERSION:
        return _reject([f"unknown schema version: {event['v']!r} (expected {SCHEMA_VERSION})"])

    if not isinstance(event["id"], str) or not event["id"]:
        return _reject(["id must be a non-empty string"])

    if event["id"] in seen_ids:
        return _reject([f"non-unique id: {event['id']!r}"])

    if not isinstance(event["type"], str) or not event["type"]:
        return _reject(["type must be a non-empty string"])

    if not isinstance(event["ts"], str) or not ISO8601_RE.match(event["ts"]):
        return _reject([f"invalid timestamp: {event.get('ts')!r} (expected ISO 8601 UTC)"])

    if not isinstance(event["payload"], dict):
        return _reject(["payload must be an object"])

    # 2.2 — type registry validation
    if not is_known_type(event["type"]):
        return _reject([f"unknown event type: {event['type']!r} (not in EventTypeRegistry)"])

    # 2.3 — topic extraction + normalization
    raw_topic = extract_topic(event["payload"])
    topic_key = normalize_topic(raw_topic)

    if topic_key is AMBIGUOUS:
        return _reject(["topic resolution is ambiguous: multi-topic events are rejected in v1"])
    if topic_key is None:
        return _reject(["topic resolution failed: no resolvable topic in payload"])

    # 2.4 — admission result
    return AdmissionResult(status=AdmissionStatus.ADMITTED, reasons=["admitted"], topic_key=topic_key)
