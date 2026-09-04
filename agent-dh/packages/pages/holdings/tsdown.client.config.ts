import { defineConfig } from 'tsdown'

// Client-half bundle config: one entry (src/client/index.ts) compiled to CJS.
// react is EXTERNAL — never bundled: the DSH web shell's module-loader seed
// resolves require("react") at runtime (react 18.3.1 is served by the shell),
// so bundling our own copy would duplicate React and break hooks. Everything
// else we author is plain TS/DOM, wrapped by scripts/wrap-client.mjs.
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
