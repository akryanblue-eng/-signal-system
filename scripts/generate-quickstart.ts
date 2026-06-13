import { readFileSync, writeFileSync } from "fs";

function loadGolden(path: string) {
  return readFileSync(path, "utf-8").trimEnd();
}

// ----------------------
// Frozen ABI Inputs Only
// ----------------------
const golden = {
  pass: loadGolden("goldens/verify_pass.stdout.txt"),
  drift: loadGolden("goldens/verify_drift.stdout.txt"),
  internal_error: loadGolden("goldens/verify_internal_error.stdout.txt"),
};

const CLI = "node vdce/cli.js verify";

// ----------------------
// Render-only document
// ----------------------
const doc = `# VDCE Quickstart

## 1. Run verification
\`\`\`bash
${CLI} fixtures/pass/candidate.json
\`\`\`

---

## 2. Expected output (PASS)
\`\`\`
${golden.pass}
\`\`\`

---

## 3. Exit code model
Exit codes are a **projection of the verdict state machine**:

| Code | Verdict Type |
|------|-------------|
| 0 | certificate |
| 1 | usage_error |
| 2 | drift |
| 3 | internal_error |

---

## 4. Artifact model
Each run produces exactly one artifact directory:
- \`.vdce/runs/run-<sha1[0:8]>/\`

Artifact filename is derived from verdict type:

| Verdict Type | Artifact |
|-------------|----------|
| certificate | certificate.json |
| drift | drift.json |
| internal_error | internal_error.json |

---

## 5. Failure example (DRIFT)
\`\`\`
${golden.drift}
\`\`\`

---

## 6. Failure example (INTERNAL ERROR)
\`\`\`
${golden.internal_error}
\`\`\`

---

## 7. Mental model
VDCE is a deterministic compiler:
\`\`\`
input → evaluate → verdict → projections (stdout + exit code + artifacts)
\`\`\`
No step is allowed to mutate downstream meaning.
`;

writeFileSync("docs/QUICKSTART.md", doc.trimStart());
console.log("docs/QUICKSTART.md written");
