/**
 * 验收单规约（REQ-47939a t4 / INV-6，REQ-2e9473 t13/W6）。
 *
 * 从 host/verdicts.ts 与 host/agent-tools.ts 的 verify_submit / accept_sheet 抽出三件纯规则：
 *   - buildSheet：逐项验收单生成（每任务验收标准 + 需求级标准；返工续版只含「未过项 + 未裁决项」）；
 *   - applyVerdicts：逐项裁决（不通过必填意见）+ 返工任务**规格**生成（落地由 host 负责）；
 *   - isAllPassed：是否全过。
 *
 * v5 变更（migration.md C7）：VerificationItem.source 由字符串改为判别联合
 * （{kind:'requirement'} | {kind:'task',taskId}）——原字符串同时表达"需求级"与"任务 id"
 * 两种含义，是字符串型歧义。类型定义落在本文件，protocol 再导出。
 *
 * 纯函数 / 就地修改传入的 sheet（调用方已在 store.mutate 草稿对象上操作）；唯一抛出的是
 * 领域错误 invalid_input（不通过缺意见 / 验收项不存在）。时间与随机数一律由参数注入。
 */

import type { ActorRef } from '../actor.js'
import { REQBOARD_ERROR_CODES, domainError } from '../errors.js'
import { fmt } from '../text/fmt.js'

/** 验收项来源（v5 判别联合）。 */
export type VerificationItemSource = { kind: 'requirement' } | { kind: 'task'; taskId: string }

/** 验收单项（结构对齐 shared/protocol.ts 的 VerificationItem）。 */
export interface SheetItemLike {
  id: string
  source: VerificationItemSource
  criterion: string
  evidence: string[]
  /** 四值（REQ-308b9a FR-9）：not_verifiable=不可验收/不适用，须带原因，不阻断通过 */
  status: 'pending' | 'passed' | 'failed' | 'not_verifiable'
  opinion?: string
  decidedAt?: number
  decidedBy?: ActorRef
}

/** 验收单（结构对齐 shared/protocol.ts 的 VerificationSheet）。 */
export interface SheetLike {
  version: number
  items: SheetItemLike[]
  generatedAt: number
  generatedBy: ActorRef
  /** 本轮是否只含上一版未过项（返工续验标记） */
  reworkOnly?: boolean
}

/** 任务验收标准来源（最小投影）。 */
export interface SheetTaskLike {
  id: string
  title: string
  acceptance: string
}

/** 需求级验收标准原文（唯一常量，避免前端/后端各写一份）。 */
export const REQUIREMENT_LEVEL_CRITERION = '需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）'

export interface SheetBuildInput {
  /** 历史验收单条数（version = history + 上一版 + 1）。 */
  sheetHistoryLength: number
  /** 上一版验收单（返工续版判定用）。 */
  prevSheet?: SheetLike
  /** 未取消任务的验收标准（顺序即验收项顺序）。 */
  tasks: readonly SheetTaskLike[]
  /** 本轮证据（复制进每一项）。 */
  evidence: readonly string[]
  /**
   * 孤儿用例（REQ-d3e61a T-7 / FR-5）：设计文件点名了、但文件头未声明覆盖条款的测试文件。
   * 按规范这是**警告级**（不阻断），但必须是验收面上**可见的一项**——"靠人记得"正是不该有的形态。
   * 非空时追加一条需求级验收项。
   */
  orphanTestFiles?: readonly string[]
  /**
   * 不可照着验、但**从未过计划期锚点门**的验收项（直种/历史数据，REQ-d3e61a T-9）。
   * 非空时追加一条需求级可见项——不追溯硬拦，但绝不允许静默（"看不见"正是 R9 那类事故的形态）。
   */
  unverifiableItems?: readonly string[]
  /**
   * E2E 覆盖读数（REQ-d3e61a T-16 / FR-11）：true=有 E2E 场景用例，false=**缺口**。
   * undefined = 读数未知（需求文档缺失/无测试策略表）→ 不追加可见项，避免噪声。
   * 只有单元/集成测试必须**作为一个可见验收项**暴露，而不是靠人记得。
   */
  e2eCoverage?: boolean
  /**
   * 三方一致性缺口（REQ-d3e61a T-8 / FR-9）：做什么 × 怎么做 × 实际做了什么 对不上时的文案。
   * 非空时追加一条需求级可见项——不一致必须**显式出现**，不允许沉默（R9 的形态就是沉默）。
   */
  consistencyGaps?: readonly string[]
  generatedAt: number
  generatedBy: ActorRef
}

export interface SheetBuildResult {
  sheet: SheetLike
  /** true = 本轮为返工续验（上一版有未过项），items 只含未过项与未裁决项。 */
  reworkOnly: boolean
}

/**
 * 生成验收单。
 * 返工续版（上一版有 failed 项）→ 带过上一版的**未过项 + 未裁决项**（已过项保留结论，不重验）；
 * 否则 → 每任务一条 + 需求级一条，全部 pending（重新生成，不是续版）。
 *
 * 2026-09-17 用户裁定（REQ-47939a D-7，范围补充）：旧实现只带 failed，**pending 项会从在册
 * 验收单里消失**（只留在 sheetHistory）。极端路径：v1 = failed + pending → 打回返工 →
 * v2 只含 failed → 修好后 v2 全过 → 归档，而那些 pending 项**从未被裁决过**。带过后
 * "逐项验收"才真正成立：未过项要复核，未验项也必须有人点头。
 * 保留另一条既有语义：上一版**没有** failed 项时仍重新生成全新验收单（不进入续版）。
 */
export function buildSheet(input: SheetBuildInput): SheetBuildResult {
  const prevSheet = input.prevSheet
  const prevItems = prevSheet?.items ?? []
  const prevFailed = prevItems.filter(i => i.status === 'failed')
  const version = input.sheetHistoryLength + (prevSheet !== undefined ? 1 : 0) + 1
  const reworkOnly = prevFailed.length > 0
  // 续版带过：failed（要复核）+ pending（从未裁决）——顺序沿用上一版，保证人工核对时位置不变
  const carried = reworkOnly
    ? prevItems.filter(i => i.status === 'failed' || i.status === 'pending')
    : []
  const orphanTestFiles = input.orphanTestFiles ?? []
  const unverifiable = input.unverifiableItems ?? []
  const unverifiableItems: SheetItemLike[] = unverifiable.length === 0 ? [] : [{
    id: 'v' + version + '-' + (input.tasks.length + 3),
    source: { kind: 'requirement' } as VerificationItemSource,
    criterion: fmt('验收项不可照着验（历史数据）：以下验收项没写「怎么验」——{list}。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。', { list: unverifiable.slice(0, 5).join('；') }),
    evidence: [...input.evidence],
    status: 'pending' as const,
  }]
  const consistency = input.consistencyGaps ?? []
  const consistencyItems: SheetItemLike[] = consistency.length === 0 ? [] : [{
    id: 'v' + version + '-' + (input.tasks.length + 5),
    source: { kind: 'requirement' } as VerificationItemSource,
    criterion: fmt('三方一致性（做什么 × 怎么做 × 实际做了什么）：以下对不上——{list}。请补设计、补实施、或显式登记为不做。', { list: consistency.slice(0, 6).join('；') }),
    evidence: [...input.evidence],
    status: 'pending' as const,
  }]
  const e2eItems: SheetItemLike[] = input.e2eCoverage === undefined ? [] : [{
    id: 'v' + version + '-' + (input.tasks.length + 4),
    source: { kind: 'requirement' } as VerificationItemSource,
    criterion: input.e2eCoverage
      ? 'E2E 覆盖：**有**（存在跨组件跑通完整业务链路的场景用例）'
      : 'E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。',
    evidence: [...input.evidence],
    status: 'pending' as const,
  }]
  const orphanItems: SheetItemLike[] = orphanTestFiles.length === 0 ? [] : [{
    id: 'v' + version + '-' + (input.tasks.length + 2),
    source: { kind: 'requirement' } as VerificationItemSource,
    criterion: fmt(
      '孤儿用例（缺映射）：以下测试文件未在文件头声明覆盖的条款/卡——{list}。请补 serves: 声明，或说明为何无需映射。',
      { list: orphanTestFiles.join('、') },
    ),
    evidence: [...input.evidence],
    status: 'pending' as const,
  }]
  const items: SheetItemLike[] = reworkOnly
    ? carried.map((it, idx) => ({
        ...it,
        id: 'v' + version + '-' + (idx + 1),
        status: 'pending' as const,
        opinion: undefined,
        decidedAt: undefined,
        decidedBy: undefined,
      }))
    : [
        ...input.tasks.map((t, idx) => ({
          id: 'v' + version + '-' + (idx + 1),
          source: { kind: 'task', taskId: t.id } as VerificationItemSource,
          // T-11：验收项先说**业务结果**（标题即业务语言，T-10 保证），再说**怎么验**——
          // 原来直接放 acceptance（一串命令），用户读不出"这项在确认什么"。
          criterion: fmt('【{title}】验收：{detail}', {
            title: t.title.length > 0 ? t.title : t.id,
            detail: t.acceptance.length > 0 ? t.acceptance : '交付完成',
          }),
          evidence: [...input.evidence],
          status: 'pending' as const,
        })),
        {
          id: 'v' + version + '-' + (input.tasks.length + 1),
          source: { kind: 'requirement' } as VerificationItemSource,
          criterion: REQUIREMENT_LEVEL_CRITERION,
          evidence: [...input.evidence],
          status: 'pending' as const,
        },
        // 孤儿用例 / 不可照着验的项（有则追加；都做成**需求级**项——本就是需求级关切，
        // 且不动 protocol 的 source 联合，避免碰被占用的 protocol.ts）
        ...orphanItems,
        ...unverifiableItems,
        ...e2eItems,
        ...consistencyItems,
      ]
  const sheet: SheetLike = {
    version,
    items,
    generatedAt: input.generatedAt,
    generatedBy: input.generatedBy,
    ...(reworkOnly ? { reworkOnly: true } : {}),
  }
  return { sheet, reworkOnly }
}

/** 逐项裁决入参。 */
export interface SheetVerdictInput {
  itemId: string
  status: 'passed' | 'failed' | 'not_verifiable'
  opinion?: string
}

/** 返工任务的原任务投影（承接 phase/side/scope）。 */
export interface ReworkSourceTaskLike {
  id: string
  title: string
  phase: string
  side: string
  scope?: unknown
}

/** 返工任务规格（host 据此 materialize 成 TaskRecord：id / 时间戳 / 状态事件由 host 负责）。 */
export interface ReworkTaskSpec {
  title: string
  description: string
  phase: string
  side: string
  scope: unknown
  acceptance: string
  implementation: string
  context: string
  /** 原验收意见（''=未写；评论留痕用，与 implementation 的兜底文案不同）。 */
  opinion: string
}

export interface ApplySheetVerdictsResult {
  sheet: SheetLike
  /** 本批**不通过**项对应的返工任务规格（数量 = 本批 failed 数）。 */
  reworkTasks: ReworkTaskSpec[]
  pending: number
  passed: number
  failed: number
  /** 不可验收项计数（REQ-308b9a FR-9）：不触发返工、不阻断通过。 */
  notVerifiable: number
}

/**
 * 单个"不通过"验收项 → 返工任务规格（承接原任务 phase/side/scope 与验收意见）。
 *
 * REQ-a8d582 FR-2：本函数从 applyVerdicts 内部**抽出来成为单点**——因为"返工任务何时生成"
 * 从"裁决时"搬到了"人点退回返工时"，两条路径（裁决批次 / 退回返工）必须用同一套规格，
 * 各写一份必然漂移。
 */
export function reworkSpecFor(
  item: SheetItemLike,
  sheet: SheetLike,
  tasks: readonly ReworkSourceTaskLike[],
): ReworkTaskSpec {
  const src = item.source
  const orig = src.kind === 'task' ? tasks.find(t => t.id === src.taskId) : undefined
  return {
    title: fmt('返工：{title}', { title: (orig?.title ?? item.criterion).slice(0, 60) }),
    description: fmt('验收不通过项返工（v{version} 项 {itemId}）：{criterion}', { version: sheet.version, itemId: item.id, criterion: item.criterion }),
    phase: orig?.phase ?? 'implement',
    side: orig?.side ?? 'fullstack',
    scope: orig?.scope ?? { apis: [], tables: [], files: [] },
    acceptance: item.criterion,
    implementation: fmt('按验收意见修复：{opinion}', { opinion: item.opinion ?? '（见验收单）' }),
    context: fmt('承接自 {origin}；验收意见：{opinion}', {
      origin: src.kind === 'requirement' ? '需求级验收项' : fmt('任务 {taskId}', { taskId: src.taskId }),
      opinion: item.opinion ?? '',
    }),
    opinion: item.opinion ?? '',
  }
}

/** 验收单里**已判不通过**的全部项 → 返工规格（"退回返工"路径用；与裁决路径同源）。 */
export function reworkSpecsFor(sheet: SheetLike, tasks: readonly ReworkSourceTaskLike[]): ReworkTaskSpec[] {
  return sheet.items.filter(i => i.status === 'failed').map(i => reworkSpecFor(i, sheet, tasks))
}

/**
 * 逐项应用裁决（就地修改 sheet.items）。
 * 不通过项缺意见 / 验收项不存在 → 抛 code=invalid_input 的领域错误（调用方可映射传输码）。
 * 返工规格承接原任务 phase/side/scope + 意见；需求级项的 source 不指向任务，故 orig 为空。
 */
export function applyVerdicts(
  sheet: SheetLike,
  verdicts: readonly SheetVerdictInput[],
  actor: ActorRef,
  at: number,
  tasks: readonly ReworkSourceTaskLike[],
): ApplySheetVerdictsResult {
  const failedItems: SheetItemLike[] = []
  for (const verdict of verdicts) {
    const item = sheet.items.find(i => i.id === verdict.itemId)
    if (item === undefined) {
      throw domainError(REQBOARD_ERROR_CODES.invalidInput, fmt('验收项 {itemId} 不存在', { itemId: verdict.itemId }))
    }
    if (verdict.status === 'failed' && (verdict.opinion ?? '').length === 0) {
      throw domainError(REQBOARD_ERROR_CODES.invalidInput, fmt('不通过的验收项必须写意见（{itemId}）', { itemId: item.id }))
    }
    // REQ-308b9a FR-9 / AC-9.2："不可验收"同样必须有人给出原因——不允许静默消失。
    if (verdict.status === 'not_verifiable' && (verdict.opinion ?? '').length === 0) {
      throw domainError(REQBOARD_ERROR_CODES.invalidInput, fmt('不可验收的验收项必须写原因（{itemId}）', { itemId: item.id }))
    }
    item.status = verdict.status
    if ((verdict.opinion ?? '').length > 0) item.opinion = verdict.opinion
    item.decidedAt = at
    item.decidedBy = actor
    if (verdict.status === 'failed') failedItems.push(item)
  }
  const reworkTasks: ReworkTaskSpec[] = failedItems.map(item => reworkSpecFor(item, sheet, tasks))
  return {
    sheet,
    reworkTasks,
    pending: sheet.items.filter(i => i.status === 'pending').length,
    passed: sheet.items.filter(i => i.status === 'passed').length,
    failed: sheet.items.filter(i => i.status === 'failed').length,
    notVerifiable: sheet.items.filter(i => i.status === 'not_verifiable').length,
  }
}

/** 是否全部通过（任一 pending/failed/not_verifiable → false）。 */
export function isAllPassed(sheet: SheetLike): boolean {
  return sheet.items.every(i => i.status === 'passed')
}

/**
 * 是否全部项已裁决（无 pending）——**"可以走验收通过"这条规则的唯一实现**（REQ-308b9a FR-9 / AC-9.3）。
 *
 * 与 isAllPassed 的区别：not_verifiable（不可验收）算已裁决——人已看过并给出原因，
 * 不允许因为它把整次验收卡死；而 pending 一律不放行（AC-9.5，防未验项静默消失）。
 * failed 项由 FR-8 自动回退处理，正常到不了这里。
 */
export function isFullyDecided(sheet: SheetLike): boolean {
  return sheet.items.every(i => i.status !== 'pending')
}
