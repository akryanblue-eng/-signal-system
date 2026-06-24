/**
 * Independent conformance runner: loads the language-agnostic golden corpus
 * (src/golden_corpus/cases.json) and the committed manifest, and reports
 * whether this TypeScript port reproduces every case and every load-bearing
 * hash exactly. `npm test` (tests/golden_corpus.test.ts) asserts the same
 * facts; this CLI exists for a human-readable pass/fail report.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { runOp } from "./corpusOps.js";
import { verifyManifest } from "./manifest.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// dist/src/runCorpus.js -> dist -> typescript -> conformance -> repo root
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
  const fullPath = path.join(REPO_ROOT, relPath);
  return JSON.parse(readFileSync(fullPath, "utf-8"));
}

function runCases(): { passed: number; failed: number; failures: string[] } {
  const corpus = loadJson("src/golden_corpus/cases.json") as { cases: GoldenCase[] };
  let passed = 0;
  let failed = 0;
  const failures: string[] = [];

  for (const testCase of corpus.cases) {
    try {
      if (testCase.expect_error !== undefined) {
        let threw = false;
        let message = "";
        try {
          runOp(testCase.op, testCase.args);
        } catch (e) {
          threw = true;
          message = e instanceof Error ? e.message : String(e);
        }
        if (!threw) {
          failed++;
          failures.push(`${testCase.id}: expected error matching ${JSON.stringify(testCase.expect_error)}, but no error was thrown`);
          continue;
        }
        if (!message.includes(testCase.expect_error)) {
          failed++;
          failures.push(`${testCase.id}: error message ${JSON.stringify(message)} does not contain ${JSON.stringify(testCase.expect_error)}`);
          continue;
        }
        passed++;
      } else {
        const actual = runOp(testCase.op, testCase.args);
        if (JSON.stringify(actual) !== JSON.stringify(testCase.expect)) {
          failed++;
          failures.push(`${testCase.id}: expected ${JSON.stringify(testCase.expect)}, got ${JSON.stringify(actual)}`);
          continue;
        }
        passed++;
      }
    } catch (e) {
      failed++;
      const message = e instanceof Error ? e.message : String(e);
      failures.push(`${testCase.id}: unexpected error ${JSON.stringify(message)}`);
    }
  }

  return { passed, failed, failures };
}

function main(): void {
  const { passed, failed, failures } = runCases();
  console.log(`golden corpus: ${passed} passed, ${failed} failed`);
  for (const failure of failures) {
    console.log(`  FAIL ${failure}`);
  }

  const manifest = loadJson("src/golden_corpus/manifest.json") as Record<string, unknown>;
  const registry = loadJson("src/edge_extractor_v1.json") as never;
  const parity = verifyManifest(manifest, registry);

  console.log("manifest parity:");
  console.log(
    `  proof_schema_hash: ${parity.proofSchemaHash.matches ? "MATCH" : "MISMATCH"} (ts=${parity.proofSchemaHash.ts}, manifest=${parity.proofSchemaHash.manifest})`
  );
  console.log(
    `  registry_hash: ${parity.registryHash.matches ? "MATCH" : "MISMATCH"} (ts=${parity.registryHash.ts}, manifest=${parity.registryHash.manifest})`
  );

  if (failed > 0 || !parity.matches) {
    process.exitCode = 1;
  }
}

main();
