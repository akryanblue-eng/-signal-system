// golden_corpus_test.go — Post-freeze evaluation harness for NIC-CLEANROOM-002.
// Written by the orchestrator after freeze; does NOT modify src (nic.go).
// Drives the frozen Go implementation against cases.json (corpus v1.1, 30 cases).
package nic

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// ── Corpus schema ─────────────────────────────────────────────────────────────

type corpusFile struct {
	Version       string        `json:"version"`
	CorpusRelease string        `json:"corpus_release"`
	SpecVersion   string        `json:"spec_version"`
	Cases         []corpusCase  `json:"cases"`
}

type corpusCase struct {
	ID          string                 `json:"id"`
	Category    string                 `json:"category"`
	Op          string                 `json:"op"`
	Args        map[string]interface{} `json:"args"`
	Expect      interface{}            `json:"expect"`
	ExpectError string                 `json:"expect_error"`
}

type manifestFile struct {
	ProofSchemaHash string `json:"proof_schema_hash"`
	RegistryHash    string `json:"registry_hash"`
	HashAlg         string `json:"hash_alg"`
	CaseCount       int    `json:"case_count"`
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func corpusDir(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	return filepath.Join(wd, "golden_corpus")
}

func loadCorpus(t *testing.T) corpusFile {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(corpusDir(t), "cases.json"))
	if err != nil {
		t.Fatalf("read cases.json: %v", err)
	}
	var cf corpusFile
	if err := json.Unmarshal(data, &cf); err != nil {
		t.Fatalf("parse cases.json: %v", err)
	}
	return cf
}

func loadManifest(t *testing.T) manifestFile {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(corpusDir(t), "manifest.json"))
	if err != nil {
		t.Fatalf("read manifest.json: %v", err)
	}
	var mf manifestFile
	if err := json.Unmarshal(data, &mf); err != nil {
		t.Fatalf("parse manifest.json: %v", err)
	}
	return mf
}

func loadRegistry(t *testing.T) interface{} {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(corpusDir(t), "edge_extractor_v1.json"))
	if err != nil {
		t.Fatalf("read edge_extractor_v1.json: %v", err)
	}
	// Use json.Decoder with UseNumber to avoid float64 precision loss.
	var doc interface{}
	dec := json.NewDecoder(strings.NewReader(string(data)))
	dec.UseNumber()
	if err := dec.Decode(&doc); err != nil {
		t.Fatalf("parse edge_extractor_v1.json: %v", err)
	}
	return doc
}

// ── Op dispatcher ─────────────────────────────────────────────────────────────

// runCase executes a single corpus case and returns (result, errMsg).
// result is the computed value (may be nil if an error was raised).
// errMsg is non-empty if the op raised an error.
func runCase(c corpusCase) (result interface{}, errMsg string) {
	args := c.Args
	switch c.Op {

	case "canonical_path":
		raw, _ := args["raw"].(string)
		s, err := CanonicalPathHex(raw)
		if err != nil {
			return nil, err.Error()
		}
		return s, ""

	case "glob_match":
		pattern, _ := args["pattern"].(string)
		path, _ := args["path"].(string)
		b, err := GlobMatch(pattern, path)
		if err != nil {
			return nil, err.Error()
		}
		return b, ""

	case "canonicalize_url":
		rawURL, _ := args["raw_url"].(string)
		s, err := CanonicalizeURL(rawURL)
		if err != nil {
			return nil, err.Error()
		}
		return s, ""

	case "compute_edge_id":
		from_, _ := args["from_"].(string)
		typ, _ := args["type"].(string)
		to, _ := args["to"].(string)
		s, err := ComputeEdgeID(from_, typ, to)
		if err != nil {
			return nil, err.Error()
		}
		return s, ""

	case "compute_set_hash":
		rawIDs, _ := args["edge_ids"].([]interface{})
		ids := make([]string, len(rawIDs))
		for i, v := range rawIDs {
			ids[i], _ = v.(string)
		}
		return ComputeSetHash(ids), ""

	case "compute_witness_hash":
		rawIDs, _ := args["edge_ids"].([]interface{})
		ids := make([]string, len(rawIDs))
		for i, v := range rawIDs {
			ids[i], _ = v.(string)
		}
		return ComputeWitnessHash(ids), ""

	case "check_no_unknown_edges":
		rawEdges, _ := args["edges"].([]interface{})
		edges := make([]Edge, 0, len(rawEdges))
		for _, re := range rawEdges {
			em, _ := re.(map[string]interface{})
			edges = append(edges, Edge{
				From: strVal(em, "from_"),
				Type: strVal(em, "type"),
				To:   strVal(em, "to"),
			})
		}
		rawWaived, _ := args["waived_edge_ids"].([]interface{})
		waived := make([]string, len(rawWaived))
		for i, v := range rawWaived {
			waived[i], _ = v.(string)
		}
		b, err := CheckNoUnknownEdges(edges, waived)
		if err != nil {
			return nil, err.Error()
		}
		return b, ""

	case "verify_proof_schema":
		obj := args["obj"]
		return VerifyProofSchema(obj), ""

	default:
		return nil, fmt.Sprintf("unknown op: %s", c.Op)
	}
}

func strVal(m map[string]interface{}, key string) string {
	s, _ := m[key].(string)
	return s
}

// ── Tests ─────────────────────────────────────────────────────────────────────

func TestGoldenCorpusConformance(t *testing.T) {
	cf := loadCorpus(t)
	t.Logf("corpus: version=%s release=%s spec=%s cases=%d",
		cf.Version, cf.CorpusRelease, cf.SpecVersion, len(cf.Cases))

	pass, fail := 0, 0
	for _, c := range cf.Cases {
		c := c
		t.Run(c.ID, func(t *testing.T) {
			result, errMsg := runCase(c)

			if c.ExpectError != "" {
				// Op must error; error message must contain the substring.
				if errMsg == "" {
					t.Errorf("expected error containing %q, got result %v", c.ExpectError, result)
					fail++
					return
				}
				if !strings.Contains(errMsg, c.ExpectError) {
					t.Errorf("error %q does not contain expected substring %q", errMsg, c.ExpectError)
					fail++
					return
				}
				pass++
				return
			}

			// Op must succeed and return expect.
			if errMsg != "" {
				t.Errorf("unexpected error: %s", errMsg)
				fail++
				return
			}

			// Compare result to expect.
			if !valuesEqual(result, c.Expect) {
				t.Errorf("got %v (%T), want %v (%T)", result, result, c.Expect, c.Expect)
				fail++
				return
			}
			pass++
		})
	}

	t.Logf("result: %d/%d passed", pass, pass+fail)
}

// valuesEqual compares two values for corpus equality.
// JSON numbers unmarshaled from cases.json come as float64 or bool.
func valuesEqual(got, want interface{}) bool {
	// Both nil.
	if got == nil && want == nil {
		return true
	}
	// Bool.
	if gb, ok := got.(bool); ok {
		if wb, ok := want.(bool); ok {
			return gb == wb
		}
		return false
	}
	// String.
	if gs, ok := got.(string); ok {
		if ws, ok := want.(string); ok {
			return gs == ws
		}
		return false
	}
	return fmt.Sprintf("%v", got) == fmt.Sprintf("%v", want)
}

func TestManifestHashParity(t *testing.T) {
	mf := loadManifest(t)
	reg := loadRegistry(t)

	// proof_schema_hash
	psh, err := ProofSchemaHash()
	if err != nil {
		t.Fatalf("ProofSchemaHash: %v", err)
	}
	if psh != mf.ProofSchemaHash {
		t.Errorf("proof_schema_hash mismatch:\n  got:  %s\n  want: %s", psh, mf.ProofSchemaHash)
	} else {
		t.Logf("proof_schema_hash: OK (%s)", psh)
	}

	// registry_hash
	rh, err := RegistryHash(reg)
	if err != nil {
		t.Fatalf("RegistryHash: %v", err)
	}
	if rh != mf.RegistryHash {
		t.Errorf("registry_hash mismatch:\n  got:  %s\n  want: %s", rh, mf.RegistryHash)
	} else {
		t.Logf("registry_hash: OK (%s)", rh)
	}

	// case_count
	cf := loadCorpus(t)
	if len(cf.Cases) != mf.CaseCount {
		t.Errorf("case_count mismatch: corpus has %d, manifest says %d", len(cf.Cases), mf.CaseCount)
	} else {
		t.Logf("case_count: OK (%d)", mf.CaseCount)
	}
}
