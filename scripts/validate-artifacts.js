const fs = require("fs");
const path = require("path");

const RUNS_DIR = ".vdce/runs";

const ALLOWED_KEYS = new Set(["runId", "type", "candidatePath", "baselineId", "timestamp", "error"]);

const CERTIFICATE_TYPES = new Set(["certificate"]);
const DRIFT_TYPES = new Set(["drift", "internal_error", "invalid_input"]);

function assertField(obj, key, expectedType, file, nullable = false) {
  const val = obj[key];
  if (nullable && val === null) return;
  if (typeof val !== expectedType) {
    console.error(`FAIL: ${file}: field "${key}" must be ${nullable ? `${expectedType} | null` : expectedType}, got ${val === null ? "null" : typeof val}`);
    process.exit(1);
  }
}

function assertNoExtraKeys(obj, file) {
  for (const key of Object.keys(obj)) {
    if (!ALLOWED_KEYS.has(key)) {
      console.error(`FAIL: ${file}: unexpected key "${key}"`);
      process.exit(1);
    }
  }
}

function validateCertificate(obj, file) {
  assertNoExtraKeys(obj, file);
  assertField(obj, "runId", "string", file);
  assertField(obj, "type", "string", file);
  assertField(obj, "candidatePath", "string", file);
  assertField(obj, "timestamp", "number", file);
  assertField(obj, "baselineId", "string", file, /* nullable */ true);
  // error must be present (may be null)
  if (!Object.prototype.hasOwnProperty.call(obj, "error")) {
    console.error(`FAIL: ${file}: missing required field "error"`);
    process.exit(1);
  }

  if (!CERTIFICATE_TYPES.has(obj.type)) {
    console.error(`FAIL: ${file}: type must be "certificate", got "${obj.type}"`);
    process.exit(1);
  }
}

function validateDrift(obj, file) {
  assertNoExtraKeys(obj, file);
  assertField(obj, "runId", "string", file);
  assertField(obj, "type", "string", file);
  assertField(obj, "candidatePath", "string", file);
  assertField(obj, "timestamp", "number", file);
  assertField(obj, "baselineId", "string", file, /* nullable */ true);
  if (!Object.prototype.hasOwnProperty.call(obj, "error")) {
    console.error(`FAIL: ${file}: missing required field "error"`);
    process.exit(1);
  }

  if (!DRIFT_TYPES.has(obj.type)) {
    console.error(`FAIL: ${file}: type must be one of ${JSON.stringify([...DRIFT_TYPES])}, got "${obj.type}"`);
    process.exit(1);
  }
  // drift artifacts must carry an error string
  if (typeof obj.error !== "string" || obj.error.length === 0) {
    console.error(`FAIL: ${file}: "error" must be a non-empty string for drift artifacts`);
    process.exit(1);
  }
}

function validateRun(runDir) {
  const fullPath = path.join(RUNS_DIR, runDir);
  const certPath = path.join(fullPath, "certificate.json");
  const driftPath = path.join(fullPath, "drift.json");

  const hasCert = fs.existsSync(certPath);
  const hasDrift = fs.existsSync(driftPath);

  if (hasCert && hasDrift) {
    console.error(`FAIL: ${runDir}: both certificate.json and drift.json exist`);
    process.exit(1);
  }
  if (!hasCert && !hasDrift) {
    console.error(`FAIL: ${runDir}: neither certificate.json nor drift.json exists`);
    process.exit(1);
  }

  if (hasCert) {
    const obj = JSON.parse(fs.readFileSync(certPath, "utf8"));
    validateCertificate(obj, `${runDir}/certificate.json`);
    if (obj.runId !== runDir) {
      console.error(`FAIL: ${runDir}/certificate.json: runId "${obj.runId}" does not match directory name "${runDir}"`);
      process.exit(1);
    }
    console.log(`PASS: ${runDir}/certificate.json (type=${obj.type})`);
  }

  if (hasDrift) {
    const obj = JSON.parse(fs.readFileSync(driftPath, "utf8"));
    validateDrift(obj, `${runDir}/drift.json`);
    if (obj.runId !== runDir) {
      console.error(`FAIL: ${runDir}/drift.json: runId "${obj.runId}" does not match directory name "${runDir}"`);
      process.exit(1);
    }
    console.log(`PASS: ${runDir}/drift.json (type=${obj.type})`);
  }
}

function main() {
  if (!fs.existsSync(RUNS_DIR)) {
    console.error("FAIL: .vdce/runs directory does not exist");
    process.exit(1);
  }

  const runDirs = fs.readdirSync(RUNS_DIR)
    .filter(d => d.startsWith("run-"))
    .sort();

  if (runDirs.length === 0) {
    console.error("FAIL: no run directories found in .vdce/runs");
    process.exit(1);
  }

  for (const runDir of runDirs) {
    validateRun(runDir);
  }

  console.log(`PASS: all ${runDirs.length} run(s) validated`);
  process.exit(0);
}

main();
