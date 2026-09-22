import { defineConfig } from "vite-plus";

// CLI bundles must run with plain `node` on any machine: one self-contained
// ESM file per entry, no runtime imports. Output lands in ../scripts
// (committed; not a git-ignored directory name). dts + exports follow the
// publishable-library standard; staged/pre-commit hooks are intentionally off.
export default defineConfig({
  pack: {
    entry: {
      "mobile-use": "src/bin/mobile-use.ts",
      "verify-artifact-receipt": "src/verify-artifact-receipt.ts",
    },
    format: ["esm"],
    platform: "node",
    target: "esnext",
    outDir: "../scripts",
    clean: true,
    treeshake: true,
    sourcemap: false,
    deps: { resolveDepSubpath: true },
    dts: {
      generator: "tsgo",
    },
    exports: {
      bin: {
        "mobile-use": "./src/bin/mobile-use.ts",
        "mobile-use-verify": "./src/verify-artifact-receipt.ts",
      },
    },
  },
  lint: {
    options: {
      typeAware: true,
      typeCheck: true,
    },
  },
  fmt: {},
});
