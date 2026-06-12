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


def verify_fixture_pack(repo_root: Path) -> tuple[bool, str]:
    """
    Regenerate live outputs, hash them, compare against e12_manifest.json.
    Returns (passed, message).
    """
    if not MANIFEST.exists():
        return False, f"manifest not found: {MANIFEST}"

    manifest = json.loads(MANIFEST.read_text())

    errors: list[str] = []

    # Regenerate impl_a output
    r = subprocess.run(
        [sys.executable, "-u", "-m", "src.evidence_gate"],
        cwd=repo_root, capture_output=True, text=True,
    )
    if r.returncode != 0:
        return False, f"impl_a execution failed\n{r.stderr}"
    impl_a_hash = _sha256(r.stdout.encode())
    expected_a = manifest.get("impl_a_stdout.txt", {}).get("sha256", "")
    if impl_a_hash != expected_a:
        errors.append(
            f"impl_a_stdout.txt hash mismatch\n"
            f"  expected: {expected_a}\n"
            f"  observed: {impl_a_hash}"
        )

    # Regenerate impl_b output
    r2 = subprocess.run(
        ["go", "run", "main.go"],
        cwd=repo_root / "impl_b", capture_output=True, text=True,
    )
    if r2.returncode != 0:
        return False, f"impl_b execution failed\n{r2.stderr}"
    impl_b_hash = _sha256(r2.stdout.encode())
    expected_b = manifest.get("impl_b_stdout.txt", {}).get("sha256", "")
    if impl_b_hash != expected_b:
        errors.append(
            f"impl_b_stdout.txt hash mismatch\n"
            f"  expected: {expected_b}\n"
            f"  observed: {impl_b_hash}"
        )

    # Verify invariants.json is unchanged
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
    return True, "fixture pack PASS (all 3 fixtures match manifest)"
