/**
 * 队列依赖归一化迁移脚本（REQ-260929010300-dbf9 · 用户 2026-09-29 裁定 B「数据侧」）。
 *
 * 背景：拆分落库时每张卡写的是**全部前置**（传递闭包），于是存量 queue.json 里普遍存在
 * 「A→B、B→C、A→C」三角形（线上实测 55 份队列 / 卡片层 646 条边里 98 条可归约）。
 * 写入侧已收敛（见 `src/repositories/QueueTaskStore.ts` 的 `recompute` 与
 * `src/domain/queue/transitiveReduction.ts`）；本脚本负责把**存量文件本身**也收敛成
 * 「dependsOn 只写直接前置」，并整份重算 layer/edges/layers/ready。
 *
 * 归一化不改变执行序与可开工集（传递归约保持可达性）——它只去掉**存储冗余**。
 *
 * ⚠️ 运行时机：写完后**运行中的实例内存里仍是旧缓存**（QueueTaskStore 按需求缓存，
 * 只在写路径重读）。故 apply 后需重启实例（`./scripts/start.sh`）让看板读到新数据。
 * 读取侧画布自身有传递归约，所以重启前视觉不变，不会"改完反而更花"。
 *
 * 用法（默认 dry-run，不写盘）：
 *   npx tsx scripts/normalize-queue-deps.ts                      # 全量 dry-run
 *   npx tsx scripts/normalize-queue-deps.ts --req REQ-xxx         # 单个需求 dry-run（可重复）
 *   npx tsx scripts/normalize-queue-deps.ts --req REQ-xxx --apply # 真写
 *   npx tsx scripts/normalize-queue-deps.ts --apply               # 全量真写
 *   --root <dir>  工作区根（默认从脚本位置推出 <agent-dh>）
 */
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'
import { JsonQueueRepository } from '../src/repositories/QueueRepository.js'
import { countRedundantDependencies, normalizeQueueFile } from '../src/domain/queue/normalizeQueue.js'

interface Failure { requirementId: string; reason: string }

const args = process.argv.slice(2)
const apply = args.includes('--apply')
const reqIds: string[] = []
for (let i = 0; i < args.length; i += 1) {
  if (args[i] === '--req' && args[i + 1] !== undefined) reqIds.push(args[i + 1] as string)
}
const rootArg = args.indexOf('--root')
const scriptDir = dirname(fileURLToPath(import.meta.url))
// scripts → dsh-pmboard → web → packages → agent-dh（4 级）
const workspaceRoot = rootArg >= 0 ? resolve(args[rootArg + 1] as string) : resolve(scriptDir, '../../../..')

const repo = new JsonQueueRepository({ workspaceRoot })
const nowIso = () => new Date().toISOString()

const ids = reqIds.length > 0 ? reqIds : await repo.listRequirementIds()
const failures: Failure[] = []
let scanned = 0
let missing = 0
let clean = 0
let changed = 0
let saved = 0
let removedTotal = 0

for (const id of ids) {
  scanned += 1
  let file
  try {
    file = await repo.load(id)
  } catch (error) {
    failures.push({ requirementId: id, reason: '读失败：' + (error as Error).message })
    continue
  }
  if (file === undefined) {
    missing += 1 // 无队列文件 / 校验未通过（repo.load 两种情况都返回 undefined）
    continue
  }
  const removed = countRedundantDependencies(file)
  if (removed === 0) {
    clean += 1
    continue
  }
  changed += 1
  removedTotal += removed
  console.log(`[dry-run] ${id}: 可归约 ${removed} 条依赖（tasks=${file.tasks.length}）`)
  if (!apply) continue
  try {
    const next = { ...normalizeQueueFile(file), updated_at: nowIso() }
    await repo.save(id, next)
    saved += 1
    console.log(`[applied] ${id}: 已写回（edges=${next.edges.length}, layers=${next.layers.length}, ready=${next.ready.length}）`)
  } catch (error) {
    failures.push({ requirementId: id, reason: '写失败：' + (error as Error).message })
  }
}

console.log('')
console.log(apply ? '=== 迁移完成（--apply）===' : '=== 预演完成（dry-run；加 --apply 才会写盘）===')
console.log(`工作区根：${workspaceRoot}`)
console.log(`扫描 ${scanned} 个需求：无队列 ${missing} / 已直接前置 ${clean} / 需归约 ${changed} / 已写回 ${saved}`)
console.log(`合计可归约依赖：${removedTotal} 条`)
if (failures.length > 0) {
  console.error(`失败 ${failures.length} 个：`)
  for (const f of failures) console.error(`  - ${f.requirementId}: ${f.reason}`)
  process.exit(1)
}
