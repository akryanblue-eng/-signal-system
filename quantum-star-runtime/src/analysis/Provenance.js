// Provenance.js
// Immutable descriptor attached to every derived metric (CSF, PBD, CRφC, EquivalenceGraph).
// Lets you attribute any shift in a metric — CRφC, GSS, φ₀ — to a specific
// canonicalizer version, equivalence mode, implementation, or corpus version,
// rather than to a behavioral change in the system.
//
// Without provenance, a canonicalization improvement masquerades as a phase shift.
// With it, diffs are traceable to their cause.

export const QSR_SPEC_VERSION = 'v0.6';
export const IMPLEMENTATION   = 'browser-js';

// Build an immutable provenance descriptor.
// Fields:
//   mode                — equivalence mode used ('exact' | 'canonical' | 'structural')
//   runIndex            — 0-based position in the session's RunStore (null = not from RunStore)
//   canonicalizerVersion — from CausalEquivalence.js (default 'v1')
//   corpusRelease       — content/corpus version tag (null until a corpus versioning system exists)
export function makeProvenance({
  mode               = null,
  runIndex           = null,
  canonicalizerVersion = 'v1',
  corpusRelease      = null,
} = {}) {
  return Object.freeze({
    specVersion:          QSR_SPEC_VERSION,
    implementation:       IMPLEMENTATION,
    canonicalizerVersion,
    equivalenceMode:      mode,
    runIndex,
    corpusRelease,
  });
}
