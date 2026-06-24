/**
 * ProofV1 schema — fail-closed verifier and schema-hash derivation. Mirrors
 * the frozen vocabulary exactly: unknown field => FAIL, missing required
 * field => FAIL, hash_alg_id mismatch => FAIL, unrecognized value in any
 * closed-vocabulary field => FAIL. The closed vocabulary for `result` is
 * exactly {PASS, FAIL} — there is no DIAGNOSTIC value at this layer; that
 * status belongs to the boundary-trace step ahead of proof emission, which
 * is out of scope for this deterministic-core port.
 */
import { createHash } from "node:crypto";
import { canonJsonBytes } from "./canonJson.js";
import { HASH_ALG } from "./hashing.js";

export const SPEC_VERSION = "nic.proof.v1";

const SNAPSHOT_MODES = new Set(["git_tree", "manifest"]);
const RESULTS = new Set(["PASS", "FAIL"]);
const REQUIRED_FIELDS = new Set([
  "spec_version",
  "hash_alg_id",
  "snapshot_mode",
  "snapshot_id",
  "extractor_version",
  "result",
  "proof_payload",
]);

export function verifyProofSchema(obj: unknown): boolean {
  if (typeof obj !== "object" || obj === null || Array.isArray(obj)) {
    return false;
  }
  const record = obj as Record<string, unknown>;
  const keys = Object.keys(record);

  if (keys.length !== REQUIRED_FIELDS.size || !keys.every((k) => REQUIRED_FIELDS.has(k))) {
    return false;
  }

  if (record["spec_version"] !== SPEC_VERSION) return false;
  if (record["hash_alg_id"] !== HASH_ALG) return false;
  if (typeof record["snapshot_mode"] !== "string" || !SNAPSHOT_MODES.has(record["snapshot_mode"])) {
    return false;
  }
  if (typeof record["result"] !== "string" || !RESULTS.has(record["result"])) {
    return false;
  }
  if (typeof record["snapshot_id"] !== "string" || record["snapshot_id"] === "") {
    return false;
  }
  if (typeof record["extractor_version"] !== "string" || record["extractor_version"] === "") {
    return false;
  }
  const payload = record["proof_payload"];
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    return false;
  }
  return true;
}

export function schemaDescriptor(): Record<string, unknown> {
  return {
    spec_version: SPEC_VERSION,
    hash_alg_id: HASH_ALG,
    required_fields: [...REQUIRED_FIELDS].sort(),
    snapshot_modes: [...SNAPSHOT_MODES].sort(),
    results: [...RESULTS].sort(),
  };
}

export function computeProofSchemaHash(): string {
  const canonical = canonJsonBytes(schemaDescriptor() as never);
  return createHash("sha256").update(canonical).digest("hex");
}
