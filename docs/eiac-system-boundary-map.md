# EIAC System Boundary Map (COSCTL Admissibility Stack)

Version: v1.0 (isolated spec artifact)
Scope: Structural semantics only (no execution layer, no ESS, no runtime binding)

---

## 0. Purpose

This document defines the **structural boundary architecture** of the COSCTL admissibility system:

- Compilation space (what can exist)
- Governance space (what is admissible)
- Proof space (what is derivable)
- Normalization space (what is canonical)
- Topological space (what is structurally close)
- Criticality space (what is stable vs phase-transitioning)

This system is **not an interpreter**.
It is a stratified restriction-and-quotient geometry over a fixed possibility space.

---

## 1. Core Object Spaces

### 1.1 Source Space

```
S = Intent / Program Space
```

Uninterpreted structured inputs.

---

### 1.2 Execution Possibility Space (v1.5 Compilation Output)

```
C : S → P ∪ {fail}
```

- P = space of all possible execution artifacts
- No admissibility filtering occurs here

---

## 2. EIAC Governance Layer (v1.6)

### 2.1 Admissibility Definition

```
A(env) ⊆ P
```

Defined as:

```
A(env) =
(⋂_a lift_a(A_a(π_a(env)))) ∩ X(env)
```

Where:

- A_a = adapter-local admissibility functions
- π_a = environment projection per adapter
- X(env) = K-typed coupling constraint closure

---

### 2.2 Structural Meaning

EIAC is a **restriction operator**, not a computation engine:

```
P → A(env)
```

It only filters the pre-existing possibility space.

---

## 3. Coupling Space (K-typed Closure)

### 3.1 Definition

```
K = Budgets ⊎ ResourceLocks ⊎ Zones ⊎ GovEdges
```

### 3.2 Coupling Set

```
X(env) ⊆ P
```

Membership condition:

A packet p is in X(env) iff there exists a **K-typed witness**:

- wellTyped(w, K)
- validate(w, env)
- applies(w, p)

---

### 3.3 Interpretation

- X(env) is not primitive
- It is induced from K-witness validation
- All cross-adapter effects must pass through K

---

## 4. Proof-Carrying Layer (v1.7)

### 4.1 Admissibility as Derivation

```
Proof(env, p) ⇔ (env, p) ∈ A
```

### 4.2 Collapse Identity

```
A(env) ⇔ ∃ Proof(env, p)
```

### 4.3 Extractor

```
Extract(env, p) → Proof(env, p) ∪ {⊥}
```

Properties:

- deterministic
- non-interactive
- no hidden state

---

### 4.4 Proof Structure

A proof consists of:

- Π_local: adapter-local proofs
- Π_couple: K-witness set
- Π_glue: EIAC recomposition trace

---

## 5. Proof Normalization (vPNF)

### 5.1 Quotient Structure

```
Π / ~
```

Where ~ is equivalence over:

- adapter-local proof equivalence
- coupling witness redundancy
- structural recomposition equivalence

---

### 5.2 Normalization Operator

```
PNF : Proof → Proof*
```

Properties:

- idempotent
- deterministic
- semantics-preserving
- produces canonical representative per equivalence class

---

## 6. EIAC Topology (Cost-Induced Geometry)

### 6.1 Topological Space

```
(Π / ~ , τ_cost)
```

Where τ_cost is induced by normalization cost.

### 6.2 Interpretation

- proximity = similarity under normalization
- continuity = structural stability of proofs
- discontinuity = structural rewrites under normalization collapse

---

## 7. Criticality Layer (χ(k))

### 7.1 Constraint Decomposition

```
X(env) = ⋂ X_k(env)
```

Each constraint k has:

```
χ(k) ∈ {0,1}
```

- 0 → topology-preserving constraint
- 1 → phase-transition constraint

---

### 7.2 Brittleness Metric

```
B(env) = Σ w_k · χ(k)
```

Where weights are structural only.

---

### 7.3 Interpretation

- χ(k) classifies constraint behavior
- B(env) measures governance fragility
- This is a geometric property of admissibility, not a policy decision

---

## 8. Dependency Chain (System Flow)

```
S
↓
C (compile)
↓
P (possibility space)
↓
A(env) (EIAC restriction)
↓
Proof(env,p)
↓
PNF (quotient normalization)
↓
(Π/~, τ_cost) topology
↓
χ(k), B(env) criticality
```

---

## 9. Boundary Invariants

### 9.1 No Upward Causality

- χ(k) cannot affect A(env)
- PNF cannot affect governance
- Proofs cannot modify compilation

---

### 9.2 No Hidden Evaluation Layer

All semantics reduce to:

- function on fixed space
- restriction operator
- quotient structure
- topology induced by cost

No external interpreter exists.

---

## 10. System Identity Statement

COSCTL EIAC is a stratified admissibility geometry where:

- compilation generates a fixed possibility space
- governance restricts it via environment-indexed filters
- proofs certify membership in that restricted space
- normalization quotients proof fibers
- topology defines structural proximity
- criticality classifies constraint-induced phase transitions

---

End of document.
