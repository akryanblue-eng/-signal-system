import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";

function loadGolden(filePath: string): string {
  return readFileSync(filePath, "utf-8").trimEnd();
}

const golden = {
  pass: loadGolden("goldens/verify_pass.stdout.txt"),
  drift: loadGolden("goldens/verify_drift.stdout.txt"),
  internal_error: loadGolden("goldens/verify_internal_error.stdout.txt"),
};

const CLI = "node vdce/cli.js verify";

const doc = `# VDCE Quickstart

## 1. Run verification
\`\`\`bash
${CLI} fixtures/pass/candidate.json
\`\`\`

## 2. Expected output (PASS)
\`\`\`
${golden.pass}
\`\`\`

## 3. Exit codes
| Code | Meaning |
|------|---------|
| 0 | PASS — certificate issued |
| 1 | USAGE ERROR — bad invocation |
| 2 | DRIFT — deterministic mismatch |
| 3 | INTERNAL ERROR — evaluation threw |

## 4. Artifact layout
Every run writes to \`.vdce/runs/<run-id>/\`, which contains exactly one of:

| Verdict | File written |
|---------|-------------|
| PASS | \`certificate.json\` |
| DRIFT / INTERNAL ERROR / USAGE ERROR | \`drift.json\` |

Run IDs are derived from \`sha1(candidatePath)[0:8]\`, making them deterministic per input and collision-free across parallel CI jobs.

## 5. Failure example — DRIFT
\`\`\`
${golden.drift}
\`\`\`

## 6. Failure example — INTERNAL ERROR
\`\`\`
${golden.internal_error}
\`\`\`

## 7. Validate artifacts
\`\`\`bash
node scripts/validate-artifacts.js
\`\`\`

Checks every run directory for:
- exactly one artifact file (certificate.json XOR drift.json)
- all required schema fields with correct types
- no unexpected keys
- \`runId\` value matches directory name
- drift artifacts carry a non-empty \`error\` string

## 8. Mental model

\`\`\`
candidate.json → evaluate() → verdict → ABI stdout + artifact
                               │
                  ┌────────────┼────────────┐
                  │            │            │
             certificate    drift.json   drift.json
               .json       (type=drift) (type=internal_error)
\`\`\`

VDCE is a deterministic pipeline: the same input always produces the same stdout, the same exit code, and the same artifact shape. The golden files in \`goldens/\` are the locked ABI contract.
`;

if (!existsSync("docs")) mkdirSync("docs");
writeFileSync("docs/QUICKSTART.md", doc.trimStart());
console.log("docs/QUICKSTART.md written");
