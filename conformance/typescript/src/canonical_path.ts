/**
 * Canonical Path Pipeline (NIC v1.1 Freeze Commit C). Frozen step order, no
 * recovery, no best-effort cleanup:
 *   1. UTF-8 validate   2. NFC normalize   3. separator normalize (\ -> /),
 *   reject absolute/drive-qualified input   4. dot-segment collapse, reject
 *   escape past repo root via '..'   5. emit CanonicalPath bytes.
 */
import { NICError } from "./errors.js";

function hasUnpairedSurrogate(s: string): boolean {
  for (let i = 0; i < s.length; i++) {
    const code = s.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = s.charCodeAt(i + 1);
      if (Number.isNaN(next) || next < 0xdc00 || next > 0xdfff) return true;
      i++;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return true;
    }
  }
  return false;
}

export function canonicalPath(raw: string): Uint8Array {
  if (hasUnpairedSurrogate(raw)) {
    throw new NICError(`Path is not valid UTF-8: ${raw}`);
  }
  let text = raw.normalize("NFC");
  text = text.replace(/\\/g, "/");

  if (text.startsWith("/")) {
    throw new NICError(`Absolute path rejected: ${JSON.stringify(text)}`);
  }
  const firstSegment = text.split("/", 1)[0];
  if (firstSegment.includes(":")) {
    throw new NICError(`Drive-qualified path rejected: ${JSON.stringify(text)}`);
  }

  const collapsed: string[] = [];
  for (const seg of text.split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg === "..") {
      if (collapsed.length === 0) {
        throw new NICError(`Path escapes repo root via '..': ${JSON.stringify(text)}`);
      }
      collapsed.pop();
    } else {
      collapsed.push(seg);
    }
  }
  return new TextEncoder().encode(collapsed.join("/"));
}

export function canonicalPathHex(raw: string): string {
  return Buffer.from(canonicalPath(raw)).toString("hex");
}
