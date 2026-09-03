import { defineConfig } from 'tsdown'

// Client-half bundle config: one entry (src/client/index.ts) compiled to CJS.
// Pure DOM/fetch — no react, no @deepseek-ai imports — so no externals needed;
// the bundle is self-contained and wrapped by scripts/wrap-client.mjs.
export default defineConfig({
  entry: { client: 'src/client/index.ts' },
  format: ['cjs'],
  outDir: 'lib',
  clean: false,
  sourcemap: false,
  external: [],
  target: 'chrome120',
  minify: true,
  outExtensions: () => ({ js: '.cjs' }),
})
