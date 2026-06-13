#!/usr/bin/env node
const { readFileSync, writeFileSync, existsSync, mkdirSync } = require("fs");
const path = require("path");
const crypto = require("crypto");

function createRunId(candidatePath) {
  const hash = crypto.createHash("sha1").update(candidatePath).digest("hex").slice(0, 8);
  return `run-${hash}`;
}

function loadCandidate(filePath) {
  const raw = readFileSync(filePath, "utf-8");
  return JSON.parse(raw);
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

function ensureRunDir(runId) {
  const dir = path.join(".vdce", "runs", runId);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return "./" + dir;
}

function writeArtifact(verdict, dir, runId, candidatePath, baselineId) {
  const fileName = verdict.type === "certificate" ? "certificate.json" : "drift.json";
  const filePath = path.join(dir, fileName);

  const artifactType = verdict.type === "usage_error" ? "invalid_input" : verdict.type;

  const payload = {
    runId,
    type: artifactType,
    candidatePath,
    baselineId,
    timestamp: Date.now(),
    error: verdict.message ?? null,
  };

  writeFileSync(filePath, JSON.stringify(payload, null, 2), "utf-8");
}

function formatStdout(verdict, artifactDir, exitCode) {
  const status = verdict.type === "certificate" ? "PASS" : "FAIL";

  const certificatePath =
    verdict.type === "certificate" ? `${artifactDir}/certificate.json` : "none";

  const driftReportPath =
    verdict.type === "certificate" ? "none" : `${artifactDir}/drift.json`;

  const nextStep =
    verdict.type === "certificate" ? `vdce show ${artifactDir}` :
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

function mapExitCode(verdictType) {
  switch (verdictType) {
    case "certificate": return 0;
    case "usage_error": return 1;
    case "drift": return 2;
    case "internal_error": return 3;
  }
}

function main() {
  const args = process.argv.slice(2);

  if (args[0] !== "verify") {
    console.error("Missing required command: verify");
    process.exit(1);
  }

  const candidatePath = args[1];

  if (!candidatePath) {
    console.error("Missing required argument: <candidate.json>");
    process.exit(1);
  }

  if (!existsSync(candidatePath)) {
    console.error(`Candidate not found: ${candidatePath}`);
    process.exit(1);
  }

  const runId = createRunId(candidatePath);
  const artifactDir = ensureRunDir(runId);
  const candidate = loadCandidate(candidatePath);

  let verdict;

  try {
    verdict = evaluate(candidate);
  } catch (err) {
    verdict = { type: "internal_error", message: String(err) };
  }

  const exitCode = mapExitCode(verdict.type);
  writeArtifact(verdict, artifactDir, runId, candidatePath, candidate.baselineId ?? null);
  const stdout = formatStdout(verdict, artifactDir, exitCode);

  process.stdout.write(stdout + "\n");
  process.exit(exitCode);
}

main();
