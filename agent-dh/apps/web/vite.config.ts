import { defineConfig } from 'vite'
import type { Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'url'

/**
 * 产物指纹：把「这次构建用的是哪一版框架依赖」写进 dist/.build-info.json。
 *
 * 背景（2026-10-21 事故）：`pnpm install` 换过 DSH 版本后没有重建 dist，浏览器侧
 * 仍然是旧版本打包的 shell，与主机侧新版本插件契约对不上 → React #130 插槽崩溃。
 * 仅靠文档纪律无法防止，所以让它可检测：
 *   - 构建时写入 lockfile 哈希 + 核心包版本 + 入口文件哈希；
 *   - scripts/verify-artifact-stamp.py 在启动/发版/巡检时比对当前 node_modules；
 *   - 不一致 = 拒绝启动并提示走 restart-with-build.sh。
 */
const STAMP_SCHEMA = 1
const STAMP_PACKAGES = [
  '@deepseek-ai/dsh',
  '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-tools',
  '@deepseek-ai/dsh-client-web',
  '@deepseek-ai/dsh-web-app',
  '@deepseek-ai/dsh-base',
  '@deepseek-ai/dsh-client-ui-cordis',
  '@deepseek-ai/dsh-client-ui-renderer',
  '@deepseek-ai/dsh-cordis-client-runner',
]

function sha256(file: string): string {
  return createHash('sha256').update(readFileSync(file)).digest('hex')
}

/** Parse the emitted index.html and fingerprint the hashed entry module. */
function entryFingerprint(outDir: string): { file: string; sha256: string } | null {
  const index = join(outDir, 'index.html')
  if (!existsSync(index)) return null
  const html = readFileSync(index, 'utf8')
  const match = /src="\.?\/?(assets\/[^"]+\.js)"/.exec(html)
  if (match === null) return null
  const file = match[1]
  const abs = join(outDir, file)
  return existsSync(abs) ? { file, sha256: sha256(abs) } : null
}

function gitRevision(root: string): string | null {
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch {
    return null
  }
}

function buildStamp(): Plugin {
  let outDir = ''
  let root = ''
  return {
    name: 'agent-dh-build-stamp',
    apply: 'build',
    configResolved(config) {
      root = config.root
      outDir = resolve(config.root, config.build.outDir)
    },
    closeBundle() {
      const requireFromApp = createRequire(join(root, 'package.json'))
      const packages: Record<string, string> = {}
      for (const name of STAMP_PACKAGES) {
        try {
          packages[name] = JSON.parse(readFileSync(requireFromApp.resolve(`${name}/package.json`), 'utf8')).version as string
        } catch {
          packages[name] = 'MISSING'
        }
      }
      // apps/web → agent-dh（pnpm workspace 根，lockfile 真身在这里）
      const repoRoot = resolve(root, '../..')
      const lockfile = join(repoRoot, 'pnpm-lock.yaml')
      const stamp = {
        schema: STAMP_SCHEMA,
        builtAt: new Date().toISOString(),
        gitRev: gitRevision(repoRoot),
        lockfileSha256: existsSync(lockfile) ? sha256(lockfile) : null,
        packages,
        entry: entryFingerprint(outDir),
      }
      writeFileSync(join(outDir, '.build-info.json'), `${JSON.stringify(stamp, null, 2)}\n`)
    },
  }
}

const src = (rel: string): string => fileURLToPath(new URL(rel, import.meta.url))
const STANDALONE_ERROR = 'apps/web is not a standalone application: bare Vite cannot inject window.__DSH_BOOT__. '
  + 'From a repository checkout, run the agent-dh server; '
  + 'For client-plugin HMR, run the server together with `pnpm run dev`.'
const DEFAULT_CLIENT_TITLE = 'Agent-DH'

/** Escape build-time text before placing it in the HTML title element. */
function escapeHtmlText(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** Project the public build title into the initial HTML document. */
function clientDocumentTitle(): Plugin {
  const title = escapeHtmlText(process.env.DSH_CLIENT_TITLE ?? DEFAULT_CLIENT_TITLE)
  return {
    name: 'agent-dh-client-document-title',
    transformIndexHtml(html) {
      return html.replace('<title>Agent-DH</title>', `<title>${title}</title>`)
    },
  }
}

/** Fail before a Vite dev or preview server can expose the boot-manifest-free shell. */
function rejectStandaloneServe(): Plugin {
  return {
    name: 'agent-dh-reject-standalone-web-serve',
    config(_config, env) {
      if (env.command === 'serve') throw new Error(STANDALONE_ERROR)
    },
  }
}

export default defineConfig({
  // Relative asset URLs
  base: './',
  plugins: [
    rejectStandaloneServe(),
    clientDocumentTitle(),
    buildStamp(),
    react(),
  ],
  build: {
    target: 'es2022',
    sourcemap: true,
    rollupOptions: {
      input: {
        index: src('./index.html'),
      },
      output: {
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
  resolve: {
    // One instance per shared npm identity
    dedupe: ['react', 'react-dom'],
    alias: [
      { find: /^node:module$/, replacement: src('./src/node-module-stub.ts') },
    ],
  },
  define: {
    // Browser environment stubs
    'process.versions.node': '"0.0.0"',
    'process.execArgv': '[]',
    'process.env.CORDIS_SHARED': 'undefined',
  },
})
