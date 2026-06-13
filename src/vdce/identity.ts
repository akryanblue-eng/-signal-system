import { createHash } from "crypto";

export type SemanticId = string;
export type RunId = string;

export interface IdentityInput {
  candidate: unknown;
  baselineId: string | null;
  schemaVersion: string;
  executionVersion: string;
}

export function toCanonicalModel(value: unknown): unknown {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return (value as unknown[]).map(toCanonicalModel);
  const obj = value as Record<string, unknown>;
  return Object.fromEntries(
    Object.keys(obj).sort().map(k => [k, toCanonicalModel(obj[k])])
  );
}

export function computeSemanticId(input: IdentityInput): SemanticId {
  const canonical = toCanonicalModel(input.candidate);
  const payload = JSON.stringify({ canonical, baselineId: input.baselineId ?? null });
  return createHash("sha256").update(payload).digest("hex");
}

export function computeRunId(input: IdentityInput): RunId {
  const semanticId = computeSemanticId(input);
  const payload = JSON.stringify({
    semanticId,
    schemaVersion: input.schemaVersion,
    executionVersion: input.executionVersion,
  });
  return "run-" + createHash("sha256").update(payload).digest("hex").slice(0, 12);
}
