/**
 * Glob Language (NIC v1.1 Freeze Commit B). Grammar is exactly `*`, `?`,
 * `**`. No `[...]`, `{...}`, `!`. Fail-closed: forbidden syntax is rejected
 * outright, never silently treated as a literal. This is a pure string
 * match over a single (pattern, path) pair — no filesystem traversal, no
 * glob expansion against a directory tree.
 */
import { NICError } from "./errors.js";

const GLOB_FORBIDDEN_CHARS = new Set(["[", "]", "{", "}", "!"]);

export function globMatch(pattern: string, path: string): boolean {
  const forbidden = [...new Set([...pattern].filter((c) => GLOB_FORBIDDEN_CHARS.has(c)))].sort();
  if (forbidden.length > 0) {
    throw new NICError(
      `Glob pattern ${JSON.stringify(pattern)} uses forbidden syntax ${JSON.stringify(
        forbidden
      )} — NIC-GLOB-1 permits only '*', '?', '**'`
    );
  }
  const regex = globToRegex(pattern);
  return new RegExp(`^(?:${regex})$`).test(path);
}

function globToRegex(pattern: string): string {
  const segments = pattern.split("/");
  const n = segments.length;
  const tokens: string[] = segments.map((seg) => (seg === "**" ? "" : globSegmentToRegex(seg)));
  const suppressAfter = new Set<number>();
  const suppressBefore = new Set<number>();

  segments.forEach((seg, idx) => {
    if (seg !== "**") return;
    if (n === 1) {
      tokens[idx] = ".*";
    } else if (idx === 0) {
      tokens[idx] = "(?:.*/)?";
      suppressAfter.add(idx);
    } else if (idx === n - 1) {
      tokens[idx] = "(?:/.*)?";
      suppressBefore.add(idx);
    } else {
      tokens[idx] = "(?:.*/)?";
      suppressAfter.add(idx);
    }
  });

  let result = tokens[0];
  for (let idx = 1; idx < n; idx++) {
    if (suppressBefore.has(idx) || suppressAfter.has(idx - 1)) {
      result += tokens[idx];
    } else {
      result += "/" + tokens[idx];
    }
  }
  return result;
}

function globSegmentToRegex(segment: string): string {
  const parts: string[] = [];
  let i = 0;
  const n = segment.length;
  while (i < n) {
    const c = segment[i];
    if (c === "*") {
      if (i + 1 < n && segment[i + 1] === "*") {
        parts.push(".*");
        i += 2;
      } else {
        parts.push("[^/]*");
        i += 1;
      }
    } else if (c === "?") {
      parts.push("[^/]");
      i += 1;
    } else {
      parts.push(escapeRegexChar(c));
      i += 1;
    }
  }
  return parts.join("");
}

function escapeRegexChar(c: string): string {
  return c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
