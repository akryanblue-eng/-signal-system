/**
 * Golden-corpus op dispatcher — maps each `op` name in
 * src/golden_corpus/cases.json to this port's implementation. Mirrors the
 * Python reference runner's `_run_op` switch (same op names, same argument
 * shapes) so the same fixture file drives both conformance suites.
 */
import { canonicalPathHex } from "./canonical_path.js";
import { canonicalizeUrl } from "./canonical_url.js";
import { globMatch } from "./glob.js";
import { checkNoUnknownEdges, computeEdgeId, computeSetHash, computeWitnessHash } from "./hashing.js";
import { verifyProofSchema } from "./proof_v1.js";

export function runOp(op: string, args: Record<string, unknown>): unknown {
  switch (op) {
    case "canonical_path":
      return canonicalPathHex(args["raw"] as string);
    case "glob_match":
      return globMatch(args["pattern"] as string, args["path"] as string);
    case "canonicalize_url":
      return canonicalizeUrl(args["raw_url"] as string);
    case "compute_edge_id":
      return computeEdgeId(args["from_"] as string, args["type"] as string, args["to"] as string);
    case "compute_set_hash":
      return computeSetHash(args["edge_ids"] as string[]);
    case "compute_witness_hash":
      return computeWitnessHash(args["edge_ids"] as string[]);
    case "check_no_unknown_edges": {
      const edges = (args["edges"] as Array<Record<string, string>>).map((e) => ({
        from_: e["from_"],
        type: e["type"],
        to: e["to"],
      }));
      const waived = new Set(args["waived_edge_ids"] as string[]);
      return checkNoUnknownEdges(edges, waived);
    }
    case "verify_proof_schema":
      return verifyProofSchema(args["obj"]);
    default:
      throw new Error(`Unknown op ${JSON.stringify(op)} in golden corpus`);
  }
}
