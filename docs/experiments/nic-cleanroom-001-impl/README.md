# NIC-CLEANROOM-001 — frozen implementation snapshot

See `../nic-cleanroom-001.md` for the full experiment record. This directory
is a snapshot of the standalone clean-room repository, copied in after the
implementation was frozen and the corpus was revealed, so the artifact
survives independently of the now-discarded clean-room environment.

Provenance — two distinct phases, kept separate so it's clear what the
clean-room implementer actually saw vs. what was added afterward:

**Phase 1 (clean-room, frozen at commit `86e3cfb` in the original
standalone repo, before any corpus access):**
- `docs/nic-v1.1-spec.md` — the only input
- `Cargo.toml`, `Cargo.lock`, `.gitignore`
- `src/` — the implementation
- `QUESTIONS.md`, `FREEZE.md` — the implementer's own ambiguity log and
  freeze declaration, written before the corpus existed in its environment

**Phase 2 (orchestrator, added after freeze and after revealing the
corpus — not authored by the clean-room implementer, and `src/` was not
touched):**
- `golden_corpus/` — copies of `cases.json`, `manifest.json`,
  `edge_extractor_v1.json`, revealed only after Phase 1 was declared
  complete
- `tests/golden_corpus.rs` — evaluation harness driving every corpus case
  and the manifest hash check through the frozen `src/` public API

Run `cargo test` from this directory to reproduce both the 27/27 corpus
result and the manifest hash parity result recorded in the experiment
record.
