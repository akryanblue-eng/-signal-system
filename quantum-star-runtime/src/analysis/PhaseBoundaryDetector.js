// PhaseBoundaryDetector.js
// Detects φ₀ — the exploration pressure threshold where the system transitions
// from stable equivalence partitioning to unstable.
//
// Also computes the Cross-Run φ₀ Consistency Metric (CRφC) across runs/implementations.
//
// SAL (Stability-at-Scale Law):
//   φ = D × log(1 + E)   — exploration pressure scalar
//   D = average replay window depth across live branches (structural divergence)
//   E = beat-tape event density (events/sec, perturbation intensity)
//   GSS ≈ S(φ)            — stability response function, empirically determined
//
// φ and gss are pre-computed by EquivalenceGraph.build() and exposed on the result.
//
// Three expected response regimes for S(φ):
//   Stable compression:  linear decay   → canonicalization is robust
//   Phase transition:    sigmoid collapse → structure holds to φ₀, then fractures
//   Chaotic:             flat low value  → equivalence stopped working earlier
//
// PBD algorithm: maximum variance reduction via optimal 2-regime split.

// ── Helpers ─────────────────────────────────────────────────────────────────────
function mean(arr) {
  return arr.reduce((s, v) => s + v, 0) / arr.length;
}
function variance(arr) {
  const m = mean(arr);
  return arr.reduce((s, v) => s + (v - m) ** 2, 0) / arr.length;
}

import { makeProvenance } from './Provenance.js';

// ── Phase Boundary Detector ──────────────────────────────────────────────────────

// Detect φ₀ from SAL data.
// data: Array<{ phi: number, gss: number }> — at least 4 points required.
// provenance: optional Provenance descriptor — carried on result unchanged.
// Returns null if data is insufficient or system shows no variance.
export function detectPhaseBoundary(data, provenance = null) {
  if (!data || data.length < 4) return null;

  const sorted  = [...data].sort((a, b) => a.phi - b.phi);
  const allGSS  = sorted.map(d => d.gss);
  const totalVar = variance(allGSS);

  const prov = provenance ?? makeProvenance();

  // No variance → system fully stable across this φ range (no boundary detectable yet)
  if (totalVar < 1e-10) {
    return Object.freeze({ provenance: prov, phi0: null, stable: true, score: 0, totalVariance: totalVar });
  }

  // Find the split point k that maximizes explained variance (= Var(all) - Var(left) - Var(right))
  let bestScore = -Infinity, bestK = 1;
  for (let k = 1; k < sorted.length - 1; k++) {
    const leftGSS  = sorted.slice(0, k + 1).map(d => d.gss);
    const rightGSS = sorted.slice(k + 1).map(d => d.gss);
    const score    = totalVar - (variance(leftGSS) + variance(rightGSS));
    if (score > bestScore) { bestScore = score; bestK = k; }
  }

  const phi0     = sorted[bestK].phi;
  const leftGSS  = sorted.slice(0, bestK + 1).map(d => d.gss);
  const rightGSS = sorted.slice(bestK + 1).map(d => d.gss);
  const leftVar  = variance(leftGSS);
  const rightVar = variance(rightGSS);
  // stabilityRatio << 1 confirms left regime is tighter than right (expected at a real boundary)
  const stabilityRatio = leftVar / (rightVar + 1e-10);
  const leftMean       = mean(leftGSS);
  const rightMean      = mean(rightGSS);

  // Valid boundary: variance reduction is positive AND left is tighter AND stable→unstable
  const isValid = bestScore > 0 && stabilityRatio < 0.5;

  // φ₀ semantic: not "the system collapses here" but "your equivalence relation stops
  // being a stable projector of state space beyond this point"
  return Object.freeze({
    provenance:     prov,
    phi0,
    score:          +bestScore.toFixed(6),
    leftVariance:   +leftVar.toFixed(6),
    rightVariance:  +rightVar.toFixed(6),
    stabilityRatio: +stabilityRatio.toFixed(6),
    leftMean:       +leftMean.toFixed(6),
    rightMean:      +rightMean.toFixed(6),
    boundaryIndex:  bestK,
    totalVariance:  +totalVar.toFixed(6),
    sampleCount:    data.length,
    isValid,
    regime:         leftMean > rightMean ? 'stable→unstable' : 'unstable→stable',
  });
}

// ── Cross-Run φ₀ Consistency Metric ─────────────────────────────────────────────

// CRφC = Var(φ₀) / Mean(φ₀) across independent runs.
// Dimensionless instability ratio: low → φ₀ is a real structural property;
//                                  high → φ₀ is a sampling artifact.
// phi0Values: Array<number> — one per independent run (or implementation).
// Requires ≥2 values.
export function crossRunConsistency(phi0Values, provenance = null) {
  if (!phi0Values || phi0Values.length < 2) return null;
  const valid = phi0Values.filter(v => v !== null && isFinite(v));
  if (valid.length < 2) return null;

  const mu     = mean(valid);
  const v      = variance(valid);
  const CRphiC = v / (Math.abs(mu) + 1e-10);

  // Regime thresholds — calibrated to catch meaningful structure vs noise
  let regime, interpretation;
  if (CRphiC < 0.01) {
    regime = 'stable';
    interpretation = 'φ₀ is invariant — phase boundary is a structural property of the system';
  } else if (CRphiC < 0.1) {
    regime = 'weak';
    interpretation = 'φ₀ shifts slightly — partial structure, sensitive to corpus composition';
  } else {
    regime = 'unstable';
    interpretation = 'φ₀ is inconsistent — phase boundary is likely a sampling artifact';
  }

  return Object.freeze({
    provenance:  provenance ?? makeProvenance(),
    CRphiC:      +CRphiC.toFixed(6),
    mean:        +mu.toFixed(6),
    variance:    +v.toFixed(6),
    stddev:      +Math.sqrt(v).toFixed(6),
    sampleCount: valid.length,
    regime,
    interpretation,
    summary:     `φ₀ = ${mu.toFixed(4)} ± ${Math.sqrt(v).toFixed(4)} (CRφC=${CRphiC.toFixed(4)}, ${regime})`,
  });
}
