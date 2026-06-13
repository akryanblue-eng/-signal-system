# VDCE Quickstart

## 1. Run verification
```bash
node vdce/cli.js verify fixtures/pass/candidate.json
```

## 2. Expected output (PASS)
```
VDCE RESULT: PASS
Artifacts: ./.vdce/runs/run-836fa1b9
Certificate: ./.vdce/runs/run-836fa1b9/certificate.json
Drift Report: none
Next Step: vdce show ./.vdce/runs/run-836fa1b9
Exit Code: 0
```

## 3. Exit codes
| Code | Meaning |
|------|---------|
| 0 | PASS — certificate issued |
| 1 | USAGE ERROR — bad invocation |
| 2 | DRIFT — deterministic mismatch |
| 3 | INTERNAL ERROR — evaluation threw |

## 4. Artifact layout
Every run writes to `.vdce/runs/<run-id>/`, which contains exactly one of:

| Verdict | File written |
|---------|-------------|
| PASS | `certificate.json` |
| DRIFT / INTERNAL ERROR / USAGE ERROR | `drift.json` |

Run IDs are derived from `sha1(candidatePath)[0:8]`, making them deterministic per input and collision-free across parallel CI jobs.

## 5. Failure example — DRIFT
```
VDCE RESULT: FAIL
Artifacts: ./.vdce/runs/run-07528fdc
Certificate: none
Drift Report: ./.vdce/runs/run-07528fdc/drift.json
Next Step: vdce inspect ./.vdce/runs/run-07528fdc
Exit Code: 2
```

## 6. Failure example — INTERNAL ERROR
```
VDCE RESULT: FAIL
Artifacts: ./.vdce/runs/run-01b9d268
Certificate: none
Drift Report: ./.vdce/runs/run-01b9d268/drift.json
Next Step: vdce doctor
Exit Code: 3
```

## 7. Validate artifacts
```bash
node scripts/validate-artifacts.js
```

Checks every run directory for:
- exactly one artifact file (certificate.json XOR drift.json)
- all required schema fields with correct types
- no unexpected keys
- `runId` value matches directory name
- drift artifacts carry a non-empty `error` string

## 8. Mental model

```
candidate.json → evaluate() → verdict → ABI stdout + artifact
                               │
                  ┌────────────┼────────────┐
                  │            │            │
             certificate    drift.json   drift.json
               .json       (type=drift) (type=internal_error)
```

VDCE is a deterministic pipeline: the same input always produces the same stdout, the same exit code, and the same artifact shape. The golden files in `goldens/` are the locked ABI contract.
