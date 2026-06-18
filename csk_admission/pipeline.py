"""
EventAdmissionPipeline — wires the three stages together:

    RAW INPUT
      -> Event Admission Gate      (admission_gate.admit)
      -> Witness Contract Evaluation (witness_contracts.evaluate)
      -> Ledger Commit or Quarantine (ledger.Ledger.commit_or_quarantine)

Every ingested event carries a witnessChain in its result, recording which
validation stages it passed through — auditable provenance back to the
validation logic, not just the data.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import admission_gate, witness_contracts
from .ledger import Ledger
from .types import AdmissionStatus, Disposition, IngestResult, WitnessOutcome


class EventAdmissionPipeline:
    def __init__(self, ledger: Ledger | None = None) -> None:
        self.ledger = ledger if ledger is not None else Ledger()

    def ingest(self, event: dict) -> IngestResult:
        admission = admission_gate.admit(event, self.ledger.seen_ids)
        witness_chain = ["admission_gate:v1"]

        if admission.status != AdmissionStatus.ADMITTED:
            return IngestResult(
                event_id=event.get("id", "?"),
                admission=admission,
                witness=None,
                disposition=Disposition.REJECTED,
                drift_event=None,
                witness_chain=witness_chain,
            )

        topic_key = admission.topic_key
        assert topic_key is not None  # admission_gate guarantees this for ADMITTED status

        witness_chain.append(f"witness_contract:{event['type']}:v1")
        outcome: WitnessOutcome = witness_contracts.evaluate(event, topic_key, self.ledger.state)

        disposition, drift_event = self.ledger.commit_or_quarantine(event, topic_key, outcome)
        witness_chain.append(
            "ledger_commit:v1" if disposition == Disposition.COMMITTED else "ledger_quarantine:v1"
        )

        return IngestResult(
            event_id=event["id"],
            admission=admission,
            witness=outcome,
            disposition=disposition,
            drift_event=drift_event,
            witness_chain=witness_chain,
        )

    def persist(self, base_dir: Path) -> None:
        """Write committed and quarantined events to ledger/events.jsonl and quarantine/events.jsonl."""
        ledger_dir = base_dir / "ledger"
        quarantine_dir = base_dir / "quarantine"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        with (ledger_dir / "events.jsonl").open("w") as f:
            for event in self.ledger.events:
                f.write(json.dumps(event, sort_keys=True) + "\n")

        with (quarantine_dir / "events.jsonl").open("w") as f:
            for event in self.ledger.quarantine:
                f.write(json.dumps(event, sort_keys=True) + "\n")
