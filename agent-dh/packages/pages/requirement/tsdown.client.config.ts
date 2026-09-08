import { defineConfig } from 'tsdown'

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
