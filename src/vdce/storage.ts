import { existsSync, mkdirSync, writeFileSync, renameSync, appendFileSync } from "fs";

export interface StorageModule {
  createRunDir(runPath: string): void;
  writeArtifactAtomic(filePath: string, data: object): void;
  appendTrace(tracePath: string, event: object): void;
}

export function createRunDir(runPath: string): void {
  if (existsSync(runPath)) {
    throw new Error(`RUN_COLLISION: ${runPath}`);
  }
  mkdirSync(runPath, { recursive: false });
}

export function writeArtifactAtomic(filePath: string, data: object): void {
  const tmp = `${filePath}.tmp`;
  writeFileSync(tmp, JSON.stringify(data, null, 2), "utf-8");
  renameSync(tmp, filePath);
}

// Append-only. File order = causal order. No timestamps in events.
export function appendTrace(tracePath: string, event: object): void {
  appendFileSync(tracePath, JSON.stringify(event) + "\n", { flag: "a" });
}
