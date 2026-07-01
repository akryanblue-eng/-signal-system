# NIC-CLEANROOM-002 Implementation Snapshot

This directory is a snapshot of the frozen Go implementation from
NIC-CLEANROOM-002, preserved here because the standalone clean-room
repository (`/home/user/nic-cleanroom-002`) is ephemeral and will be
reclaimed when the container is reclaimed.

## Provenance

- **Experiment:** NIC-CLEANROOM-002
- **Language:** Go 1.21
- **Freeze commit:** `7f5051f` in the standalone clean-room repo
  (`Freeze: Go implementation + Q-log (NIC-CLEANROOM-002)`)
- **Post-freeze commits:**
  - `615d412` — corpus revealed, evaluation harness added (`golden_corpus_test.go`)
  - `f508ed1` — `corpus_exercises_this` set on all Q-log entries

## Contents

| File | Written by |
|---|---|
| `nic.go` | clean-room implementer (pre-freeze) |
| `nic_test.go` | clean-room implementer (pre-freeze) |
| `go.mod`, `go.sum` | clean-room implementer (pre-freeze) |
| `QUESTIONS.md` | clean-room implementer (pre-freeze) |
| `QUESTIONS.json` | clean-room implementer (pre-freeze) + orchestrator (`corpus_exercises_this`) |
| `FREEZE.md` | clean-room implementer (pre-freeze) |
| `golden_corpus_test.go` | orchestrator (post-freeze evaluation harness) |
| `golden_corpus/` | orchestrator (post-freeze corpus reveal) |

## Build and test (from this directory)

```sh
go test ./... -count=1
```

Note: requires Go 1.21+ and internet access for `golang.org/x/text v0.14.0`
(or a local module cache). The `go.sum` file pins the exact version.
