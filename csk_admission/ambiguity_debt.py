"""
Ambiguity debt gate — turns divergence.analyze() into a CI ratchet.

Debt is *not* the same as the hotspot count. A hotspot with at least one
collapse anchor (csk_admission.divergence.AmbiguityHotspot.collapse_anchors)
is normal operational backlog: something just needs to submit an
event.disambiguated naming one of the already-viable candidates. That is
expected, recoverable, and not debt.

Debt is a hotspot with *zero* collapse anchors: every candidate visible in
current history would itself resolve to CONTRADICTION (or there are no
candidates at all). No event.disambiguated submission can rescue it without
new information entering the system. That is a structural gap, and it is
the only thing this gate ratchets on.

Usage:
    python -m csk_admission.ambiguity_debt <ledger_base_dir>                 # check
    python -m csk_admission.ambiguity_debt <ledger_base_dir> --write-baseline # accept current debt

<ledger_base_dir> is the directory passed to EventAdmissionPipeline.persist()
(must contain ledger/events.jsonl and quarantine/events.jsonl).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .divergence import DivergenceReport, analyze
from .ledger import Ledger, replay

BASELINE_PATH = Path(__file__).parent / "ambiguity_debt_baseline.json"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_ledger(base_dir: Path) -> Ledger:
    """Reconstruct a Ledger from the on-disk layout written by EventAdmissionPipeline.persist()."""
    committed = _read_jsonl(base_dir / "ledger" / "events.jsonl")
    quarantined = _read_jsonl(base_dir / "quarantine" / "events.jsonl")
    ledger = Ledger()
    ledger.state = replay(committed)
    ledger.quarantine = {event["id"]: event for event in quarantined}
    return ledger


def debt_from_report(report: DivergenceReport) -> dict:
    stuck = [h for h in report.hotspots if not h.collapse_anchors]
    return {
        "total_hotspots": len(report.hotspots),
        "stuck_hotspots": len(stuck),
        "stuck_event_ids": sorted(h.event_id for h in stuck),
    }


def compute_debt(ledger: Ledger) -> dict:
    return debt_from_report(analyze(ledger))


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {"stuck_hotspots": 0}
    return json.loads(BASELINE_PATH.read_text())


def check(base_dir: Path, baseline: dict | None = None) -> tuple[bool, dict]:
    """Returns (passed, current_debt). Fails only if stuck_hotspots increased over baseline."""
    current = compute_debt(load_ledger(base_dir))
    baseline = baseline if baseline is not None else _load_baseline()
    passed = current["stuck_hotspots"] <= baseline["stuck_hotspots"]
    return passed, current


def main(argv: list[str]) -> int:
    if not argv:
        print(f"usage: python -m {__name__} <ledger_base_dir> [--write-baseline]", file=sys.stderr)
        return 2

    base_dir = Path(argv[0])
    write_baseline = "--write-baseline" in argv[1:]
    current = compute_debt(load_ledger(base_dir))

    if write_baseline:
        BASELINE_PATH.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"baseline written: stuck_hotspots={current['stuck_hotspots']}")
        return 0

    baseline = _load_baseline()
    print(f"stuck_hotspots: baseline={baseline['stuck_hotspots']} current={current['stuck_hotspots']}")
    if current["stuck_hotspots"] > baseline["stuck_hotspots"]:
        print(
            f"FAIL: ambiguity debt increased ({baseline['stuck_hotspots']} -> {current['stuck_hotspots']})",
            file=sys.stderr,
        )
        print(f"new stuck events: {current['stuck_event_ids']}", file=sys.stderr)
        return 1

    print("PASS: ambiguity debt did not increase")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
