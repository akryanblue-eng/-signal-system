"""
Core types for the CSK Event Admission Layer + Witness Contract Pipeline.

Pipeline: RAW INPUT -> Event Admission Gate -> Witness Contract Evaluation
          -> Ledger Commit or Quarantine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"  # reserved for future admission-stage holds; v1 admission never assigns this


class WitnessResult(str, Enum):
    VALID = "VALID"
    CONTRADICTION = "CONTRADICTION"
    AMBIGUOUS = "AMBIGUOUS"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class Disposition(str, Enum):
    COMMITTED = "COMMITTED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"


@dataclass
class AdmissionResult:
    status: AdmissionStatus
    reasons: list[str] = field(default_factory=list)
    topic_key: str | None = None


@dataclass
class WitnessOutcome:
    result: WitnessResult
    reasons: list[str] = field(default_factory=list)
    affected_topics: list[str] = field(default_factory=list)


@dataclass
class DriftEvent:
    type: str
    topic_key: str | None
    severity: str
    source_event_ids: list[str]

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "topicKey": self.topic_key,
            "severity": self.severity,
            "sourceEventIds": self.source_event_ids,
        }


@dataclass
class IngestResult:
    event_id: str
    admission: AdmissionResult
    witness: WitnessOutcome | None
    disposition: Disposition
    drift_event: DriftEvent | None
    witness_chain: list[str]
