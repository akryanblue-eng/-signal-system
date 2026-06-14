#!/usr/bin/env bash
# DSVM-0 Conformance Stack — full verification
# Runs all five crates in sequence and exits non-zero on the first failure.
# Usage: ./ci.sh [--root <repo-root>]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0

step() {
    echo ""
    echo "=== $* ==="
}

ok() {
    echo "  OK  $*"
    PASS=$((PASS + 1))
}

fail() {
    echo "  FAIL  $*"
    FAIL=$((FAIL + 1))
}

# ── Layer A: Schema compiler (grammar determinism) ────────────────────────────
step "schema-compiler: 17 tests"
(cd "$ROOT/schema-compiler" && cargo test --quiet 2>&1) && ok "schema-compiler" || fail "schema-compiler"

# ── Regenerate outputs and verify hash stability ──────────────────────────────
step "schema-compiler: generate + combined_hash check"
SCHEMA_OUT="$(mktemp -d)"
SCHEMA_COMBINED_HASH_LOCKED="772a0ccc18861627c4f4bc6611134ba017b27e7c21b50f4236a7eaf2a25314d7"
SCHEMA_COMBINED_HASH_ACTUAL=$(cd "$ROOT/schema-compiler" && \
    cargo run --quiet -- build \
        --input EVENT_SCHEMAS.v1.json \
        --output-dir "$SCHEMA_OUT" 2>&1 | grep "Combined hash:" | awk '{print $NF}')
if [ "$SCHEMA_COMBINED_HASH_ACTUAL" = "$SCHEMA_COMBINED_HASH_LOCKED" ]; then
    ok "schema-compiler combined_hash stable ($SCHEMA_COMBINED_HASH_ACTUAL)"
else
    fail "schema-compiler combined_hash DRIFT: got $SCHEMA_COMBINED_HASH_ACTUAL, expected $SCHEMA_COMBINED_HASH_LOCKED"
fi

# ── Layer B: impl_c (CT-0 / RI-0 execution core) ─────────────────────────────
step "impl_c: build + run (CT-0 + spatial replay)"
(cd "$ROOT/impl_c" && cargo run --quiet 2>&1 | grep -E "^(spatial )?verdict:" | grep -v FAIL) \
    && ok "impl_c CT-0 + spatial verdict" || fail "impl_c verdict"

# ── Layer C: golden-lock (Merkle identity gate) ───────────────────────────────
step "golden-lock: verify baseline (includes spatial binding)"
(cd "$ROOT/golden-lock" && \
    cargo run --quiet -- verify \
        --vectors vectors \
        --spatial-lock "$ROOT/spatial-vm-replay/spatial-lock.json" \
        --baseline golden-lock.json 2>&1 | grep -E "^(PASS|FAIL)") \
    && ok "golden-lock" || fail "golden-lock"

# ── Layer D: replay-witness (field-level RI-0 trace) ─────────────────────────
step "replay-witness: build"
(cd "$ROOT/replay-witness" && cargo build --quiet 2>&1) && ok "replay-witness build" || fail "replay-witness build"

# ── Spatial VM replay (state machine + dispatch seal) ────────────────────────
step "spatial-vm-replay: 21 tests"
(cd "$ROOT/spatial-vm-replay" && cargo test --quiet 2>&1) && ok "spatial-vm-replay" || fail "spatial-vm-replay"

# ── spatial-vm-replay: verify golden vectors ─────────────────────────────────
step "spatial-vm-replay: verify spatial-lock.json"
(cd "$ROOT/spatial-vm-replay" && \
    cargo run --quiet -- verify \
        --vectors vectors \
        --baseline spatial-lock.json 2>&1 | grep -E "^(OK|FAIL)") \
    && ok "spatial-lock verify" || fail "spatial-lock verify"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  DSVM-0 conformance: ${PASS} passed, ${FAIL} failed"
echo "════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
