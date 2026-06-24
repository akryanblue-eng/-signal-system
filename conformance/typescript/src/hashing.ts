/**
 * Hash Domain (NIC v1.1 Freeze Commit F) and the Candidate Recognition
 * Contract's UNKNOWN-edge check (Freeze Commit E). Every hash operates on
 * edge_id only — never serialized edges, never JSON blobs. Set ordering =
 * sorted(edge_id). Witness ordering = caller-supplied order, never re-sorted.
 */
import { createHash } from "node:crypto";
import { canonJsonBytes } from "./canonJson.js";

export const HASH_ALG = "sha256";
export const DIGEST_LEN_BYTES = 32;

export const UNKNOWN_EDGE_TYPE = "UNKNOWN";

export interface EdgeLike {
  from_: string;
  type: string;
  to: string;
}

export function computeEdgeId(from_: string, edgeType: string, to: string): string {
  const payload = canonJsonBytes({ from: from_, to, type: edgeType });
  return createHash("sha256").update(payload).digest("hex");
}

export function checkNoUnknownEdges(edges: EdgeLike[], waivedEdgeIds: Set<string>): boolean {
  return edges.every((edge) => {
    const edgeId = computeEdgeId(edge.from_, edge.type, edge.to);
    return !(edge.type === UNKNOWN_EDGE_TYPE && !waivedEdgeIds.has(edgeId));
  });
}

export function computeSetHash(edgeIds: string[]): string {
  const hash = createHash("sha256");
  for (const eid of [...edgeIds].sort()) {
    hash.update(Buffer.from(eid, "ascii"));
  }
  return hash.digest("hex");
}

export function computeWitnessHash(edgeIds: string[]): string {
  const hash = createHash("sha256");
  for (const eid of edgeIds) {
    hash.update(Buffer.from(eid, "ascii"));
  }
  return hash.digest("hex");
}
