"""
Local dev tool — NOT run in CI.

Regenerates golden vectors from the current oracle implementation.
Run this when the CER hash function or oracle semantics change.
The output files become the new non-regression boundary; diff them in the PR.

Usage:
    python tools/generate_golden.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = ROOT / "tests" / "scenarios"
GOLDEN_DIR = ROOT / "tests" / "golden"

sys.path.insert(0, str(ROOT))

from src.cer import dispatch  # noqa: E402
from src.oracle import interpret  # noqa: E402


GENERATED_AT = "2026-06-16"


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for scenario_path in sorted(SCENARIOS_DIR.glob("*.json")):
        scenario = json.loads(scenario_path.read_bytes())
        chain, merkle_root = dispatch(scenario)
        output = interpret(scenario)
        golden = {
            "scenario_id": scenario["scenario_id"],
            "oracle_output_type": type(output).__name__,
            "merkle_root": merkle_root,
            "cer_count": len(chain),
            "generated_at": GENERATED_AT,
        }
        out_path = GOLDEN_DIR / f"{scenario['scenario_id']}.golden.json"
        out_path.write_text(json.dumps(golden, indent=2) + "\n", encoding="utf-8")
        print(f"  {out_path.name}: {type(output).__name__}, root={merkle_root[:16]}...")

    print(f"\n{len(list(SCENARIOS_DIR.glob('*.json')))} golden vectors written to {GOLDEN_DIR}")
    print("Review the diff before committing — these become the schema lock boundary.")


if __name__ == "__main__":
    main()
