import { defineConfig } from 'tsdown'

// Client-half bundle config. Plain .mjs on purpose (see tsdown.config.mjs).
//
// react is EXTERNAL (served by the DSH shell's module-loader seed). Any bare
// npm package imported by client code MUST be bundled — the shell's seed map
// holds ONLY react/react-dom/.../@deepseek-ai/* (see staticModules in
// @deepseek-ai/dsh-web-frontend), nothing a plugin registers makes a bare
// package resolvable at runtime. 2026-09-16: shipping 'marked' external broke
// the whole client half — "require(\"marked\") missed the module table".
//
// 2026-09-20: this plugin is fully self-contained (no bare npm imports in
// src/client/) — keep it that way; think twice before adding any import.
export default defineConfig({
  entry: { client: 'src/client/index.ts' },
  format: ['cjs'],
  outDir: 'lib',
  clean: false,
  sourcemap: false,
  external: ['react', 'react/jsx-runtime'],
  target: 'chrome120',
  minify: true,
  outExtensions: () => ({ js: '.cjs' }),
})
