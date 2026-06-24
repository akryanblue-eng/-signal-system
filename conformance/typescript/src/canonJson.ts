/**
 * Canonical JSON — must byte-for-byte match Python's
 *   json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
 * since every content hash in NIC (edge_id, proof_schema_hash, extractor_version,
 * proof_id) is computed over this exact encoding. Any divergence here would
 * silently break cross-language hash convergence rather than fail loudly.
 */

export type CanonValue =
  | null
  | boolean
  | number
  | string
  | CanonValue[]
  | { [key: string]: CanonValue };

export function canonJsonString(value: CanonValue): string {
  return stringify(value);
}

export function canonJsonBytes(value: CanonValue): Uint8Array {
  return new TextEncoder().encode(canonJsonString(value));
}

function stringify(value: CanonValue): string {
  if (value === null) {
    return "null";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value) || !Number.isInteger(value)) {
      throw new Error(`canon_json only supports finite integers, got ${value}`);
    }
    return String(value);
  }
  if (typeof value === "string") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map(stringify).join(",") + "]";
  }
  const keys = Object.keys(value).sort();
  return (
    "{" +
    keys.map((k) => JSON.stringify(k) + ":" + stringify(value[k])).join(",") +
    "}"
  );
}
