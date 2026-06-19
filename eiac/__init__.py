"""EIAC v0 realization (docs/eiac-schema-v1.0.md, docs/eiac-stratified-admissibility-v0.1.md).

This package is the first executable artifact in the EIAC stack: a
canonical encoder/hasher (canon.py) and a structural proof verifier
(extract.py) over the data shapes frozen in the schema doc.

It is intentionally isolated. Nothing in this package is imported by, or
imports from, cvp_transition/, cvp_drift_injector/, or src/. It implements
no execution semantics, no normalization (vPNF), and no criticality (chi(k))
-- those remain undefined, per the schema doc's non-goals section.
"""
