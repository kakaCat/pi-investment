import { defineConfig } from 'tsdown'

// Client-half bundle config. react is EXTERNAL (served by the DSH shell's
// module-loader seed); page-kit is BUNDLED via noExternal — it's a shared
// workspace util lib, not a dsh module, and the shell loader cannot resolve
// plugin workspace deps at runtime (missing noExternal → require throws →
// client half fails to load → sidebar button disappears).
//
// marked is BUNDLED for the same reason: tsdown externalizes everything in
// package.json `dependencies` by default, so listing marked there left a
// literal require("marked") in the bundle — and the shell's seed map holds
// ONLY react/react-dom/.../@deepseek-ai/* (see staticModules in
// @deepseek-ai/dsh-web-frontend). Nothing a plugin can register makes a bare
// npm package resolvable, so it must be inlined. 2026-09-16: shipping it
// external broke the whole client half — "require(\"marked\") missed the
// module table" on boot.
export default defineConfig({
  entry: { client: 'src/client/index.ts' },
  format: ['cjs'],
  outDir: 'lib',
  clean: false,
  sourcemap: false,
  noExternal: [/@pi-investment\/page-kit/, 'marked'],
  external: ['react', 'react/jsx-runtime'],
  target: 'chrome120',
  minify: true,
  outExtensions: () => ({ js: '.cjs' }),
})
