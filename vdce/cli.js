#!/usr/bin/env node
const { readFileSync, existsSync, mkdirSync } = require("fs");
const path = require("path");
const { computeRunId } = require("../dist/src/vdce/identity");
const { createRunDir, writeArtifactAtomic, appendTrace } = require("../dist/src/vdce/storage");

const SCHEMA_VERSION = "v1";
const EXECUTION_VERSION = "v1";

function loadCandidate(filePath) {
  return JSON.parse(readFileSync(filePath, "utf-8"));
}

function evaluate(candidate) {
  if (!candidate.payload) {
    return { type: "usage_error", message: "Missing payload" };
  }

  if (candidate.payload.__forceError) {
    throw new Error(candidate.payload.__forceError);
  }

  const hash = JSON.stringify(candidate.payload).length % 2;
  if (hash === 0) {
    return { type: "certificate" };
  } else {
    return { type: "drift", message: "Deterministic mismatch" };
  }
}

function mapExitCode(verdictType) {
  switch (verdictType) {
    case "certificate":   return 0;
    case "usage_error":   return 1;
    case "drift":         return 2;
    case "internal_error": return 3;
  }
}

function formatVerifyStdout(verdict, artifactDir, exitCode) {
  const status = verdict.type === "certificate" ? "PASS" : "FAIL";

  const certificatePath =
    verdict.type === "certificate" ? `${artifactDir}/certificate.json` : "none";

  const driftReportPath =
    verdict.type === "certificate" ? "none" : `${artifactDir}/drift.json`;

  const nextStep =
    verdict.type === "certificate"   ? `vdce show ${artifactDir}` :
    verdict.type === "internal_error" ? "vdce doctor" :
    `vdce inspect ${artifactDir}`;

  return [
    `VDCE RESULT: ${status}`,
    `Artifacts: ${artifactDir}`,
    `Certificate: ${certificatePath}`,
    `Drift Report: ${driftReportPath}`,
    `Next Step: ${nextStep}`,
    `Exit Code: ${exitCode}`,
  ].join("\n");
}

// ── inspect ───────────────────────────────────────────────────────────────────

function loadArtifact(runDir) {
  const certPath = path.join(runDir, "certificate.json");
  const driftPath = path.join(runDir, "drift.json");

  if (existsSync(certPath)) {
    return { file: certPath, data: JSON.parse(readFileSync(certPath, "utf-8")) };
  }
  if (existsSync(driftPath)) {
    return { file: driftPath, data: JSON.parse(readFileSync(driftPath, "utf-8")) };
  }
  return null;
}

function formatInspect(artifact) {
  const { file, data } = artifact;
  const runId = path.basename(path.dirname(file));
  return [
    `VDCE INSPECT: ${runId}`,
    `  Type:       ${data.type}`,
    `  Candidate:  ${data.candidatePath}`,
    `  Baseline:   ${data.baselineId ?? "none"}`,
    `  Error:      ${data.error ?? "none"}`,
    `  Artifact:   ./${file}`,
  ].join("\n");
}

function cmdInspect(args) {
  const runDir = args[0];

  if (!runDir) {
    console.error("Missing required argument: <run-dir>");
    process.exit(1);
  }
  if (!existsSync(runDir)) {
    console.error(`Run directory not found: ${runDir}`);
    process.exit(1);
  }

  const artifact = loadArtifact(runDir);
  if (!artifact) {
    console.error(`No artifact found in: ${runDir}`);
    process.exit(1);
  }

  process.stdout.write(formatInspect(artifact) + "\n");
  process.exit(0);
}

// ── verify ────────────────────────────────────────────────────────────────────

function cmdVerify(args) {
  const candidatePath = args[0];

  if (!candidatePath) {
    console.error("Missing required argument: <candidate.json>");
    process.exit(1);
  }
  if (!existsSync(candidatePath)) {
    console.error(`Candidate not found: ${candidatePath}`);
    process.exit(1);
  }

  const candidate = loadCandidate(candidatePath);

  const runId = computeRunId({
    candidate,
    baselineId: candidate.baselineId ?? null,
    schemaVersion: SCHEMA_VERSION,
    executionVersion: EXECUTION_VERSION,
  });

  const runDirRel = path.join(".vdce", "runs", runId);
  mkdirSync(path.join(".vdce", "runs"), { recursive: true }); // parent only
  createRunDir(runDirRel);          // throws RUN_COLLISION if already exists
  const artifactDir = "./" + runDirRel;
  const tracePath = path.join(runDirRel, "trace.jsonl");

  appendTrace(tracePath, { step: 0, type: "verify_start", candidatePath, runId });

  let verdict;
  try {
    verdict = evaluate(candidate);
  } catch (err) {
    verdict = { type: "internal_error", message: String(err) };
  }

  appendTrace(tracePath, { step: 1, type: "verdict", verdictType: verdict.type });

  const artifactType = verdict.type === "usage_error" ? "invalid_input" : verdict.type;
  const fileName = verdict.type === "certificate" ? "certificate.json" : "drift.json";
  const artifactPath = path.join(runDirRel, fileName);

  writeArtifactAtomic(artifactPath, {
    runId,
    type: artifactType,
    candidatePath,
    baselineId: candidate.baselineId ?? null,
    timestamp: Date.now(),
    error: verdict.message ?? null,
  });

  appendTrace(tracePath, { step: 2, type: "artifact_written", file: fileName });

  const exitCode = mapExitCode(verdict.type);
  const stdout = formatVerifyStdout(verdict, artifactDir, exitCode);
  process.stdout.write(stdout + "\n");
  process.exit(exitCode);
}

// ── dispatch ──────────────────────────────────────────────────────────────────

function main() {
  const [cmd, ...rest] = process.argv.slice(2);

  switch (cmd) {
    case "verify":  return cmdVerify(rest);
    case "inspect": return cmdInspect(rest);
    default:
      console.error(`Unknown command: ${cmd ?? "(none)"}`);
      console.error("Available commands: verify, inspect");
      process.exit(1);
  }
}

main();
