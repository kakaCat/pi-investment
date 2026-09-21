#!/usr/bin/env node
/**
 * 分片库构建期生成器（REQ-422af1 t2；t7 扩展 light/heavy 与 overrides）。
 *
 * 为什么构建期内联：这批文本要长期人工打磨（md 作者态），但"确定性注入"要求编译进
 * 产物、不许运行时读盘（本仓有过"读盘失败静默降级"的事故）。两者用"生成 + 门禁"连接。
 *
 * 纪律（REQ-422af1 硬约束）：生成器**只做整文件模板拼接**（banner + 逐条记录 + footer），
 * 不得对 md 内容做逐行缩进/替换等字符串变换；md 正文逐字节原样进 JSON 字符串字面量。
 *
 * 路径 → 元数据约定：
 *   common/<name>.md                  → (*, *, *)          priority=floor
 *   <stage>/default.md                → (stage, *, *)      priority=floor（P0 兜底档；P1 起六节点已分化，不再使用）
 *   <stage>/light.md                  → (stage, light, *)  priority=floor（节点轻档，不可裁）
 *   <stage>/heavy.md                  → (stage, heavy, *)  priority=floor（heavy 主 skill 原文，不裁）
 *   <stage>/<difficulty>/overrides.md → (stage, 难度, *)   priority=floor（overrides 附加片段，不可裁）
 *   <stage>/<category>.md             → (stage, *, 类型)   priority=10（P2 类型档，可裁）
 *   <stage>/<difficulty>/<cat>.md     → (stage, 难度, 类型) priority=10（P2 类型档精确档；本仓由
 *                                        生成器自 <stage>/<category>.md **合成 include-only 路由壳**，
 *                                        见 typeRouteShells()——不要求手写 72 份重复内容）
 *
 * vendor 原文：vendor/superpowers/<skill>/SKILL.md 是 heavy 主 skill 的**唯一事实源**；
 * fragments/<stage>/heavy.md 必须与其逐字节一致（映射见 VENDOR_MAIN_SKILLS，门禁在
 * check-prompt-fragments.mjs 与 tests/prompt-tiers.test.ts）。运行时不读盘：heavy.md 被内联。
 *
 * 类型档的 ①/③ 双可达（P2/t8）：类型差异正文只写一份，落在 <stage>/<category>.md（回退链第 ③ 层
 * 的 (stage,*,category)）。但回退链是"取首个命中层"——若只在 ③ 注册，② 的 light/heavy 会先命中，
 * 类型档永远拿不到；若只在 ① 注册，① 命中又会挤掉 ② 的节点内容。故生成器为每个类型档按难度
 * 各合成一个 **include-only 路由壳** (stage, 难度, 类型)：壳自身 text 为空（assembleText 跳过空
 * 片段），只 include「节点难度档（+ heavy/overrides）」与「类型档正文」。这样：
 *   - (stage,difficulty,category) 命中 ① —— 注入 = 节点内容 + 类型差异；
 *   - (stage,*,category)         命中 ③ —— 类型档仍是可用分片，且被 include 命中，不是孤岛。
 *
 * 用法：node scripts/inline-prompt-fragments.mjs
 */

import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, join, relative } from 'node:path'

export const STAGES = ['brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived']
export const DIFFICULTIES = ['light', 'heavy']
export const CATEGORIES = ['feature', 'bug', 'doc', 'refactor', 'spike', 'chore']

const HERE = dirname(fileURLToPath(import.meta.url))
export const PKG_ROOT = join(HERE, '..')
export const FRAGMENTS_DIR = join(PKG_ROOT, 'src/domain/prompt/fragments')
export const GENERATED_FILE = join(PKG_ROOT, 'src/domain/prompt/generated/fragments.ts')
export const GENERATED_REL = 'src/domain/prompt/generated/fragments.ts'
export const VENDOR_DIR = join(PKG_ROOT, 'src/domain/prompt/vendor/superpowers')

/**
 * 节点 → heavy 主 skill（vendor 原文来源）。decomposing 故意缺席：
 * superpowers 14 份 skill 里没有"拆分/任务 DAG/卡质量"的对应物（对照结论 §4.5 口径例外），
 * 其 heavy 为自写完整档，不做"与 vendor 原文逐字一致"断言。
 */
// 2026-09-21 用户裁定：设计阶段只写设计文档、不写计划——design 自本表移除，
// 其 heavy 改为自写档（writing-plans 的写计划纪律迁往 decomposing 档），不再镜像 vendor。
export const VENDOR_MAIN_SKILLS = {
  brainstorming: 'brainstorming',
  implementing: 'executing-plans',
  accepting: 'verification-before-completion',
  archived: 'finishing-a-development-branch',
}

/** 递归列出 fragments 下的 .md（按相对路径字典序，保证确定性）。 */
export function listFragmentFiles(dir = FRAGMENTS_DIR) {
  const out = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name)
    if (entry.isDirectory()) out.push(...listFragmentFiles(p))
    else if (entry.name.endsWith('.md')) out.push(p)
  }
  return out.sort()
}

/** 路径去 .md = 分片 id。 */
export function fragmentIdOf(file) {
  return relative(FRAGMENTS_DIR, file).replace(/\\/g, '/').replace(/\.md$/, '')
}

/** id → 元数据（stage/difficulty/category/priority）；非法路径直接抛错（响亮失败）。 */
export function parseFragmentId(id) {
  const segs = id.split('/')
  if (segs.some((s) => s.length === 0)) throw new Error('分片 id 含空路径段：' + id)
  if (segs[0] === 'common') {
    if (segs.length !== 2) throw new Error('common/ 只允许一层：' + id)
    return { id, stage: '*', difficulty: '*', category: '*', priority: 'floor' }
  }
  const stage = segs[0]
  if (!STAGES.includes(stage)) throw new Error('未知节点目录：' + id + '（合法：common 或 ' + STAGES.join('/') + '）')
  if (segs.length === 2) {
    const leaf = segs[1]
    if (leaf === 'default') return { id, stage, difficulty: '*', category: '*', priority: 'floor' }
    if (DIFFICULTIES.includes(leaf)) return { id, stage, difficulty: leaf, category: '*', priority: 'floor' }
    if (CATEGORIES.includes(leaf)) return { id, stage, difficulty: '*', category: leaf, priority: 10 }
    throw new Error('未知分片叶子名：' + id)
  }
  if (segs.length === 3) {
    if (!DIFFICULTIES.includes(segs[1])) throw new Error('三段路径第 2 段须为难度：' + id)
    if (segs[2] === 'overrides') return { id, stage, difficulty: segs[1], category: '*', priority: 'floor' }
    if (!CATEGORIES.includes(segs[2])) throw new Error('三段路径第 3 段须为类型或 overrides：' + id)
    return { id, stage, difficulty: segs[1], category: segs[2], priority: 10 }
  }
  throw new Error('分片路径最多三段：' + id)
}

/**
 * 类型档的 ① 路由壳（合成记录，不对应磁盘文件）：
 *   <stage>/<difficulty>/<category>  →  (stage, 难度, 类型)  priority=10, text='',
 *                                       include=[<stage>/<difficulty>(,<stage>/<difficulty>/overrides), <stage>/<category>]
 *
 * 为什么需要：回退链"取首个命中层"——只注册在 ③ 的类型档会被 ② 的 light/heavy 永久遮住；
 * 只注册在 ① 又会挤掉 ② 的节点内容。壳把两边 include 起来，① 就能同时注入节点内容与类型差异。
 *
 * 依赖缺失即抛错（响亮失败）：壳 include 的难度档必须真实存在，否则 resolve 期 expandIncludes 会炸。
 */
export function typeRouteShells(stage, difficulty, category) {
  const nodeId = stage + '/' + difficulty
  if (!existsSync(join(FRAGMENTS_DIR, stage, difficulty + '.md'))) {
    throw new Error('类型档路由壳缺少节点难度档：' + nodeId + '.md（' + stage + '/' + category + '.md 依赖它）')
  }
  const include = [nodeId]
  // <difficulty>/overrides.md（floor）若存在则一并挂上——**不限于 heavy**。
  // 文件头约定即 <stage>/<difficulty>/overrides.md → (stage, 难度, *) priority=floor；
  // 原先只挂 heavy 是历史遗留（此前只有 heavy 有 overrides），会让 light 档 overrides 变成孤岛
  // （tests/prompt-gates.test.ts 门禁 4「每个分片至少被一条路由命中」会红）。
  if (existsSync(join(FRAGMENTS_DIR, stage, difficulty, 'overrides.md'))) {
    include.push(stage + '/' + difficulty + '/overrides')
  }
  include.push(stage + '/' + category)
  return { id: stage + '/' + difficulty + '/' + category, stage, difficulty, category, priority: 10, text: '', include }
}

/** 读全部 md（**逐字节，不 trim**）→ 记录数组（按 id 字典序）+ 类型档 ① 路由壳。 */
export function readFragments() {
  const records = []
  const seen = new Set()
  for (const file of listFragmentFiles()) {
    const id = fragmentIdOf(file)
    if (seen.has(id)) throw new Error('分片 id 重复：' + id)
    seen.add(id)
    const meta = parseFragmentId(id)
    records.push({ ...meta, text: readFileSync(file, 'utf8') })
    // <stage>/<category>.md（③）→ 按难度合成 ① 路由壳，避免类型档成为孤岛或挤掉节点内容。
    const segs = id.split('/')
    if (segs.length === 2 && meta.stage !== '*' && CATEGORIES.includes(segs[1])) {
      for (const difficulty of DIFFICULTIES) {
        const shell = typeRouteShells(meta.stage, difficulty, meta.category)
        if (seen.has(shell.id)) throw new Error('类型档路由壳 id 与已有分片冲突：' + shell.id)
        seen.add(shell.id)
        records.push(shell)
      }
    }
  }
  records.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
  return records
}

/** 读取某 skill 的 vendor 原文（缺失抛错，不静默）。 */
export function readVendorSkill(skill) {
  const file = join(VENDOR_DIR, skill, 'SKILL.md')
  if (!existsSync(file)) throw new Error('vendor 原文缺失：' + file)
  return readFileSync(file, 'utf8')
}

/**
 * heavy.md ↔ vendor 原文一致性检查：返回问题清单（空数组 = 通过）。
 * vendor/ 是唯一事实源，fragments/<stage>/heavy.md 是它的逐字节镜像；漂移即报错。
 */
export function vendorMirrorProblems() {
  const problems = []
  for (const [stage, skill] of Object.entries(VENDOR_MAIN_SKILLS)) {
    const mirrored = join(FRAGMENTS_DIR, stage, 'heavy.md')
    if (!existsSync(mirrored)) {
      problems.push('fragments/' + stage + '/heavy.md 不存在（应由 vendor/' + skill + '/SKILL.md 镜像）')
      continue
    }
    const actual = readFileSync(mirrored, 'utf8')
    const expected = readVendorSkill(skill)
    if (actual !== expected) {
      problems.push('fragments/' + stage + '/heavy.md 与 vendor/' + skill + '/SKILL.md 不一致（'
        + Buffer.byteLength(actual, 'utf8') + ' vs ' + Buffer.byteLength(expected, 'utf8') + ' bytes）')
    }
  }
  return problems
}

/** 生成整份 TS 源码（纯函数，不落盘——check 脚本复用做内存比对）。 */
export function buildFragmentsSource() {
  const records = readFragments()
  const lines = []
  lines.push('/**')
  lines.push(' * 分片库构建期生成物（REQ-422af1 t2；t7 六节点 light/heavy）—— 由 scripts/inline-prompt-fragments.mjs 生成。')
  lines.push(' *')
  lines.push(' * **不要手改本文件**：改 fragments 目录下的 .md 源后重跑生成器；')
  lines.push(' * 门槛 tests/prompt-gates.test.ts 第 6 条（源/产物同步）会在不一致时变红。')
  lines.push(' * md 正文逐字节内联（不 trim、不做逐行变换）。')
  lines.push(' *')
  lines.push(' * P1 说明：六节点各有 light/heavy（heavy 主 skill 原文不裁；overrides 与 common/iron-rules 为 floor）；')
  lines.push(' * fragments/<stage>/heavy.md 是 vendor/ 原文的逐字节镜像，由同步门禁与 tests/prompt-tiers.test.ts 双保险。')
  lines.push(' *')
  lines.push(' * P2 说明：六节点各有 <category> 类型档（(stage,*,category) ③），并由生成器按难度合成 include-only')
  lines.push(' * 路由壳（(stage,难度,category) ①）——壳无正文，只把节点内容与类型档串起来（见 typeRouteShells）。')
  lines.push(' */')
  lines.push('')
  lines.push('export interface GeneratedFragment {')
  lines.push('  readonly id: string')
  lines.push('  readonly stage: string')
  lines.push('  readonly difficulty: string')
  lines.push('  readonly category: string')
  lines.push("  readonly priority: number | 'floor'")
  lines.push('  readonly text: string')
  lines.push('  readonly include?: readonly string[]')
  lines.push('}')
  lines.push('')
  lines.push('export const GENERATED_FRAGMENTS: readonly GeneratedFragment[] = [')
  // 一条记录一行：t8 起记录数 = 节点档 + 类型档 + 类型档路由壳（126 条），多行展开会越过
  // tests/size-budget.test.ts 的 400 行硬上限。这里仍是"整文件模板拼接"——text 依旧逐字节原样
  // 走 JSON.stringify，不涉及任何逐行字符串变换。
  for (const r of records) {
    const fields = [
      'id: ' + JSON.stringify(r.id),
      'stage: ' + JSON.stringify(r.stage),
      'difficulty: ' + JSON.stringify(r.difficulty),
      'category: ' + JSON.stringify(r.category),
      'priority: ' + JSON.stringify(r.priority),
      'text: ' + JSON.stringify(r.text),
    ]
    if (r.include !== undefined) fields.push('include: ' + JSON.stringify(r.include))
    lines.push('  { ' + fields.join(', ') + ' },')
  }
  lines.push(']')
  lines.push('')
  return lines.join('\n')
}

function main() {
  const source = buildFragmentsSource()
  mkdirSync(dirname(GENERATED_FILE), { recursive: true })
  writeFileSync(GENERATED_FILE, source, 'utf8')
  const n = readFragments().length
  const problems = vendorMirrorProblems()
  if (problems.length > 0) {
    console.error('[inline-prompt-fragments] vendor 镜像不一致：')
    for (const p of problems) console.error('  - ' + p)
    process.exit(1)
  }
  console.log('[inline-prompt-fragments] wrote ' + GENERATED_REL + ' (' + n + ' fragments, ' + source.length + ' bytes)')
}

if (process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href) main()
