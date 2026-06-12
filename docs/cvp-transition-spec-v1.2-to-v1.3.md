# CVP Transition Spec: v1.2 → v1.3

**Status:** Normative Draft  
**Scope:** Defines what constitutes a valid version transition from CVP-v1.2 to any CVP-v1.3 kernel. A v1.3 kernel that does not satisfy all constraints in this document is not a valid v1.3 — it is a new, incompatible kernel and must be versioned accordingly.

---

## 1. Reference Oracle

CVP-v1.2 is the frozen reference oracle for all compatibility checks.

The v1.2 oracle consists of exactly these artifacts, pinned by commit hash:

| Artifact | Path | Role |
|---|---|---|
| Kernel spec | `docs/simulation-os-kernel-reference-v0.5.md` | Normative vocabulary |
| RI-0 implementation | `src/ri0.py` | Reference replay engine |
| CT-0 implementation | `src/ct0.py` | Reference verdict harness |
| CVL1 extractor | `src/cvl1.py` | Canonical line extraction rules |
| Drift engine | `cvp_drift_injector/` | Adversarial test substrate |
| Baseline fixture | `cvp_drift_injector/fixtures/invariants.json` | Locked hash values |
| Portability contract | `verify.py` | Cross-runtime check |

The oracle commit is: `4b7dbeb` (branch `claude/simulation-os-v0.5-kernel-ref-inrlk7`).

Any v1.3 implementation MUST retain a reference to this commit in its compatibility declaration.

---

## 2. Compatibility Classes

Every change from v1.2 to v1.3 falls into exactly one class:

| Class | Definition | CI requirement |
|---|---|---|
| **Compatible extension** | New behavior added; all v1.2 inputs produce identical outputs | Regression suite MUST pass with zero changes |
| **Compatible relaxation** | Accepts inputs v1.2 rejected; v1.2-valid inputs still produce identical outputs | Regression suite MUST pass; new acceptance test added |
| **Breaking change** | Any v1.2-valid input produces a different output or verdict | Not permitted within v1.3; requires a new kernel version |
| **Incompatible extension** | New output fields added that v1.2 did not emit | Permitted only if v1.2 fields are byte-identical; new fields are additive only |

A change is **breaking** if any of the following are true:
- The `commit` field value changes for any v1.2 input
- The `certificate` field value changes for any v1.2 input
- The `verdict` field changes from OK to FAIL or FAIL to OK for any v1.2 input
- CVL1 extraction rules change such that a previously extractable field becomes non-extractable

---

## 3. What May Change in v1.3

### 3.1 CVL1 Extraction Rules

| Change | Permitted |
|---|---|
| Accept additional field names | ✅ Compatible extension |
| Change field name syntax | ❌ Breaking |
| Change value validation regex for `commit` or `certificate` | ❌ Breaking |
| Add new validated fields | ✅ Compatible extension |
| Change first-occurrence-wins to last-occurrence-wins | ❌ Breaking |
| Change CRLF handling | ❌ Breaking |

### 3.2 Drift Engine Behavior

| Change | Permitted |
|---|---|
| Add new drift injector modules | ✅ Compatible extension |
| Change `derive_seed` hash function | ❌ Breaking (reproducibility lost) |
| Change `DriftConfig` field names or defaults | ❌ Breaking |
| Add new `DriftConfig` fields with `default=False` | ✅ Compatible extension |
| Change behavior of existing injectors | ❌ Breaking |

### 3.3 Artifact Schema

| Change | Permitted |
|---|---|
| Add new output fields to evidence gate | ✅ Compatible extension (additive only) |
| Remove existing output fields | ❌ Breaking |
| Change `run_id` or `build_id` computation | ❌ Breaking |
| Change `commit` or `certificate` preimage | ❌ Breaking |

### 3.4 Verifier Output Contract

| Change | Permitted |
|---|---|
| Add new exit codes (beyond 0 and 1) | ✅ Compatible extension |
| Change meaning of exit code 0 | ❌ Breaking |
| Change meaning of exit code 1 | ❌ Breaking |
| Add structured output alongside existing output | ✅ Compatible extension |

---

## 4. Regression Validation Requirement

Any v1.3 candidate MUST pass the v1.2 regression suite before being declared valid.

The regression suite consists of:

1. **Baseline hash check**: run `python verify.py` against the v1.2 locked baseline values. Exit code MUST be 0.
2. **Cross-impl check**: run both `python -m src.evidence_gate` and `cd impl_b && go run main.go`. Both `commit` and `certificate` fields MUST be byte-identical to the v1.2 baseline.
3. **Drift immunity**: run `python -m src.immunity_test`. `stability_score` MUST equal `1.000`.
4. **Test suite**: run `python -m pytest cvp_drift_injector/tests/`. All tests MUST pass.

These four checks are the machine-checkable definition of "v1.2 compatibility." A v1.3 candidate that fails any of them is not compatible, regardless of any other claimed property.

---

## 5. Breaking Change Protocol

If a proposed change is breaking (Section 2), the following applies:

1. The change MUST NOT be versioned as v1.3.
2. The change MUST be versioned as a new kernel (e.g., v2.0) with a new oracle commit.
3. A new transition spec MUST be written for that kernel before any implementation begins.
4. The v1.2 oracle remains frozen and is never modified retroactively.

There is no "patch" path for breaking changes. The kernel is replaced, not amended.

---

## 6. Compatibility Declaration

A valid v1.3 implementation MUST include a file `CVP_COMPAT.json` at the repository root with the following structure:

```json
{
  "kernel_version": "1.3",
  "base_oracle_commit": "4b7dbeb",
  "transition_spec": "docs/cvp-transition-spec-v1.2-to-v1.3.md",
  "regression_results": {
    "baseline_hash_check": "PASS",
    "cross_impl_check": "PASS",
    "drift_immunity": "PASS",
    "test_suite": "PASS"
  },
  "witness_environment": "<OS/runtime/commit where regression suite was executed>"
}
```

This file is the machine-readable proof that the transition is valid. It MUST be committed before the v1.3 kernel is declared complete.

---

## 7. What This Spec Does Not Define

This spec defines transition validity, not v1.3 semantics. The following are explicitly out of scope:

- What new capabilities v1.3 adds
- What problems v1.3 solves that v1.2 does not
- Internal implementation choices in v1.3
- Performance or resource characteristics

Those are defined by the v1.3 kernel spec, which is a separate document written after this transition spec is satisfied.

---

## Sources

- CVP-v1.2 kernel: commit `4b7dbeb`, branch `claude/simulation-os-v0.5-kernel-ref-inrlk7`
- Simulation OS Kernel Reference v0.5: `docs/simulation-os-kernel-reference-v0.5.md`
