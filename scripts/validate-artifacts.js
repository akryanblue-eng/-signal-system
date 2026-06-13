const fs = require("fs");
const path = require("path");

const RUNS_DIR = ".vdce/runs";

function validateArtifact() {
  if (!fs.existsSync(RUNS_DIR)) {
    console.error("FAIL: .vdce/runs directory does not exist");
    process.exit(1);
  }

  const runDirs = fs.readdirSync(RUNS_DIR).filter(d => d.startsWith("run-"));

  if (runDirs.length === 0) {
    console.error("FAIL: No run directories found in .vdce/runs");
    process.exit(1);
  }

  for (const runDir of runDirs) {
    const fullPath = path.join(RUNS_DIR, runDir);
    const certificatePath = path.join(fullPath, "certificate.json");
    const driftPath = path.join(fullPath, "drift.json");

    const hasCertificate = fs.existsSync(certificatePath);
    const hasDrift = fs.existsSync(driftPath);

    if (hasCertificate && hasDrift) {
      console.error(`FAIL: Both certificate.json and drift.json exist in ${runDir}`);
      process.exit(1);
    }

    if (!hasCertificate && !hasDrift) {
      console.error(`FAIL: Neither certificate.json nor drift.json exists in ${runDir}`);
      process.exit(1);
    }

    if (hasCertificate) {
      const cert = JSON.parse(fs.readFileSync(certificatePath, "utf8"));
      if (cert.type !== "certificate") {
        console.error(`FAIL: certificate.json in ${runDir} must have type="certificate"`);
        process.exit(1);
      }
      if (!cert.runId || !cert.candidatePath) {
        console.error(`FAIL: certificate.json in ${runDir} must have runId and candidatePath`);
        process.exit(1);
      }
      console.log(`PASS: certificate.json in ${runDir} is valid`);
    }

    if (hasDrift) {
      const drift = JSON.parse(fs.readFileSync(driftPath, "utf8"));
      const validTypes = ["drift", "internal_error", "invalid_input"];
      if (!validTypes.includes(drift.type)) {
        console.error(`FAIL: drift.json in ${runDir} must have type in ${JSON.stringify(validTypes)}, got: ${drift.type}`);
        process.exit(1);
      }
      if (!drift.error && !drift.message) {
        console.error(`FAIL: drift.json in ${runDir} must have an error or message field`);
        process.exit(1);
      }
      console.log(`PASS: drift.json in ${runDir} is valid (type=${drift.type})`);
    }
  }

  console.log("PASS: All artifacts validated");
  process.exit(0);
}

validateArtifact();
