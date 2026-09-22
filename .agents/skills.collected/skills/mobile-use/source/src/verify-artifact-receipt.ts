#!/usr/bin/env node

import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { isRecord } from "./lib/types.ts";
import type { JsonRecord } from "./lib/types.ts";

const SCHEMA_VERSION = 1;
const MAX_RECEIPT_BYTES = 8 * 1024 * 1024;

interface ArtifactDescriptor {
  algorithm: string;
  digest: string;
  mediaType?: string;
  size: number;
  uri: string;
}

interface VerifiedArtifact extends ArtifactDescriptor {
  path?: string;
  actualSize?: number;
  actualDigest?: string;
  sizeMatches?: boolean;
  digestMatches?: boolean;
  integrity: "verified" | "mismatch" | "unavailable";
  reason?: string;
}

interface VerifierError extends Error {
  code?: string;
  exitCode?: number;
}

export async function verifyArtifactReceipt(receiptPath: string) {
  const absoluteReceiptPath = resolve(receiptPath);
  let receiptStat;
  try {
    receiptStat = await stat(absoluteReceiptPath);
  } catch (error) {
    throw verifierError(
      "artifact.receipt.unreadable",
      `Unable to read receipt: ${error instanceof Error ? error.message : String(error)}`,
      2,
    );
  }
  if (!receiptStat.isFile())
    throw verifierError("artifact.receipt.invalid", "Receipt path is not a file.", 2);
  if (receiptStat.size > MAX_RECEIPT_BYTES) {
    throw verifierError("artifact.receipt.too-large", "Receipt exceeds the 8 MiB limit.", 2);
  }

  let payload: unknown;
  try {
    payload = JSON.parse(await readFile(absoluteReceiptPath, "utf8"));
  } catch (error) {
    throw verifierError(
      "artifact.receipt.invalid-json",
      `Unable to parse receipt JSON: ${error instanceof Error ? error.message : String(error)}`,
      2,
    );
  }

  if (!isRecord(payload))
    throw verifierError("artifact.receipt.invalid", "Receipt JSON must be an object.", 2);

  const descriptors = collectArtifactDescriptors(payload);
  if (descriptors.length === 0) {
    throw verifierError(
      "artifact.receipt.missing-artifact",
      "No SHA-256 artifact descriptor was found.",
      2,
    );
  }

  const artifacts: VerifiedArtifact[] = [];
  for (const descriptor of descriptors) artifacts.push(await verifyDescriptor(descriptor));

  const hasMismatch = artifacts.some((artifact) => artifact.integrity === "mismatch");
  const hasUnavailable = artifacts.some((artifact) => artifact.integrity === "unavailable");
  const exitCode = hasMismatch ? 4 : hasUnavailable ? 3 : 0;

  return Object.freeze({
    schemaVersion: SCHEMA_VERSION,
    ok: exitCode === 0,
    commandOk: typeof payload.ok === "boolean" ? payload.ok : null,
    receipt: absoluteReceiptPath,
    visualInspection: false,
    artifacts: Object.freeze(artifacts),
    exitCode,
  });
}

function collectArtifactDescriptors(payload: JsonRecord): ArtifactDescriptor[] {
  const found = new Map<string, ArtifactDescriptor>();
  const pending: unknown[] = [payload];
  const visited = new Set<unknown>();

  while (pending.length > 0) {
    const value = pending.pop();
    if (!value || typeof value !== "object" || visited.has(value)) continue;
    visited.add(value);

    if (isArtifactDescriptor(value)) {
      const candidate = value as JsonRecord & {
        algorithm: string;
        digest: string;
        size: number;
        uri: string;
      };
      const key = `${candidate.uri}\n${candidate.digest}\n${candidate.size}`;
      if (!found.has(key))
        found.set(
          key,
          Object.freeze({
            algorithm: candidate.algorithm,
            digest: candidate.digest.toLowerCase(),
            mediaType: typeof candidate.mediaType === "string" ? candidate.mediaType : undefined,
            size: candidate.size,
            uri: candidate.uri,
          }),
        );
    }

    if (Array.isArray(value)) pending.push(...value);
    else pending.push(...Object.values(value));
  }

  return [...found.values()];
}

async function verifyDescriptor(descriptor: ArtifactDescriptor): Promise<VerifiedArtifact> {
  if (!descriptor.uri.startsWith("file:")) {
    return Object.freeze({
      ...descriptor,
      integrity: "unavailable" as const,
      reason: "Only local file: artifact URIs can be verified.",
    });
  }

  let artifactPath: string;
  try {
    artifactPath = fileURLToPath(descriptor.uri);
  } catch (error) {
    return Object.freeze({
      ...descriptor,
      integrity: "unavailable" as const,
      reason: `Invalid file URI: ${error instanceof Error ? error.message : String(error)}`,
    });
  }
  if (!isAbsolute(artifactPath)) {
    return Object.freeze({
      ...descriptor,
      integrity: "unavailable" as const,
      reason: "Artifact path is not absolute.",
    });
  }

  try {
    const artifactStat = await stat(artifactPath);
    if (!artifactStat.isFile()) {
      return Object.freeze({
        ...descriptor,
        path: artifactPath,
        integrity: "unavailable" as const,
        reason: "Artifact is not a file.",
      });
    }
    const actualDigest = await sha256File(artifactPath);
    const sizeMatches = artifactStat.size === descriptor.size;
    const digestMatches = actualDigest === descriptor.digest;
    return Object.freeze({
      ...descriptor,
      path: artifactPath,
      actualSize: artifactStat.size,
      actualDigest,
      sizeMatches,
      digestMatches,
      integrity: (sizeMatches && digestMatches ? "verified" : "mismatch") as
        | "verified"
        | "mismatch",
    });
  } catch (error) {
    return Object.freeze({
      ...descriptor,
      path: artifactPath,
      integrity: "unavailable" as const,
      reason: error instanceof Error ? error.message : String(error),
    });
  }
}

function sha256File(filePath: string): Promise<string> {
  return new Promise((resolveDigest, rejectDigest) => {
    const hash = createHash("sha256");
    const stream = createReadStream(filePath);
    stream.on("data", (chunk: Buffer | string) => hash.update(chunk));
    stream.once("error", rejectDigest);
    stream.once("end", () => resolveDigest(hash.digest("hex")));
  });
}

function isArtifactDescriptor(
  value: unknown,
): value is JsonRecord & { algorithm: string; digest: string; size: number; uri: string } {
  if (!isRecord(value)) return false;
  const candidate = value as JsonRecord;
  return (
    candidate.algorithm === "sha256" &&
    typeof candidate.digest === "string" &&
    /^[0-9a-f]{64}$/iu.test(candidate.digest as string) &&
    Number.isSafeInteger(candidate.size) &&
    (candidate.size as number) >= 0 &&
    typeof candidate.uri === "string"
  );
}

function verifierError(code: string, message: string, exitCode: number): VerifierError {
  const error: VerifierError = new Error(message);
  error.code = code;
  error.exitCode = exitCode;
  return error;
}

async function main(argv: string[]): Promise<number> {
  if (argv.length !== 1 || argv[0] === "--help" || argv[0] === "-h") {
    const help = "Usage: verify-artifact-receipt.mjs /absolute/path/to/mobile-use-receipt.json";
    if (argv[0] === "--help" || argv[0] === "-h") {
      process.stdout.write(`${help}\n`);
      return 0;
    }
    throw verifierError("artifact.cli.argument", help, 2);
  }

  const result = await verifyArtifactReceipt(argv[0]);
  process.stdout.write(`${JSON.stringify(result)}\n`);
  return result.exitCode;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    process.exitCode = await main(process.argv.slice(2));
  } catch (error) {
    const verifierErr = error as VerifierError;
    process.stderr.write(
      `${JSON.stringify({
        schemaVersion: SCHEMA_VERSION,
        ok: false,
        error: {
          code:
            typeof verifierErr?.code === "string"
              ? verifierErr.code
              : "artifact.verification.failed",
          message: error instanceof Error ? error.message : String(error),
        },
      })}\n`,
    );
    process.exitCode = Number.isInteger(verifierErr?.exitCode) ? verifierErr.exitCode : 1;
  }
}
