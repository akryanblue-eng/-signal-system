/**
 * Manifest verification — independently recomputes the two load-bearing
 * hashes the committed src/golden_corpus/manifest.json attests
 * (proof_schema_hash, registry_hash) and reports whether this TypeScript
 * implementation reproduces them byte-for-byte. This is the strongest
 * available evidence of canonical-JSON-serialization parity across
 * languages: both hashes are sha256 over canon_json of a value this port
 * never reads from Python source, only from the same JSON each language
 * loads independently (registry.json, and this port's own schema
 * descriptor).
 */
import { createHash } from "node:crypto";
import { canonJsonBytes, type CanonValue } from "./canonJson.js";
import { computeProofSchemaHash } from "./proof_v1.js";

export interface ManifestParity {
  proofSchemaHash: { ts: string; manifest: unknown; matches: boolean };
  registryHash: { ts: string; manifest: unknown; matches: boolean };
  matches: boolean;
}

export function computeRegistryHash(registry: CanonValue): string {
  return createHash("sha256").update(canonJsonBytes(registry)).digest("hex");
}

export function verifyManifest(
  manifest: Record<string, unknown>,
  registry: CanonValue
): ManifestParity {
  const tsProofSchemaHash = computeProofSchemaHash();
  const tsRegistryHash = computeRegistryHash(registry);

  const proofSchemaMatch = tsProofSchemaHash === manifest["proof_schema_hash"];
  const registryMatch = tsRegistryHash === manifest["registry_hash"];

  return {
    proofSchemaHash: {
      ts: tsProofSchemaHash,
      manifest: manifest["proof_schema_hash"],
      matches: proofSchemaMatch,
    },
    registryHash: {
      ts: tsRegistryHash,
      manifest: manifest["registry_hash"],
      matches: registryMatch,
    },
    matches: proofSchemaMatch && registryMatch,
  };
}
