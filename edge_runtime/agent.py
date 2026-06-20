"""
edge_runtime CLI entrypoint — unattended wrapper around the existing CVP
transition gate run, meant to be invoked by systemd on a constrained device
(e.g. NVIDIA Jetson). Each invocation produces one witness JSON file.

Usage:
    python -m edge_runtime.agent [morphism_path]

Exit code matches the underlying `cvp_transition.validate` run, so systemd
unit status reflects gate outcome.
"""
import json
import sys
from pathlib import Path

from cvp_transition.witness import validate_witness

from .config import DEFAULT_MORPHISM_PATH, REPO_ROOT, WITNESS_OUTPUT_DIR
from .witness_runner import run_witness


def main() -> int:
    morphism_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MORPHISM_PATH

    witness, exit_code = run_witness(morphism_path, REPO_ROOT)

    schema_errors = validate_witness(witness)
    if schema_errors:
        print("[WARN] generated witness failed schema validation:", file=sys.stderr)
        for e in schema_errors:
            print(f"  - {e}", file=sys.stderr)

    WITNESS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WITNESS_OUTPUT_DIR / f"{witness['witness_id']}.json"
    out_path.write_text(json.dumps(witness, indent=2, sort_keys=True))

    print(f"witness_id: {witness['witness_id']}")
    print(f"verdict:    {witness['verdict']}")
    print(f"written:    {out_path}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
