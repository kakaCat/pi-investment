/**
 * t17 端到端验收（REQ-260927202051-f6df · 整体验收标准 #4）。
 *
 * 「新建需求 → 拆分 → 队列生成且**台账无新任务** → 推进任务 → 队列 ready 更新」——**一条真实连续链**，
 * 全程走**真实用例入口 + 真实仓储/文件系统**（`JsonLedgerRepository` / `FileDocRepository` /
 * `JsonQueueRepository` + `QueueTaskStore`），在 `os.tmpdir()` 的独立工作区里跑，
 * **不碰**真实仓库 `docs/` 与 `.dsh-data/`（活台账零接触）。
 *
 * 走过的真实入口（逐段，非手工拼装）：
 *   1. `executeCreateRequirement`（reqboard_create）→ 立项（台账 draft）
 *   2. `executeMoveRequirement` → brainstorming
 *   3. `submitRequirementArtifact` + `askConfirm(target=artifact, kind=requirement)` → design
 *   4. `submitDesignArtifacts` + `askConfirm(target=artifact, kind=design)` → 设计确认
 *   5. `executeMoveRequirement` → decomposing
 *   6. `submitPlanArtifact`（拆分计划提交，含 FR↔计划 key 覆盖对照表）
 *   7. `askConfirm(target=plan)` → **「计划批准即落库」那条真实路径**（confirm-settle 的门合并分支
 *      → `landPlanTasks` 唯一落库实现）→ 需求 implementing + 任务卡落 `queue.json`
 *   8. `executeReportTask` + `executeMoveTask` → 真实状态推进（走完 legacy 五段合法边）
 *   9. 断言队列 `ready` 随状态更新、台账需求侧状态同步（rollup）
 *
 * 台账判据用**语义级** `'tasks' in ledger === false`（不是 `grep '"tasks"'`：台账是单行 compact JSON
 * 且 `requirements[].plan.tasks` 恒存在，grep 会**假绿**）。
 */
import { createHash } from 'node:crypto'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { JsonQueueRepository, queueRelativePath } from '../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../src/repositories/QueueTaskStore.js'
import { DEFAULT_CONFIRM_OPTIONS } from '../src/domain/text/labels.js'
import { FakeQuestions, FakeSession, FixedClock, SeqIds } from './application/harness.js'
import type { UseCaseDeps } from '../src/application/ports.js'
import { executeCreateRequirement } from '../src/application/use-cases/CreateRequirement.js'
import { executeMoveRequirement } from '../src/application/use-cases/MoveRequirement.js'
import { submitRequirementArtifact, submitPlanArtifact } from '../src/application/use-cases/SubmitArtifact.js'
import { submitDesignArtifacts } from '../src/application/use-cases/SubmitDesignArtifacts.js'
import { askConfirm } from '../src/application/use-cases/AskConfirm.js'
import { executeReportTask } from '../src/application/use-cases/ReportTask.js'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { executeSubtask } from '../src/application/use-cases/ExecuteTask.js'

const WINDOW = 'session-w-001'
const EXEC = { agent: { id: WINDOW } }

const roots: string[] = []
afterEach(() => { for (const r of roots.splice(0)) rmSync(r, { recursive: true, force: true }) })

/** 台账文件解析（**语义级**判据的载体；不是 grep 文本）。 */
function readLedger(file: string): Record<string, unknown> {
  return JSON.parse(readFileSync(file, 'utf8')) as Record<string, unknown>
}
const hasTasksKey = (file: string): boolean => Object.prototype.hasOwnProperty.call(readLedger(file), 'tasks')

function makeRealDeps(root: string) {
  const clock = new FixedClock()
  const docs = new FileDocRepository({ workspaceRoot: root })
  const repo = new JsonLedgerRepository({ file: join(root, 'dsh-reqboard.json') })
  const queueRepo = new JsonQueueRepository({ workspaceRoot: root })
  const taskStore = new QueueTaskStore({ repo: queueRepo, now: () => clock.t })
  const questions = new FakeQuestions()
  const deps = {
    repo, docs, clock, ids: new SeqIds(), session: new FakeSession(), questions, taskStore, doneThrottleMs: 0,
  } as unknown as UseCaseDeps
  return { deps, repo, docs, queueRepo, clock, questions, ledgerFile: join(root, 'dsh-reqboard.json') }
}

const REQ_DOC = [
  '# 测试需求', '',
  '## 边界', '只做本链验证。', '',
  '## 问题', '任务存储搬家后无人跑过整条链。', '',
  '## 成功标准', '一条链跑到底。', '',
  '## 产品定义', '端到端验收脚本。', '',
  '## 用户与角色', 'agent 窗口。', '',
  '## 功能点', '',
  '- **FR-1: 端到端链**：新建 → 拆分 → 队列 → 推进 → ready 更新', '',
].join('\n')

/** 拆分计划文档：覆盖对照表把 FR-1 映到**计划 key**（表头须含「需求条款」与「任务」两列）。 */
const PLAN_DOC = [
  '# 拆分（decomposition）', '',
  '## §1 RTM 覆盖对照表（需求条款 ↔ 接收任务）', '',
  '| 需求条款 | 接收任务 |',
  '|---|---|',
  '| FR-1 | t1 |',
  '| FR-1 | t2 |', '',
].join('\n')

const PLAN_TASKS = [
  { key: 't1', title: '卡一', acceptance: '跑 npx vitest run a.test.ts 看到通过', implementation: '改 src/a.ts', description: 'd1' },
  { key: 't2', title: '卡二', acceptance: '跑 npx vitest run b.test.ts 看到通过', implementation: '改 src/b.ts', description: 'd2', depends_on: ['t1'] },
]

describe('t17 端到端：新建需求 → 拆分落队列 → 台账零新增 → 推进 → ready 更新', () => {
  it('一条真实连续链跑到底（真实仓储 + 临时工作区）', async () => {
    const root = mkdtempSync(join(tmpdir(), 't17-e2e-'))
    roots.push(root)
    const { deps, repo, docs, questions, ledgerFile } = makeRealDeps(root)
    await repo.load()

    // ── ① 真实立项（reqboard_create 用例入口）──────────────────────────────
    const created = await executeCreateRequirement(deps, {
      title: '端到端链验证需求', category: 'feature', summary: 's', reason: 'r',
    }, EXEC) as { requirement_id: string; status: string }
    const reqId = created.requirement_id
    expect(reqId).toMatch(/^REQ-/)
    console.log('[t17] ① 立项：', reqId, '状态', created.status)

    // ── ② 需求文档 → brainstorming → 产物确认（G1）→ design ────────────────
    await docs.write('docs/requirements/' + reqId + '/requirement.md', REQ_DOC)
    await executeMoveRequirement(deps, { requirement_id: reqId, to: 'brainstorming' }, EXEC)
    await submitRequirementArtifact(deps, {
      requirement_id: reqId, path: 'docs/requirements/' + reqId + '/requirement.md', summary: '需求文档',
    }, EXEC)
    questions.answers = [{ selected: [DEFAULT_CONFIRM_OPTIONS[0] as string] }]
    const g1 = await askConfirm(deps, {
      requirement_id: reqId, target: 'artifact', kind: 'requirement', question: '确认需求文档？', advance: true,
    }, EXEC) as { confirmed: boolean }
    expect(g1.confirmed).toBe(true)
    expect(repo.snapshot().requirements[0]?.status).toBe('design')
    console.log('[t17] ② 需求产物确认 → 状态', repo.snapshot().requirements[0]?.status)

    // ── ③ 设计文档提交 + 确认（G2）→ decomposing ───────────────────────────
    await docs.write('docs/requirements/' + reqId + '/design/architecture.md', '# 架构\n\n## D-1 覆盖 `serves: FR-1`\n')
    for (const f of ['data-model', 'interfaces', 'test-cases', 'use-cases']) {
      await docs.write('docs/requirements/' + reqId + '/design/' + f + '.md', '# ' + f + '\n')
    }
    await submitDesignArtifacts(deps, { requirement_id: reqId }, EXEC)
    await askConfirm(deps, {
      requirement_id: reqId, target: 'artifact', kind: 'design', question: '确认设计文档？', advance: true,
    }, EXEC)
    // 两条都是真实路径，取决于设计确认门是否通过（本用例不假定哪条）：
    //   ① 设计确认门通过 → **后置链自动推进** design → decomposing（此时再显式 move 会变成
    //      decomposing→decomposing 的自我转移，撞上"decomposing 需先有 decomposition 产物"的产物门）；
    //   ② 设计文档不齐（gate_failure）→ 停在 design，由本用例显式 move 推进。
    if (repo.snapshot().requirements[0]?.status === 'design') {
      await executeMoveRequirement(deps, { requirement_id: reqId, to: 'decomposing' }, EXEC)
    }
    expect(repo.snapshot().requirements[0]?.status).toBe('decomposing')
    console.log('[t17] ③ 设计确认 → 状态', repo.snapshot().requirements[0]?.status)

    // ── ④ 拆分计划提交 + **计划批准即落库**（真实路径）→ implementing + 队列生成 ──
    await docs.write('docs/requirements/' + reqId + '/decomposition.md', PLAN_DOC)
    const planSub = await submitPlanArtifact(deps, {
      requirement_id: reqId, path: 'docs/requirements/' + reqId + '/decomposition.md', summary: '拆分计划', tasks: PLAN_TASKS,
    }, EXEC) as { task_count: number; plan_status: string }
    expect(planSub.task_count).toBe(2)
    console.log('[t17] ④ 计划提交：', planSub.plan_status, '任务数', planSub.task_count)

    // 台账判据（**前**）：此刻还没有队列，且台账里从来没有 tasks 键
    expect(hasTasksKey(ledgerFile)).toBe(false)
    console.log('[t17] 台账 hasTasks（批准前）=', hasTasksKey(ledgerFile))

    questions.answers = [{ selected: [DEFAULT_CONFIRM_OPTIONS[0] as string] }]
    const approve = await askConfirm(deps, {
      requirement_id: reqId, target: 'plan', question: '批准拆分计划并立即开跑？', advance: true,
    }, EXEC) as { confirmed: boolean; advanced: boolean }
    expect(approve.confirmed).toBe(true)
    expect(approve.advanced).toBe(true)
    expect(repo.snapshot().requirements[0]?.status).toBe('implementing')
    expect(repo.snapshot().requirements[0]?.autoRun).toBe(true)

    // ── ⑤ 队列文件真实生成 + 可解析 + DAG 自洽 ─────────────────────────────
    const queueFile = join(root, queueRelativePath(reqId))
    expect(existsSync(queueFile)).toBe(true)
    const q = JSON.parse(readFileSync(queueFile, 'utf8')) as {
      requirement_id: string; tasks: { id: string; status: string; dependsOn: string[]; layer: number }[]
      layers: { layer: number; tasks: string[] }[]; ready: string[]; edges: { from: string; to: string }[]
    }
    expect(q.requirement_id).toBe(reqId)
    expect(q.tasks).toHaveLength(2)
    const [c1, c2] = q.tasks
    expect(c1!.status).toBe('todo')
    expect(c2!.dependsOn).toEqual([c1!.id])
    // ready 非空且只含链首
    expect(q.ready).toEqual([c1!.id])
    // layers 自洽：扁平集合 = 全部任务；层级单调（依赖方在更深一层）
    expect(q.layers.flatMap(l => l.tasks).sort()).toEqual([c1!.id, c2!.id].sort())
    expect(c2!.layer).toBeGreaterThan(c1!.layer)
    // 边方向 = 「依赖 → 依赖方」（`{from: 被依赖, to: 依赖方}`）
    expect(q.edges).toContainEqual({ from: c1!.id, to: c2!.id })
    console.log('[t17] ⑤ 队列生成：', queueFile.replace(root, '<tmp>'))
    console.log('[t17]    任务=', q.tasks.map(t => t.id + ':' + t.status).join(','), 'ready=', q.ready, 'layers=', JSON.stringify(q.layers))

    // ── ⑥ 台账里**没有新增任何任务**（语义级判据，非 grep）──────────────────
    expect(hasTasksKey(ledgerFile)).toBe(false)
    expect(Object.keys(readLedger(ledgerFile))).not.toContain('tasks')
    // 反向对照：`requirements[].plan.tasks` 确实存在（证明 grep '"tasks"' 会假绿）
    const rawLedgerText = readFileSync(ledgerFile, 'utf8')
    expect(rawLedgerText.includes('"tasks"')).toBe(true)
    console.log('[t17] ⑥ 台账 hasTasks（批准后）=', hasTasksKey(ledgerFile), '｜文本含 "tasks" =', rawLedgerText.includes('"tasks"'), '（故 grep 会假绿）')

    // ── ⑦ 真实推进（父子两条腿都走真实入口）──────────────────────────────
    // 计划批准路径写入 `autoRun = true`，故父卡**开工即懒展开**出 4 张阶段子卡（dev→integrate→review→test）。
    // 这是生产真实形状：推进 = 父卡开工 → 子卡链逐张执行到 done → 父卡收尾 → 下游解锁。
    const filesOf = (n: string) => 'src/' + n + '.ts'
    await docs.write(filesOf('a'), 'export const a = 1\n')
    await docs.write(filesOf('b'), 'export const b = 1\n')
    // 子卡执行引擎端口（端口桩：与 execute-task / execute-subtask-team 同一口径——引擎是外部依赖，
    // 本用例验的是**任务存储/状态机/ready 推导**这条链，不是引擎本身）。
    deps.workflow = {
      async start(input: unknown) {
        const args = input as { args?: { subtaskId?: string } }
        const id = args.args?.subtaskId ?? ''
        return {
          ok: true,
          value: { ok: true, output: JSON.stringify({ filesChanged: [filesOf('a')], completed: ['子卡 ' + id + ' 完成'] }) },
        }
      },
    } as never

    const readQ = () => JSON.parse(readFileSync(queueFile, 'utf8')) as {
      tasks: { id: string; status: string; parentId?: string; dependsOn: string[] }[]
      ready: string[]; layers: { layer: number; tasks: string[] }[]
    }
    const report = (taskId: string, f: string) => executeReportTask(deps, {
      task_id: taskId, summary: '做完 ' + f, completed: ['改了 ' + f], files_changed: [f],
    }, EXEC)
    const move = (taskId: string, to: string) => executeMoveTask(deps, { task_id: taskId, to }, EXEC)

    /** 走完一张父卡的真实生命周期：开工（懒展开）→ 子卡链逐张 done → 父卡收尾 done。 */
    const finishParent = async (parentId: string, f: string) => {
      await report(parentId, f)
      await move(parentId, 'in_progress')
      const afterStart = readQ()
      const subs = afterStart.tasks.filter(t => t.parentId === parentId)
      // 懒展开：父卡开工产出该分类的阶段子卡链（feature = dev→integrate→review→test）
      expect(subs.map(s => s.status)).toEqual(['todo', 'todo', 'todo', 'todo'])
      // ready 随状态更新：父卡离开 todo 后，队列里 ready 变成**子卡链首**（链序 = 创建序）。
      // 注意链首会继承父卡的外部依赖（卡二 → 继承 t1），故"链首"判据不能写成 `dependsOn 为空`；
      // 用「ready ∩ 子卡集合」判定，并要求恰为首张、且其后各张确实被前一张挡着。
      const readySubs = afterStart.ready.filter(id => subs.some(x => x.id === id))
      expect(readySubs).toEqual([subs[0]!.id])
      for (let i = 1; i < subs.length; i += 1) expect(afterStart.ready).not.toContain(subs[i]!.id)
      console.log('[t17] ⑦ 父卡开工 → 子卡', subs.map(s => s.id).join(','), '｜ready =', afterStart.ready)
      for (const sub of subs) {
        const r = await executeSubtask(deps, { subtaskId: sub.id, windowKey: WINDOW, exec: EXEC })
        expect(r.ok, 'subtask ' + sub.id + ' should finish: ' + String(r.reason ?? '')).toBe(true)
      }
      await move(parentId, 'done')
      const done = readQ()
      expect(done.tasks.filter(t => t.parentId === parentId).every(t => t.status === 'done')).toBe(true)
      expect(done.tasks.find(t => t.id === parentId)!.status).toBe('done')
      return done
    }

    const readyBefore = readQ().ready
    const afterCard1 = await finishParent(c1!.id, filesOf('a'))
    expect(afterCard1.ready).toEqual([c2!.id])   // ★ 卡一（含子卡链）done → 下游卡二解锁
    console.log('[t17] ⑦ 卡一闭环 → ready', readyBefore, '→', afterCard1.ready)

    // ── ⑧ 完成卡二 → ready 空 + 台账需求侧状态同步（rollup → accepting）──────
    const finalQ = await finishParent(c2!.id, filesOf('b'))
    expect(finalQ.ready).toEqual([])
    const reqNow = repo.snapshot().requirements[0]!
    expect(reqNow.status).toBe('accepting')      // ★ 台账需求侧随任务事实同步
    expect((reqNow.statusHistory ?? []).map(s => s.status)).toContain('accepting')
    console.log('[t17] ⑧ 两卡闭环 → ready', finalQ.ready, '｜需求侧状态', reqNow.status, '｜队列任务数', finalQ.tasks.length)

    // ── ⑨ 收尾：台账始终无 tasks 键；队列文件可解析 ─────────────────────────
    expect(hasTasksKey(ledgerFile)).toBe(false)
    expect(createHash('md5').update(readFileSync(queueFile)).digest('hex')).toHaveLength(32)
    console.log('[t17] ⑨ 终态：台账 hasTasks =', hasTasksKey(ledgerFile), '｜队列任务数 =', finalQ.tasks.length)
  })
})
