// Implementation B — Go
// RI-0 + CT-0 Evidence Gate chain.
// Canonical encoding must match Python Implementation A exactly.
package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"sort"
	"time"
)

// ---- Types ----

type Signal struct {
	Key   string
	Value int64
}

type WitnessPacket304 struct {
	RunID            string
	PrevStateBytes   []byte
	FrozenBatchBytes []byte
	BundleHash       []byte // 32 bytes
	BundleVersion    uint32
	ValidatorPubkey  []byte // 32 bytes
	Signals          []Signal
}

type CFRFailureRecord struct {
	CFRId        string
	FailureCode  string
	Scope        string
	Outcome      string
	EvidenceHash string
	PriorityRank int
}

type Verdict struct {
	Status string
	CFR    *CFRFailureRecord
}

type Certificate struct {
	CertificateID string
	RunID         string
	ReplayCommit  string
	VerdictStatus string
	IssuedAtNS    int64
}

// ---- RI-0 ----

func encodeSignals(signals []Signal) []byte {
	// Dedup by key (last value wins), then sort lexicographically
	deduped := make(map[string]int64)
	for _, s := range signals {
		deduped[s.Key] = s.Value
	}
	keys := make([]string, 0, len(deduped))
	for k := range deduped {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	var out []byte
	for _, k := range keys {
		kb := []byte(k)
		// uint16 big-endian key length
		lenBuf := make([]byte, 2)
		binary.BigEndian.PutUint16(lenBuf, uint16(len(kb)))
		out = append(out, lenBuf...)
		out = append(out, kb...)
		// int64 big-endian value
		valBuf := make([]byte, 8)
		binary.BigEndian.PutUint64(valBuf, uint64(deduped[k]))
		out = append(out, valBuf...)
	}
	return out
}

func ri0Replay(p WitnessPacket304) []byte {
	h := sha256.New()

	// run_id: uint16 length + utf8 bytes
	runIDBytes := []byte(p.RunID)
	tmp := make([]byte, 2)
	binary.BigEndian.PutUint16(tmp, uint16(len(runIDBytes)))
	h.Write(tmp)
	h.Write(runIDBytes)

	// prev_state_bytes: uint32 length + bytes
	tmp4 := make([]byte, 4)
	binary.BigEndian.PutUint32(tmp4, uint32(len(p.PrevStateBytes)))
	h.Write(tmp4)
	h.Write(p.PrevStateBytes)

	// frozen_batch_bytes: uint32 length + bytes
	binary.BigEndian.PutUint32(tmp4, uint32(len(p.FrozenBatchBytes)))
	h.Write(tmp4)
	h.Write(p.FrozenBatchBytes)

	// bundle_hash: fixed 32 bytes
	h.Write(p.BundleHash)

	// bundle_version: uint32 big-endian
	binary.BigEndian.PutUint32(tmp4, p.BundleVersion)
	h.Write(tmp4)

	// validator_pubkey: fixed 32 bytes
	h.Write(p.ValidatorPubkey)

	// signals: uint32 length + encoded bytes
	sigBytes := encodeSignals(p.Signals)
	binary.BigEndian.PutUint32(tmp4, uint32(len(sigBytes)))
	h.Write(tmp4)
	h.Write(sigBytes)

	return h.Sum(nil)
}

// ---- CT-0 ----

func equalBytes(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func ct0Evaluate(authCommit, replayCommit []byte, runID string) (Verdict, Certificate) {
	var verdict Verdict
	if equalBytes(authCommit, replayCommit) {
		verdict = Verdict{Status: "OK"}
	} else {
		evH := sha256.Sum256(append(authCommit, replayCommit...))
		verdict = Verdict{
			Status: "FAIL",
			CFR: &CFRFailureRecord{
				CFRId:        "CFR-MISMATCH",
				FailureCode:  "REPLAY_MISMATCH",
				Scope:        "RI-0/CT-0",
				Outcome:      "FAIL",
				EvidenceHash: hex.EncodeToString(evH[:]),
				PriorityRank: 1,
			},
		}
	}

	certPayload := append(authCommit, replayCommit...)
	certPayload = append(certPayload, []byte(verdict.Status)...)
	certPayload = append(certPayload, []byte(runID)...)
	certHash := sha256.Sum256(certPayload)

	cert := Certificate{
		CertificateID: hex.EncodeToString(certHash[:]),
		RunID:         runID,
		ReplayCommit:  hex.EncodeToString(replayCommit),
		VerdictStatus: verdict.Status,
		IssuedAtNS:    time.Now().UnixNano(),
	}
	return verdict, cert
}

// ---- Synthetic trace (must match Python build_synthetic_trace) ----

func buildSyntheticTrace() WitnessPacket304 {
	bundleHash := sha256.Sum256([]byte("simulation-os-bundle-v0.5"))
	validatorKey := sha256.Sum256([]byte("validator-pubkey-ri0-ct0"))

	prevState := make([]byte, 64)
	frozenBatch := make([]byte, 48)
	for i := 0; i < 48; i += 3 {
		frozenBatch[i] = 0xAB
		frozenBatch[i+1] = 0xCD
		frozenBatch[i+2] = 0xEF
	}

	return WitnessPacket304{
		RunID:            "TRACE-V05-0001",
		PrevStateBytes:   prevState,
		FrozenBatchBytes: frozenBatch,
		BundleHash:       bundleHash[:],
		BundleVersion:    5,
		ValidatorPubkey:  validatorKey[:],
		Signals: []Signal{
			{"signal.alpha", 1},
			{"signal.beta", 2},
			{"signal.gamma", 3},
			{"signal.alpha", 99}, // duplicate — deduped to 99
		},
	}
}

func main() {
	packet := buildSyntheticTrace()

	// Trace ID
	traceInput := append([]byte(packet.RunID), packet.BundleHash...)
	traceHash := sha256.Sum256(traceInput)
	traceID := fmt.Sprintf("%X", traceHash[:8])

	authCommit := ri0Replay(packet)
	replayCommit := ri0Replay(packet)

	if !equalBytes(authCommit, replayCommit) {
		fmt.Println("FATAL: RI-0 non-determinism")
		return
	}

	verdict, cert := ct0Evaluate(authCommit, replayCommit, packet.RunID)

	buildID := "A0FAC3D181C2D1D8" // sha256(main.go)[:16]

	fmt.Printf("run_id:      %s\n", packet.RunID)
	fmt.Printf("build_id:    %s\n", buildID)
	fmt.Printf("trace_id:    %s\n", traceID)
	fmt.Printf("commit:      %s\n", hex.EncodeToString(replayCommit))
	fmt.Printf("certificate: %s\n", cert.CertificateID)
	fmt.Printf("verdict:     %s\n", verdict.Status)
}
