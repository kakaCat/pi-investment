import { defineConfig } from 'tsdown'

// Host-half (server) build. Published DSH plugins load from compiled output,
// so the package ships dist/index.mjs instead of raw TypeScript sources.
// Plain .mjs config on purpose: tsdown's TS config loading hits a known
// Node.js bug on some versions; .mjs loads natively everywhere.
// @deepseek-ai/cordis stays external — provided by the DSH host runtime.
export default defineConfig({
  entry: { index: 'src/index.ts' },
  format: ['esm'],
  outDir: 'dist',
  clean: true,
  sourcemap: false,
  dts: true,
  external: ['@deepseek-ai/cordis'],
  target: 'node20',
  minify: false,
})
