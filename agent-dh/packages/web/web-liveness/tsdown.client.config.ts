import { defineConfig } from 'tsdown'

// Client-half bundle config: one entry (src/client/index.ts) compiled to CJS,
// then wrapped by scripts/wrap-client.mjs into a __ModuleLoader__ registration.
// react is EXTERNAL as a matter of house style (the web shell seeds it); this
// plugin renders plain DOM and imports nothing from React.
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
