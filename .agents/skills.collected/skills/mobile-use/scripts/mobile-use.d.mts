//#region src/cli/mobile-use.d.ts
export interface RunCliOptions {
  stdout?: NodeJS.WritableStream;
  stderr?: NodeJS.WritableStream;
  platform?: NodeJS.Platform;
  dependencies?: Record<string, unknown>;
}
export interface ParsedArguments {
  command?: string;
  help?: boolean;
  version?: boolean;
  params: Record<string, unknown>;
  pretty: boolean;
}
export declare function runCli(argv: string[], options?: RunCliOptions): Promise<number>;
export declare function parseArguments(argv: string[]): ParsedArguments;
//#endregion