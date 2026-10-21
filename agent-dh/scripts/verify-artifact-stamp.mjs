#!/usr/bin/env node
/**
 * verify-artifact-stamp.mjs — 校验「浏览器 shell 产物」与「当前安装的框架版本」是否一致。
 *
 * 这是 2026-10-21 事故（dist 由 0.2.1-rc.2 构建、主机却跑 0.1.6-alpha.2 → React #130）
 * 的机械闸门：构建时由 apps/web/vite.config.ts 写入 dist/.build-info.json，
 * 本脚本在**启动 / 发版 / 巡检**三个入口比对：
 *   - pnpm-lock.yaml 的 sha256（谁动过依赖）
 *   - 9 个核心 @deepseek-ai 包的实际解析版本（谁换过版本）
 *   - 入口 JS 的 sha256（产物有没有被替换/损坏）
 *
 * 退出码：
 *   0 = 一致（或产物不存在但调用方明确允许——由调用方处理）
 *   1 = 不一致（必须重建：./scripts/restart-with-build.sh）
 *   2 = 无法校验（stamp 缺失/损坏）——调用方自行决定是警告还是拒绝
 *
 * 用法：
 *   node scripts/verify-artifact-stamp.mjs [--verbose] [--json]
 */

import { createHash } from 'node:crypto'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const DIST = join(ROOT, 'apps/web/dist')
const STAMP_PATH = join(DIST, '.build-info.json')
const LOCKFILE = join(ROOT, 'pnpm-lock.yaml')
const verbose = process.argv.includes('--verbose')
const json = process.argv.includes('--json')

const sha256File = (file) => createHash('sha256').update(readFileSync(file)).digest('hex')

function packageVersionAt(entryFile) {
  let dir = dirname(entryFile)
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(dir, 'package.json')
    if (existsSync(candidate)) {
      const pkg = JSON.parse(readFileSync(candidate, 'utf8'))
      if (pkg.name === undefined || pkg.version === undefined) return null
      return { name: pkg.name, version: pkg.version }
    }
    const parent = dirname(dir)
    if (parent === dir) return null
    dir = parent
  }
  return null
}

function resolveVersion(name) {
  for (const base of [join(ROOT, 'apps/web/package.json'), join(ROOT, 'package.json')]) {
    try {
      const req = createRequire(base)
      const entry = req.resolve(name)
      const found = packageVersionAt(entry)
      if (found !== null && found.name === name) return found.version
    } catch {
      // 部分包的 exports 不暴露 package.json；继续尝试下一种解析
    }
    try {
      const req = createRequire(base)
      const entry = req.resolve(`${name}/package.json`)
      return JSON.parse(readFileSync(entry, 'utf8')).version
    } catch {
      // try next base
    }
  }
  // 深层依赖不在 workspace 根 node_modules 里：回落到 pnpm store 扫描（可能多版本）
  const store = join(ROOT, 'node_modules/.pnpm')
  try {
    const prefix = `@deepseek-ai+${name.replace('@deepseek-ai/', '')}@`
    const versions = readdirSync(store)
      .filter((dir) => dir.startsWith(prefix))
      .map((dir) => dir.slice(prefix.length).split('_')[0])
      .filter((version) => version.length > 0)
    const unique = [...new Set(versions)].sort()
    if (unique.length === 0) return 'MISSING'
    return unique.join('|')
  } catch {
    return 'MISSING'
  }
}

function fail(reason, details = {}) {
  if (json) {
    console.log(JSON.stringify({ ok: false, reason, exit: 1, ...details }))
  } else {
    console.error(`❌ 产物与依赖版本不一致：${reason}`)
    for (const line of details.lines ?? []) console.error(`   ${line}`)
    console.error('   处置：./scripts/restart-with-build.sh（它会重建 dist 并重启，四层体检兜底）')
  }
  process.exit(details.exit ?? 1)
}

if (!existsSync(STAMP_PATH)) {
  if (json) console.log(JSON.stringify({ ok: false, reason: 'stamp-missing', exit: 2 }))
  else console.error(`⚠️  未找到构建指纹：${STAMP_PATH}（无法判断产物新鲜度；请重建一次以建立基线）`)
  process.exit(2)
}

let stamp
try {
  stamp = JSON.parse(readFileSync(STAMP_PATH, 'utf8'))
} catch (error) {
  if (json) console.log(JSON.stringify({ ok: false, reason: 'stamp-unreadable', exit: 2, error: String(error) }))
  else console.error(`⚠️  构建指纹损坏：${STAMP_PATH}（${String(error)}）`)
  process.exit(2)
}

if (stamp.schema !== 1 || typeof stamp.packages !== 'object' || stamp.packages === null) {
  if (json) console.log(JSON.stringify({ ok: false, reason: 'stamp-schema', exit: 2, schema: stamp.schema }))
  else console.error(`⚠️  构建指纹版本不受支持（schema=${stamp.schema}）；请重建一次。`)
  process.exit(2)
}

if (!existsSync(LOCKFILE)) fail('缺少 pnpm-lock.yaml', { lines: [LOCKFILE] })
const lockNow = sha256File(LOCKFILE)
if (stamp.lockfileSha256 !== lockNow) {
  fail('pnpm-lock.yaml 已变化（依赖被安装/改动过，dist 未重建）', {
    lines: [
      `构建时 lockfile: ${stamp.lockfileSha256}`,
      `当前   lockfile: ${lockNow}`,
      `构建时间: ${stamp.builtAt}${stamp.gitRev ? ` @ ${String(stamp.gitRev).slice(0, 9)}` : ''}`,
    ],
  })
}

const diffs = []
for (const [name, built] of Object.entries(stamp.packages)) {
  const now = resolveVersion(name)
  // store 扫描可能同时看到历史版本副本（如 0.1.6 残留）：只要构建时的版本仍在
  // 已安装集合里就视为一致；真正的版本切换由 lockfile 哈希兜底检测。
  const nowSet = now.split('|')
  if (now !== built && !nowSet.includes(built)) diffs.push(`${name}: 构建时 ${built} → 当前 ${now}`)
}
if (diffs.length > 0) {
  fail('核心框架包版本已变化（换了版本但 dist 未重建）', {
    lines: diffs,
  })
}

if (stamp.entry) {
  const entryPath = join(DIST, stamp.entry.file)
  if (!existsSync(entryPath)) {
    fail(`入口文件缺失：${stamp.entry.file}`, {})
  }
  const entryNow = sha256File(entryPath)
  if (entryNow !== stamp.entry.sha256) {
    fail(`入口文件内容被替换：${stamp.entry.file}`, {
      lines: [`构建时 sha256: ${stamp.entry.sha256}`, `当前   sha256: ${entryNow}`],
    })
  }
}

if (json) {
  console.log(JSON.stringify({ ok: true, builtAt: stamp.builtAt, gitRev: stamp.gitRev, packages: stamp.packages }))
} else if (verbose) {
  console.log(`✅ 产物指纹一致（构建于 ${stamp.builtAt}${stamp.gitRev ? ` @ ${String(stamp.gitRev).slice(0, 9)}` : ''}）`)
  for (const [name, version] of Object.entries(stamp.packages)) console.log(`   ${name} = ${version}`)
}
process.exit(0)
