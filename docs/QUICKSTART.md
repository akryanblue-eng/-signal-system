# VDCE Quickstart

## 1. Run verification
```bash
node vdce/cli.js verify fixtures/pass/candidate.json
```

---

## 2. Expected output (PASS)
```
VDCE RESULT: PASS
Artifacts: ./.vdce/runs/run-4846778e7a29
Certificate: ./.vdce/runs/run-4846778e7a29/certificate.json
Drift Report: none
Next Step: vdce show ./.vdce/runs/run-4846778e7a29
Exit Code: 0
```

---

## 3. Exit code model
Exit codes are a **projection of the verdict state machine**:

| Code | Verdict Type |
|------|-------------|
| 0 | certificate |
| 1 | usage_error |
| 2 | drift |
| 3 | internal_error |

---

## 4. Artifact model
Each run produces exactly one artifact directory:
- `.vdce/runs/run-<sha1[0:8]>/`

Artifact filename is derived from verdict type:

| Verdict Type | Artifact |
|-------------|----------|
| certificate | certificate.json |
| drift | drift.json |
| internal_error | internal_error.json |

---

## 5. Failure example (DRIFT)
```
VDCE RESULT: FAIL
Artifacts: ./.vdce/runs/run-3c98e772806d
Certificate: none
Drift Report: ./.vdce/runs/run-3c98e772806d/drift.json
Next Step: vdce inspect ./.vdce/runs/run-3c98e772806d
Exit Code: 2
```

---

## 6. Failure example (INTERNAL ERROR)
```
VDCE RESULT: FAIL
Artifacts: ./.vdce/runs/run-c14f534fc544
Certificate: none
Drift Report: ./.vdce/runs/run-c14f534fc544/drift.json
Next Step: vdce doctor
Exit Code: 3
```

---

## 7. Mental model
VDCE is a deterministic compiler:
```
input → evaluate → verdict → projections (stdout + exit code + artifacts)
```
No step is allowed to mutate downstream meaning.
