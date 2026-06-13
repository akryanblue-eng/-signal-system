"""
CT-0: Certification Tier Zero

Verdict authority. Consumes RI-0 replay results, emits exactly one terminal
verdict. All-or-nothing: no certificate is issued on incomplete evidence.
"""
import hashlib
import time
import uuid

from .types import CFRFailureRecord, Certificate, Verdict


def ct0_evaluate(
    authoritative_commit: bytes,
    replay_commit: bytes,
    run_id: str,
) -> tuple[Verdict, Certificate]:
    """
    Compare authoritative and replay commits.
    Emits OK verdict on match; exactly one CFR failure record on mismatch.
    Certificate is always issued to record the outcome.
    """
    if authoritative_commit == replay_commit:
        verdict = Verdict(status="OK")
    else:
        evidence_hash = hashlib.sha256(
            authoritative_commit + replay_commit
        ).hexdigest()
        cfr = CFRFailureRecord(
            CFR_id=f"CFR-{uuid.uuid4().hex[:8].upper()}",
            failure_code="REPLAY_MISMATCH",
            scope="RI-0/CT-0",
            outcome="FAIL",
            evidence_hash=evidence_hash,
            priority_rank=1,
        )
        verdict = Verdict(status="FAIL", cfr=cfr)

    cert_payload = (
        authoritative_commit
        + replay_commit
        + verdict.status.encode("utf-8")
        + run_id.encode("utf-8")
    )
    certificate = Certificate(
        certificate_id=hashlib.sha256(cert_payload).hexdigest(),
        run_id=run_id,
        replay_commit=replay_commit.hex(),
        verdict_status=verdict.status,
        issued_at_ns=time.time_ns(),
    )

    return verdict, certificate
