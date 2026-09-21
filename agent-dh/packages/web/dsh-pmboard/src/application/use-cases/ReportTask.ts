/**
 * ReportTask 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineTaskReportTool / reqboard_task_report 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/ReportTask
 */
import type { UseCaseDeps } from '../ports.js'
import {
  normalizeText,
  type StageArtifact,
} from '../../shared/protocol.js'
import { normalizeArtifactPath } from '../../domain/artifact/ArtifactPath.js'
import { openRequirementsFor } from '../internal/window.js'
import { captureSnapshot, endExecutionToken } from '../internal/token-usage.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
} from '../internal/support.js'

export async function executeReportTask(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as {
        task_id?: unknown
        summary?: unknown
        completed?: unknown
        files_changed?: unknown
        next_step?: unknown
      }
      const taskId = normalizeText(a.task_id, 'task_id', 64)
      if (taskId.length === 0) reject('reqboard_task_report 未执行：task_id 不能为空', 'REQBOARD_INVALID_INPUT')
      const summary = normalizeText(a.summary, 'summary', 2000)
      if (summary.length === 0) reject('reqboard_task_report 未执行：summary 不能为空', 'REQBOARD_INVALID_INPUT')
      const completed = Array.isArray(a.completed)
        ? (a.completed as unknown[]).map(c => normalizeText(c, 'completed[]', 500)).filter(c => c.length > 0).slice(0, 50)
        : []
      const filesChanged = Array.isArray(a.files_changed)
        ? (a.files_changed as unknown[]).map(f => normalizeText(f, 'files_changed[]', 400)).filter(f => f.length > 0).slice(0, 50)
        : []
      const nextStep = normalizeText(a.next_step, 'next_step', 1000)

      // ── 越权校验（与 task_move 同款）：任务必须属于本窗口绑定的需求 ──────────
      const snapshot = deps.repo.snapshot()
      const task = snapshot.tasks.find(t => t.id === taskId)
      if (task === undefined) {
        reject('reqboard_task_report 未执行：任务 ' + taskId + ' 不存在', 'REQBOARD_TASK_NOT_FOUND')
      }
      const bound = openRequirementsFor(snapshot, windowKey)
      if (!bound.some(r => r.id === task.requirementId)) {
        reject(
          'reqboard_task_report 未执行：任务 ' + taskId + ' 不属于本窗口绑定的需求',
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }
      const req = snapshot.requirements.find(r => r.id === task.requirementId)
      if (req === undefined) {
        reject('reqboard_task_report 未执行：需求 ' + task.requirementId + ' 不在台账中', 'REQBOARD_STORE_INCONSISTENT')
      }


      // ── 渲染汇报段并追加落盘（文件不存在则先写任务卡骨架头）────────────────
      const docRel = 'docs/requirements/' + req.id + '/tasks/' + task.id + '.md'
      const docs = deps.docs
      const nowTs = deps.clock.now()
      const when = new Date(nowTs).toISOString()

      // 骨架头：业务三要素——与 Decompose 的骨架**同构**（REQ-640a55 FR-2）。
      // 两条建卡路径都必须产出这三节，否则从本路径出生的卡会在 task_card_incomplete 门禁前卡住。
      if (!docs.exists(docRel)) {
        const header = [
          '# ' + task.id + ' ' + task.title,
          '',
          '> 需求：' + req.id + ' ' + req.title,
          '',
          '## 在做什么',
          task.title,
          '',
          '## 解决什么问题',
          task.context.length > 0 ? task.context : '（未填写——开工前补充这张卡要解决的业务问题）',
          '',
          '## 得到什么结果',
          task.acceptance.length > 0 ? task.acceptance : '（未填写）',
          '',
          '---',
          '',
        ].join('\n')
        await docs.write(docRel, header)
      }

      // 数已有汇报段数（用于 report_index；幂等语义：每次追加都是新一段）
      const existing = await docs.read(docRel)
      const reportIndex = (existing.match(/^## 汇报 /gm) ?? []).length + 1

      const section = [
        '## 汇报 ' + reportIndex + '（' + when + '，窗口 ' + windowKey + '）',
        '',
        summary,
        '',
        ...(completed.length > 0
          ? ['### 完成项', '', ...completed.map(c => '- ' + c), '']
          : []),
        ...(filesChanged.length > 0
          ? ['### 改动文件', '', ...filesChanged.map(f => '- `' + f + '`'), '']
          : []),
        ...(nextStep.length > 0 ? ['### 下一步', '', nextStep, ''] : []),
        '---',
        '',
      ].join('\n')
      await docs.write(docRel, existing + section)

      // ── 登记产物（幂等：同 path 不重复登记）──────────────────────────────
      const artifact: StageArtifact = {
        stage: 'implementing',
        kind: 'task_detail',
        path: docRel,
        registeredAt: nowTs,
        registeredBy: { kind: 'agent', sessionId: windowKey },
      }
      // REQ-a33899：汇报即刷新本次执行的 token 进度（中途检查点；完工时由 task_move 覆盖终值）。
      const snap = captureSnapshot(deps, windowKey)
      const result = await deps.repo.mutate('requirement-updated', (ledger) => {
        const r = ledger.requirements.find(x => x.id === req.id)
        if (r === undefined) return undefined
        // done 凭证门证据源（REQ-2e9473 t06）：汇报即结构化留痕到任务记录
        const tk = ledger.tasks.find(x => x.id === task.id)
        if (tk !== undefined) {
          tk.lastReport = { at: nowTs, reportIndex, filesChanged: [...filesChanged], completed: [...completed] }
          tk.version += 1
          tk.updatedAt = nowTs
          for (let i = tk.executions.length - 1; i >= 0; i -= 1) {
            const e = tk.executions[i]!
            if (e.outcome !== 'running' || e.sessionId !== windowKey) continue
            endExecutionToken(e, snap)
            break
          }
        }
        r.artifacts ??= []
        const already = r.artifacts.some(x => x.path === artifact.path && x.kind === artifact.kind)
        if (!already) r.artifacts.push(artifact)
        // 任务文件上浮（REQ-2e9473 t12/W4）：汇报的改动文件自动登记到需求级产物清单，
        // 覆盖 REQ 目录之外的源码文件——需求详情页可见"这个需求一共动了哪些文件"。
        // REQ-b63a7d t2：登记前一律过产物路径归一层。此前原样上浮，仓库根相对
        // （agent-dh/…）、绝对路径、跨仓相对、brace-glob 伪路径全都进了台账，前端
        // 存在性预检被文件接口白名单判 403（本实例实测 142 条）。
        const workspaceRoot = deps.docs.workspaceRoot()
        for (const f of filesChanged) {
          const norm = normalizeArtifactPath(f, workspaceRoot)
          if (norm.form === 'pseudo' || norm.path.length === 0) continue
          // 工作区之外的绝对路径（/etc/... 之类）不是本仓文件，不入产物清单
          if (norm.form === 'outside' && norm.path.startsWith('/')) continue
          if (r.artifacts.some(x => x.path === norm.path && x.kind === 'task_output')) continue
          r.artifacts.push({
            stage: 'implementing',
            kind: 'task_output',
            path: norm.path,
            registeredAt: nowTs,
            registeredBy: { kind: 'agent', sessionId: windowKey },
          } as StageArtifact)
        }
        r.comments.push({
          id: deps.ids.comment(),
          body: '[任务汇报] ' + task.id + ' ' + task.title + '：' + summary
            + '\n产物：' + docRel
            + (filesChanged.length > 0 ? '\n改动：' + filesChanged.join('、') : '')
            + '\n（窗口 ' + windowKey + '）',
          createdAt: nowTs,
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        r.version += 1
        r.updatedAt = nowTs
        r.updatedBy = { kind: 'agent', sessionId: windowKey }
        return { requirements: [r], ...(tk !== undefined ? { tasks: [tk] } : {}) }
      })
      const changed = (result.changed.requirements ?? [])[0]
      if (changed === undefined) reject('reqboard_task_report 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // 产物已登记 = 同 path 的 artifact 存在（不管是本次登记还是 decompose 时已登记）
      const artifactRegistered = changed.artifacts?.some(x => x.path === artifact.path) ?? false

      return {
        success: true,
        task_id: task.id,
        requirement_id: req.id,
        doc_path: docRel,
        artifact_registered: artifactRegistered,
        report_index: reportIndex,
        note: '汇报已追加到 ' + docRel + '（第 ' + reportIndex + ' 段）'
          + (artifactRegistered ? '，产物已登记' : '，产物已存在（幂等跳过重登）'),
      }
    }
