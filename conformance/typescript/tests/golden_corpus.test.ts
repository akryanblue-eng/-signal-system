/**
 * Assertion-based conformance suite. Every case in the language-agnostic
 * golden corpus must reproduce exactly; the two manifest hashes
 * (proof_schema_hash, registry_hash) must match the committed manifest
 * byte-for-byte. This is the actual portability evidence: it shows an
 * independent TypeScript implementation, given only the same JSON fixtures
 * any other language would load, converges on identical outputs.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { runOp } from "../src/corpusOps.js";
import { verifyManifest } from "../src/manifest.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// dist/tests/golden_corpus.test.js -> dist -> typescript -> conformance -> repo root
const REPO_ROOT = path.resolve(__dirname, "..", "..", "..", "..");

interface GoldenCase {
  id: string;
  category: string;
  op: string;
  args: Record<string, unknown>;
  expect?: unknown;
  expect_error?: string;
}

function loadJson(relPath: string): unknown {
  return JSON.parse(readFileSync(path.join(REPO_ROOT, relPath), "utf-8"));
}

const corpus = loadJson("src/golden_corpus/cases.json") as {
  version: string;
  cases: GoldenCase[];
};

test("corpus version is frozen", () => {
  assert.equal(corpus.version, "golden_corpus.v1");
});

test("all four categories are present", () => {
  const categories = new Set(corpus.cases.map((c) => c.category));
  assert.deepEqual(
    [...categories].sort(),
    ["adversarial", "boundary", "canonical", "equivalence"]
  );
});

test("case ids are unique", () => {
  const ids = corpus.cases.map((c) => c.id);
  assert.equal(new Set(ids).size, ids.length);
});

for (const testCase of corpus.cases) {
  test(`golden case ${testCase.id}`, () => {
    if (testCase.expect_error !== undefined) {
      assert.throws(
        () => runOp(testCase.op, testCase.args),
        (err: unknown) => err instanceof Error && err.message.includes(testCase.expect_error as string)
      );
    } else {
      const actual = runOp(testCase.op, testCase.args);
      assert.deepEqual(actual, testCase.expect);
    }
  });
}

test("manifest on disk matches recomputed manifest", () => {
  const manifest = loadJson("src/golden_corpus/manifest.json") as Record<string, unknown>;
  const registry = loadJson("src/edge_extractor_v1.json") as never;
  const parity = verifyManifest(manifest, registry);

  assert.equal(parity.proofSchemaHash.ts, parity.proofSchemaHash.manifest);
  assert.equal(parity.registryHash.ts, parity.registryHash.manifest);
});
