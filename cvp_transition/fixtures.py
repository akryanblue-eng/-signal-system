"""
E₁.₂ canonical fixture pack — content-addressed regression corpus.
Verifies that live execution still matches the frozen fixture hashes.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent.parent / "e12_fixtures"
MANIFEST = FIXTURE_DIR / "e12_manifest.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_fixture_pack(repo_root: Path, schema_changed: bool = False) -> tuple[bool, str]:
    """
    Regenerate live outputs, hash them, compare against e12_manifest.json.
    Returns (passed, message).
    """
    if not MANIFEST.exists():
        return False, f"manifest not found: {MANIFEST}"

    manifest = json.loads(MANIFEST.read_text())

    errors: list[str] = []
    baseline = manifest.get("_meta", {})
    expected_commit = baseline.get("baseline_commit", "")
    expected_cert   = baseline.get("baseline_certificate", "")

    def _check_stdout(label: str, stdout: str) -> None:
        if schema_changed:
            # Semantic check: canonical fields must match baseline; extra fields allowed.
            import re
            def extract(text: str, field: str) -> str:
                m = re.search(rf"^{field}:\s+(\S+)", text, re.MULTILINE)
                return m.group(1) if m else ""
            got_commit = extract(stdout, "commit")
            got_cert   = extract(stdout, "certificate")
            if got_commit != expected_commit:
                errors.append(
                    f"{label}: commit mismatch\n"
                    f"  expected: {expected_commit}\n"
                    f"  observed: {got_commit}"
                )
            if got_cert != expected_cert:
                errors.append(
                    f"{label}: certificate mismatch\n"
                    f"  expected: {expected_cert}\n"
                    f"  observed: {got_cert}"
                )
        else:
            # Byte-exact check: full stdout hash must match manifest.
            h = _sha256(stdout.encode())
            expected = manifest.get(f"{label}.txt", {}).get("sha256", "")
            if h != expected:
                errors.append(
                    f"{label} hash mismatch\n"
                    f"  expected: {expected}\n"
                    f"  observed: {h}"
                )

    # Regenerate impl_a output
    r = subprocess.run(
        [sys.executable, "-u", "-m", "src.evidence_gate"],
        cwd=repo_root, capture_output=True, text=True,
    )
    if r.returncode != 0:
        return False, f"impl_a execution failed\n{r.stderr}"
    _check_stdout("impl_a_stdout", r.stdout)

    # Regenerate impl_b output
    r2 = subprocess.run(
        ["go", "run", "main.go"],
        cwd=repo_root / "impl_b", capture_output=True, text=True,
    )
    if r2.returncode != 0:
        return False, f"impl_b execution failed\n{r2.stderr}"
    _check_stdout("impl_b_stdout", r2.stdout)

    # invariants.json is always byte-exact (not a runtime output)
    invariants_path = repo_root / "cvp_drift_injector" / "fixtures" / "invariants.json"
    inv_hash = _sha256(invariants_path.read_bytes())
    expected_inv = manifest.get("invariants.json", {}).get("sha256", "")
    if inv_hash != expected_inv:
        errors.append(
            f"invariants.json hash mismatch\n"
            f"  expected: {expected_inv}\n"
            f"  observed: {inv_hash}"
        )

    if errors:
        return False, "fixture pack FAIL:\n" + "\n".join(errors)
    mode = "semantic" if schema_changed else "byte-exact"
    return True, f"fixture pack PASS ({mode}, canonical fields match baseline)"
