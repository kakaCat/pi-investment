#!/usr/bin/env node
/**
 * 源/产物同步门禁（REQ-422af1 t2，门禁 6；t7 追加 vendor 镜像检查）——
 * fragments/**.md 或 vendor 原文改了没重跑生成器/没同步镜像即 exit 1。
 *
 * 口径：
 *   ① 内存重新生成整份 TS 源码，与磁盘上的 generated/fragments.ts **逐字节**比对；
 *   ② fragments/<stage>/heavy.md 必须与 vendor/superpowers/<skill>/SKILL.md **逐字节**一致
 *      （heavy 主 skill 唯一的原文来源，防镜像漂移）。
 * 不一致 / 产物缺失 → 打印原因 → exit 1（响亮失败，不静默通过）。
 * 用法：node scripts/check-prompt-fragments.mjs
 */
import { readFileSync, existsSync } from 'node:fs'
import {
  buildFragmentsSource,
  vendorMirrorProblems,
  GENERATED_FILE,
  GENERATED_REL,
} from './inline-prompt-fragments.mjs'

const vendorProblems = vendorMirrorProblems()
if (vendorProblems.length > 0) {
  console.error('[check-prompt-fragments] FAIL: heavy.md ↔ vendor 原文不一致：')
  for (const p of vendorProblems) console.error('  - ' + p)
  console.error('  请把 vendor/superpowers/<skill>/SKILL.md 原样复制为 fragments/<stage>/heavy.md（逐字节）')
  process.exit(1)
}

const expected = buildFragmentsSource()
if (!existsSync(GENERATED_FILE)) {
  console.error('[check-prompt-fragments] FAIL: 产物不存在，请先跑 node scripts/inline-prompt-fragments.mjs')
  process.exit(1)
}
const actual = readFileSync(GENERATED_FILE, 'utf8')
if (actual !== expected) {
  const at = [...expected].findIndex((ch, i) => ch !== actual[i])
  console.error('[check-prompt-fragments] FAIL: ' + GENERATED_REL + ' 与 fragments/**.md 不一致（首个差异偏移 ' + at + '）')
  console.error('  expected ' + expected.length + ' bytes / actual ' + actual.length + ' bytes')
  console.error('  源或产物被单独改过——请重跑 node scripts/inline-prompt-fragments.mjs')
  process.exit(1)
}
console.log('[check-prompt-fragments] OK: ' + GENERATED_REL + ' 与 fragments/**.md 一致；heavy.md ↔ vendor 原文逐字节一致')
