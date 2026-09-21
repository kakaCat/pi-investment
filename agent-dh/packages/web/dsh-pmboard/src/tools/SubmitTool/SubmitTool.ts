/**
 * reqboard_submit 工具壳（REQ-47939a t8）——**4 个提交工具合一**，按 kind 表驱动分派，
 * 每个分支体只有一行用例调用（设计 §4.3「禁止大 if」）。
 *
 * kind → 用例：requirement/plan → SubmitArtifact；verification → SubmitVerification；
 * archive → SubmitArchive。返回体为四个用例返回键的并集（穷尽声明，绑定层不拒收）。
 *
 * @module dsh-pmboard/tools/SubmitTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { submitRequirementArtifact, submitPlanArtifact } from '../../application/use-cases/SubmitArtifact.js'
import { submitVerification } from '../../application/use-cases/SubmitVerification.js'
import { submitArchive } from '../../application/use-cases/SubmitArchive.js'
import { normalizeText, ALL_TASK_PHASES, ALL_TASK_SIDES } from '../../shared/protocol.js'
import { reject } from '../../application/internal/support.js'
import { renderSmart } from '../shared.js'
import { submitSummary } from '../render-summaries.js'
import { SUBMIT_PROMPT } from './prompt.js'

/** 四个 kind（分派表的键集合；错误消息与自检共用）。 */
export const SUBMIT_KINDS = ['requirement', 'plan', 'verification', 'archive'] as const

/** 分派表：kind → 用例（每项一个独立 use-case，禁止写成一个大 if）。 */
const SUBMIT_DISPATCH: Readonly<Record<string, (deps: UseCaseDeps, args: unknown, exec: unknown) => Promise<unknown>>> = {
  requirement: submitRequirementArtifact,
  plan: submitPlanArtifact,
  verification: submitVerification,
  archive: submitArchive,
}

export function defineSubmitTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_submit',
    description: SUBMIT_PROMPT,
    parameters: {
      kind: {
        type: 'string',
        description: '提交类型：requirement=需求文档 / plan=拆分计划 / verification=验收材料 / archive=归档材料',
        required: true,
        enum: [...SUBMIT_KINDS],
      },
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      path: { type: 'string', description: '文档路径（kind=requirement/plan）：工作区相对路径' },
      summary: { type: 'string', description: '摘要：requirement=一句话摘要；plan=目标+做法；verification=交付结论（≤2000 字符）' },
      change_note: { type: 'string', description: '变更原因（已确认/已批准后重交时必填）：改了什么/为什么，下游标"待同步"' },
      tasks: {
        type: 'array',
        description: 'kind=plan 的任务表（可选，1-50 项）；每项须含 implementation 与可证伪 acceptance',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            key: { type: 'string', description: '计划内引用键（如 t1；depends_on 用它引用）' },
            title: { type: 'string', description: '任务标题（动词开头，≤120 字符）' },
            description: { type: 'string', description: '任务说明（改哪些文件/接口）' },
            phase: { type: 'string', description: 'doc / ui / analysis / implement / test / review / merge', enum: [...ALL_TASK_PHASES] },
            side: { type: 'string', description: 'frontend / backend / fullstack / doc', enum: [...ALL_TASK_SIDES] },
            depends_on: { type: 'array', description: '依赖的计划内 key', items: { type: 'string' } },
            acceptance: { type: 'string', description: '验收标准（可验证：跑什么、看到什么算过；空话/缺锚点打回）' },
            implementation: { type: 'string', description: '实施方案（必填：改哪些文件、步骤、验证方式——拆分卡≠实施卡）' },
          },
        },
      },
      evidence: {
        type: 'array',
        description: 'kind=verification 的证据清单（1-20 条；命令+结果摘要 / 报告路径 / 截图路径）',
        items: { type: 'string' },
      },
      dir: { type: 'string', description: 'kind=archive 的需求目录（工作区相对路径，如 docs/requirements/REQ-xxxxxx）' },
      docs: {
        type: 'array',
        description: 'kind=archive 的需求目录内文档清单',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            kind: { type: 'string', description: 'requirement / plan / verification / retro / notes' },
            path: { type: 'string', description: '文件路径（工作区相对路径）' },
          },
        },
      },
      merged_into: {
        type: 'array',
        description: 'kind=archive 的合并去向（1-10 条，按需求类型限定在 docs/adr|architecture|guides|rfcs|work-logs|strategy-research）',
        items: { type: 'string' },
      },
      index_entry: { type: 'string', description: 'kind=archive 的一句话结论（进归档索引）' },
      manual_updates: {
        type: 'array',
        description: 'kind=archive 的项目说明书更新点（feature/refactor/spike 必填）',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            path: { type: 'string', description: '文档路径（如 docs/architecture/project-manual.md）' },
            section: { type: 'string', description: '章节标题' },
            summary: { type: 'string', description: '一句话：这一节现在多了什么认知' },
          },
        },
      },
      manual_note: { type: 'string', description: 'kind=archive 无手册更新时的理由（bug/doc/chore 可只写这条）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean', description: '是否成功' },
          requirement_id: { type: 'string', description: '需求 id' },
          plan_status: { type: 'string', description: 'kind=plan：pending_approval' },
          task_count: { type: 'number', description: 'kind=plan：任务表条数' },
          orphan_clauses: {
            type: 'array',
            description: 'kind=plan：无任何下游引用的根编号（需求里有、没人接）——应在看板标红；不阻断提交',
            items: { type: 'string' },
          },
          tasks: {
            type: 'array',
            description: 'kind=plan：计划任务表（key/title/depends_on）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                key: { type: 'string' },
                title: { type: 'string' },
                depends_on: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          artifact: {
            type: 'object',
            additionalProperties: false,
            description: 'kind=requirement：登记的产物（stage/kind/path）',
            properties: {
              stage: { type: 'string' },
              kind: { type: 'string' },
              path: { type: 'string' },
            },
          },
          registered: { type: 'boolean', description: 'kind=requirement：false = 幂等命中（此前已登记）' },
          status: { type: 'string', description: '提交后的需求状态（accepting / archived 等）' },
          tasks_done: { type: 'number', description: 'kind=verification：已完成任务数' },
          tasks_total: { type: 'number', description: 'kind=verification：任务总数' },
          sheet_version: { type: 'number', description: 'kind=verification：验收单版本（v1/v2…）' },
          sheet_items: { type: 'number', description: 'kind=verification：本轮验收项数' },
          rework_only: { type: 'boolean', description: 'kind=verification：本轮是否只含上版未过项（返工续验）' },
          doc_sync_pending: {
            type: 'array',
            description: '待同步的下游文档（重交下游产物后销标）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                source: { type: 'string' },
                downstream: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          doc_sync_warning: { type: 'string', description: '下游待同步警告' },
          blockers: {
            type: 'array',
            description: 'kind=verification：rollup 阻塞（未完成任务清单，需求未进验收的原因）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string' },
                title: { type: 'string' },
                status: { type: 'string' },
              },
            },
          },
          required_docs: { type: 'array', items: { type: 'string' }, description: 'kind=archive：该需求类型的必填文档' },
          unlisted_files: { type: 'array', items: { type: 'string' }, description: 'kind=archive：目录内未列入归档清单的文件（漏登警告）' },
          warning: { type: 'string', description: '漏洞/阻塞等非阻断警告' },
          note: { type: 'string', description: '下一步指引' },
        },
      },
      render: renderSmart(submitSummary),
    },
    timeoutMs: LIMITS.timeoutWriteMs,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const kind = normalizeText(((args ?? {}) as { kind?: unknown }).kind, 'kind', 32)
      const run = SUBMIT_DISPATCH[kind]
      if (run === undefined) {
        reject('reqboard_submit 未执行：kind 必须是 ' + SUBMIT_KINDS.join(' / '), 'REQBOARD_INVALID_INPUT')
      }
      return run(deps, args, exec)
    },
  } as any)
}
