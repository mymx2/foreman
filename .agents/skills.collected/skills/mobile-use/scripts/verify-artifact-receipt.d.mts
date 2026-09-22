//#region src/verify-artifact-receipt.d.ts
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
export declare function verifyArtifactReceipt(receiptPath: string): Promise<Readonly<{
  schemaVersion: 1;
  ok: boolean;
  commandOk: boolean | null;
  receipt: string;
  visualInspection: false;
  artifacts: readonly VerifiedArtifact[];
  exitCode: 0 | 3 | 4;
}>>;
//#endregion