# Jetson Edge Runtime — Core / Edge Split

**Status:** Draft

## What this repo already is

`signal-system` is a deterministic CVP (gate/witness/drift-injection)
verification system:

- `src/` — RI-0 (deterministic replay) → CT-0 (verdict authority) →
  Certificate evidence chain. Pure `hashlib`/`struct`, no floats, no native
  extensions.
- `src/cvl1.py`, `src/drift.py`, `src/immunity_test.py` — canonical field
  extraction and adversarial-perturbation stability testing.
- `cvp_transition/` — the CI-facing CLI (`python -m cvp_transition
  <morphism.json>`) running four gates (frozen oracle, outcome
  preservation, determinism, witness obligation) plus a fixture-pack
  check, then emitting `CVP_COMPAT.json`.
- `verify.py` — the "Phase 1 Portability Run Contract." It is explicitly
  designed to be re-run on different machines and gates only on
  `commit`/`certificate` hash equality — OS/arch/Python version are
  recorded, never gated on.
- `cvp_transition/witness.py` — Gate 4 requires ≥2 independent admissible
  witnesses. Independence is decided by an environment fingerprint
  (`os` + `architecture` + `python_version`); different machine classes are
  automatically independent (`are_independent`, Rule 4).
- `impl_b/` — an independent Go implementation of the same RI-0/CT-0 chain,
  compared against `src/` in CI on `ubuntu-22.04` (x86_64 only today).

**Key implication:** the core gate logic has no GPU dependency and no
architecture-specific code. It is already portable to ARM64 — nothing in
`src/` or `cvp_transition/` needs to change to run on a Jetson. A Jetson
device's GPU is irrelevant to this workload; the gate suite is CPU-bound
hashing and string parsing, not inference.

## The split

| Layer | Contents | Changes for Jetson |
|---|---|---|
| **Core** | `src/`, `cvp_transition/`, `cvp_drift_injector/`, `invariants/`, `impl_b/` | None. Same Python 3.11 / Go 1.24 interpreters run unmodified on ARM64. |
| **Edge runtime** | `edge_runtime/` (new) | New — packages a gate run into a Gate 4 witness and wires it into systemd. |

`edge_runtime/` does not reimplement or wrap gate logic. It runs the
existing `python -m cvp_transition <morphism>` CLI as a subprocess,
captures stdout/exit code, and assembles a schema-valid witness record
(`cvp_transition/witness.py`'s `REQUIRED_WITNESS_FIELDS` envelope) from the
result:

- `edge_runtime/witness_runner.py` — runs the CLI, parses `[PASS]`/`[FAIL]`
  gate lines from its output, hashes the emitted `CVP_COMPAT.json` and the
  captured log, and builds the witness dict. Uses
  `compute_candidate_digest()` from `cvp_transition/witness.py` directly —
  no digest logic is duplicated.
- `edge_runtime/agent.py` — CLI entrypoint (`python -m edge_runtime.agent
  [morphism_path]`). Writes one witness JSON file per run to
  `SIGNAL_SYSTEM_WITNESS_DIR` (default `/var/lib/signal-system/witnesses`)
  and exits with the underlying gate's exit code.
- `edge_runtime/systemd/signal-system-witness.{service,timer}` — runs the
  agent on boot and hourly thereafter, with resource caps and sandboxing
  appropriate for Jetson Orin Nano–class hardware.

**Important:** the agent never writes to `transition_morphism.json`.
Folding an accepted witness into `independent_execution` stays a separate,
explicit step — consistent with the existing test-suite comment that no
synthetic/unreviewed record should appear there.

### Why this is useful, not just plumbing

Gate 4 independence is based on machine-class fingerprint
(`os`/`architecture`/`python_version`). An x86_64 CI witness and an
aarch64 Jetson witness have different fingerprints, so they are
*automatically* independent under Rule 4 in `are_independent()` — no
config or code change needed. Running the gate suite on a real Jetson
device therefore produces a genuinely stronger Gate 4 witness than two
x86_64 runs ever could, for free.

## Deploying to a Jetson device

1. JetPack ships Ubuntu (20.04/22.04) on aarch64 with Python 3.10+
   available; install Python 3.11 if not already present (no native
   wheels are required — this repo has no C-extension dependencies beyond
   the stdlib).
2. Clone the repo to `/opt/signal-system` on the device.
3. Create an unprivileged `signal-system` system user/group.
4. Create `/var/lib/signal-system/witnesses`, owned by that user.
5. Install the unit files:
   ```
   cp edge_runtime/systemd/signal-system-witness.{service,timer} /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable --now signal-system-witness.timer
   ```
6. Inspect produced witnesses under
   `/var/lib/signal-system/witnesses/<uuid>.json`; review and, if accepted,
   append to `transition_morphism.json`'s `independent_execution` by hand
   (same process as any other witness today).

## Risks / open items

- **Storage wear.** Witness JSON files accumulate indefinitely; no
  rotation is implemented. On eMMC/SD-card Jetson storage this should get
  a retention policy before long-running unattended use.
- **Determinism gate (Gate 3) cost.** `gate_determinism` re-runs the
  evidence gate 3 times per invocation via subprocess; on Jetson Orin
  Nano–class CPUs this is still sub-second (pure hashing), but the hourly
  timer cadence should be tuned if the device is shared with other
  workloads.
- **Single-implementation coverage.** The edge agent only exercises the
  Python path (`src/`); `impl_b/` (Go) cross-implementation parity is not
  run on-device. Add a second agent invocation if Go is installed on the
  target Jetson and on-device cross-impl parity becomes a requirement.
- **Witness merge is manual by design.** This avoids an edge device
  silently asserting "the transition is valid" without review, but means
  the operational loop (run → inspect → merge) is not yet automated.
