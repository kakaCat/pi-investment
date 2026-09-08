import { defineConfig } from 'tsdown'

// Client-half bundle config. react is EXTERNAL (served by the DSH shell's
// module-loader seed); page-kit is BUNDLED via noExternal — it's a shared
// workspace util lib, not a dsh module, and the shell loader cannot resolve
// plugin workspace deps at runtime (missing noExternal → require throws →
// client half fails to load → sidebar button disappears).
export default defineConfig({
  entry: { client: 'src/client/index.ts' },
  format: ['cjs'],
  outDir: 'lib',
  clean: false,
  sourcemap: false,
  noExternal: [/@pi-investment\/page-kit/],
  external: ['react', 'react/jsx-runtime'],
  target: 'chrome120',
  minify: true,
  outExtensions: () => ({ js: '.cjs' }),
})
