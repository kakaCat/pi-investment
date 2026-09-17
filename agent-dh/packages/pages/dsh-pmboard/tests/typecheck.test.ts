/**
 * 类型门禁：本包必须能被 `tsc --noEmit` 零错误通过（覆盖 src 与 tests）。
 *
 * 为什么要有这道门（返工根因，别删）：REQ-47939a 重构后 `src/http/routers/stages.ts` 引用了两个
 * **不存在的符号**（`OPEN_STATUSES` / `TASK_ORDER`）→ `GET /dashboard/api/reqboard/session/:id/progress`
 * 运行时 ReferenceError → HTTP 500 → 会话框流程节点不显示。它之所以能一路到线上，是因为本包
 * **没有 tsconfig、也没有类型检查门禁**：tsx 直接剥类型运行、vitest 不跑 tsc，所以任何"引用了
 * 不存在的名字 / 参数类型不匹配"都零成本通关。本测试把这道缺口补上。
 *
 * 口径：
 *  - 真跑 `tsc --noEmit -p tsconfig.json`（不是源码级 mock，也不是只查少量文件）；
 *  - 只把**本包 src/ 与 tests/ 下**的错误计入失败（跨包/依赖的既有历史错误不归本包）；
 *  - 超时 120s（首次冷启动 + 全量 program 构建），失败时把前若干条错误打进断言消息。
 */
import { describe, it, expect } from 'vitest'
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const pkgRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const tsconfigPath = join(pkgRoot, 'tsconfig.json')
const require = createRequire(import.meta.url)

/** tsc 入口：走本包 devDependency 的 typescript（不依赖 npx 联网/全局安装）。 */
const tscJs = join(dirname(require.resolve('typescript')), 'tsc.js')

interface TypeError { file: string; line: number; col: number; code: string; message: string }

/** 跑一次真实 tsc，返回本包 src/tests 下的类型错误。 */
function runTypecheck(): { errors: TypeError[]; timedOut: boolean; raw: string } {
  const res = spawnSync(
    process.execPath,
    [tscJs, '--noEmit', '-p', 'tsconfig.json', '--pretty', 'false'],
    { cwd: pkgRoot, encoding: 'utf8', timeout: 120_000, maxBuffer: 32 * 1024 * 1024 },
  )
  const raw = ((res.stdout ?? '') + (res.stderr ?? '')).trim()
  const errors: TypeError[] = []
  for (const line of raw.split('\n')) {
    const m = line.match(/^(.*?)\((\d+),(\d+)\): error (TS\d+): (.*)$/)
    if (m === null) continue
    const file = relative(pkgRoot, resolve(pkgRoot, m[1]))
    if (file.startsWith('src') || file.startsWith('tests')) {
      errors.push({ file, line: Number(m[2]), col: Number(m[3]), code: m[4], message: m[5] })
    }
  }
  const timedOut = res.error !== undefined || res.signal === 'SIGTERM'
  return { errors, timedOut, raw }
}

describe('类型门禁：tsc --noEmit 零错误（src 与 tests）', () => {
  it('tsconfig 覆盖 src 与 tests（不允许只查少量文件蒙过门禁）', () => {
    expect(existsSync(tsconfigPath)).toBe(true)
    const cfg = JSON.parse(readFileSync(tsconfigPath, 'utf8')) as { include?: string[] }
    expect(cfg.include ?? []).toContain('src/**/*.ts')
    expect(cfg.include ?? []).toContain('tests/**/*.ts')
    expect(existsSync(join(pkgRoot, 'src'))).toBe(true)
    expect(existsSync(join(pkgRoot, 'tests'))).toBe(true)
  })

  it('src 与 tests 下 0 个类型错误', () => {
    const { errors, timedOut, raw } = runTypecheck()
    const head = errors.slice(0, 15)
      .map(e => `${e.file}(${e.line},${e.col}): ${e.code}: ${e.message}`)
      .join('\n')
    expect(timedOut, 'tsc 未在 120s 内完成（超时/被杀）：\n' + raw.slice(0, 2000)).toBe(false)
    expect(errors.length, `tsc 报告 ${errors.length} 个类型错误（前 15 条）：\n${head}`).toBe(0)
  }, 180_000)
})
