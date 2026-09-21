/**
 * CaptureRequirement 用例（REQ-e3b6a0 t8 / FR-7）——立项四问 pm 专有弹框：一次调用一把梭。
 *
 * 为什么不复用 `reqboard_ask_confirm`：立项四问是**表单取值 + 创建**，根本没有产物可落章
 * （ask_confirm 的 target 语义是"确认**已有**产物 / 批准**已有**计划"）。但两者**共用同一条
 * 弹框通道**（`UserQuestionPort`）与**同一条后置链**——本用例只声明 `gate: 'G0'`，
 * 压缩/注入/唤醒/留痕由装饰器（adapters/GateAwareQuestions）统一织入，本用例不碰链。
 *
 * 时序（Phase A，全部在一次工具调用内完成，避免"先弹框、再另调 create"的断链）：
 *   ① 前置判定：已绑定 / 有遗留 pending 卡 → 直接拒绝（不白弹一次框）；
 *   ② 经 `deps.questions.ask(四问)` 弹框（装饰器在此刻登记 G0 的后置链）；
 *   ③ 答案映射：名称自定义优先、缺项回落既有默认并**记进 defaults_used**（不静默猜）；
 *   ③.5 拒绝立项检查：用户选择"不需要立项" → 如实返回未立项；
 *   ④ `createRequirementDirect`：创建即立项（含 draft 入口快照 + 文档位置）；
 *   ⑤ 原子推进 draft → brainstorming（= G0 的 to；H1 稍后以台账实时状态校验推进是否真发生）。
 *
 * Phase B（H2 压缩跳过 / H3 注入 brainstorming 纪律 / H4 唤醒续跑 / H5 留痕）由链负责。
 *
 * @module dsh-pmboard/application/use-cases/CaptureRequirement
 */
import type { AskAnswer, UseCaseDeps } from '../ports.js'
import { canReqTransition, normalizeText, normalizeTitle } from '../../shared/protocol.js'
import { LIMITS } from '../../domain/limits.js'
import { fmt } from '../../domain/text/fmt.js'
import { captureSnapshot, transitionRequirement } from '../internal/token-usage.js'
import { openRequirementsFor } from '../internal/window.js'
import {
  buildCaptureQuestions,
  mapCaptureAnswers,
  type CaptureMapping,
} from '../internal/capture-mapping.js'
import {
  agentIdFromExec,
  createRequirementDirect,
  findPending,
  reject,
  requireDirectHuman,
  requireLiveDriver,
} from '../internal/support.js'

/** 未立项的统一回执（success=false；绝不伪造 requirement_id）。 */
function notCreated(
  mapped: CaptureMapping | undefined,
  extra: { fallback?: string; note: string },
): Record<string, unknown> {
  return {
    success: false,
    requirement_id: '',
    status: '',
    answers: mapped?.answers ?? { title: '', category: '', difficulty: '', docLocation: '' },
    defaults_used: mapped?.defaultsUsed ?? [],
    ...(extra.fallback === undefined ? {} : { fallback: extra.fallback }),
    note: extra.note,
  }
}

/** 立项后原子推进 draft → brainstorming（G0 的 to）。失败只如实说明，不抛。 */
async function advanceDraftToBrainstorming(deps: UseCaseDeps, requirementId: string, windowKey: string): Promise<boolean> {
  if (!canReqTransition('draft', 'brainstorming')) return false
  try {
    const result = await deps.repo.mutate('requirement-moved', (ledger) => {
      const req = ledger.requirements.find(r => r.id === requirementId)
      if (req === undefined || req.status !== 'draft') return undefined
      const at = deps.clock.now()
      // REQ-b545fe t1：唯一迁移助手（结算离开节点 + 记入口快照，缺失不补 0）。
      transitionRequirement(req, 'brainstorming', {
        at,
        actor: { kind: 'agent', sessionId: windowKey },
        reason: '立项四问作答即立项（reqboard_capture 原子推进 draft → brainstorming）',
        snap: captureSnapshot(deps, windowKey),
      })
      return { requirements: [req] }
    })
    return result.changed.requirements !== undefined && result.changed.requirements.length > 0
  } catch {
    return false
  }
}

/**
 * 立项四问弹框用例（`reqboard_capture`）：四问作答 → 创建即立项 → 绑定本窗口 → 推进 brainstorming。
 * 弹框通道不可用/无权限 → `fallback=board` 并如实说明，**不伪造立项**（FR-7 第 5 条）。
 */
export async function captureRequirement(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  requireDirectHuman(deps, exec)
  const a = (args ?? {}) as { title_options?: unknown; summary?: unknown; reason?: unknown }
  const titleOptions = Array.isArray(a.title_options)
    ? (a.title_options as unknown[])
      .map(x => normalizeText(x, 'title_options[]', LIMITS.titleMax))
      .filter(x => x.length > 0)
    : []
  const summary = normalizeText(a.summary, 'summary')
  const reason = normalizeText(a.reason, 'reason')

  // ① 前置：白弹一次框是最贵的浪费（用户要等一次点击）。与 reqboard_create 的拒绝语义对齐。
  const ledger = deps.repo.snapshot()
  if (openRequirementsFor(ledger, windowKey).length > 0) {
    reject('reqboard_capture 未执行：本窗口已绑定进行中需求，勿重复立项', 'REQBOARD_WINDOW_BOUND')
  }
  if (findPending(ledger, windowKey) !== undefined) {
    reject('reqboard_capture 未执行：本窗口还有遗留待确认建议卡，请先在看板处理或忽略', 'REQBOARD_PENDING_TRIAGE')
  }

  // ② 弹框（闸门声明 G0：装饰器在此刻登记后置链；本用例不碰链）
  if (!deps.questions.available()) {
    return notCreated(undefined, {
      fallback: 'board',
      note: '弹框通道不可用（userQuestions 服务缺失）：本次未立项。可稍后重试 reqboard_capture，或请用户直接给出名称/类型/难度/文档位置后调 reqboard_create 立项。',
    })
  }
  let answers: readonly AskAnswer[]
  try {
    answers = await deps.questions.ask(buildCaptureQuestions(titleOptions), {
      ...(exec?.agent !== undefined ? { agent: exec.agent } : {}),
      signal: (exec as { signal?: unknown } | undefined)?.signal,
      gate: 'G0',
    })
  } catch (err) {
    const code = (err as { code?: string }).code ?? ''
    if (code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE') {
      return notCreated(undefined, {
        fallback: 'board',
        note: '当前调用方无弹框权限（subagent / 非活窗口）：本次未立项。请顶层窗口在直接人工回合重试，或由用户直接给出名称/类型/难度/文档位置后调 reqboard_create。',
      })
    }
    return notCreated(undefined, {
      note: '用户未作答（取消 / 暂离）：本次未立项。稍后可重新发起 reqboard_capture。',
    })
  }

  // ③ 映射（缺项回落默认并记 defaults_used；名称为空 → 响亮失败）
  const mapped = mapCaptureAnswers(answers)
  
  // ③.5 检测拒绝立项
  if (mapped.rejected) {
    return notCreated(mapped, {
      note: '用户选择不立项：本次未创建需求。如后续需要立项，可重新发起 reqboard_capture。',
    })
  }
  
  if (mapped.title.length === 0) {
    return notCreated(mapped, {
      note: '未取到需求名称（四问答复里名称为空）：本次未立项——名称是唯一没有默认值的问项，不猜不补。可重试 reqboard_capture。',
    })
  }

  // ④ 创建即立项（draft + 入口快照 + 文档位置；actor 口径与既有 reqboard_create 一致）
  const req = await createRequirementDirect(deps, windowKey, {
    title: normalizeTitle(mapped.title),
    category: mapped.category,
    description: summary.length > 0 ? summary : mapped.title,
    reason,
    promptDifficulty: mapped.difficulty,
    docBasePath: mapped.docLocation,
  })

  // ⑤ 原子推进 brainstorming（G0 的 to）
  const advanced = await advanceDraftToBrainstorming(deps, req.id, windowKey)
  return {
    success: true,
    requirement_id: req.id,
    status: advanced ? 'brainstorming' : req.status,
    answers: mapped.answers,
    defaults_used: mapped.defaultsUsed,
    doc_location: mapped.docLocation,
    note: fmt(
      '已立项并绑定本窗口：{id}（{category} / {difficulty}）。文档将存放在：{docPath}。四问作答即立项，按 brainstorming 阶段纪律继续（无需用户再发消息）。{advanced}',
      {
        id: req.id,
        category: mapped.category,
        difficulty: mapped.difficulty,
        docPath: mapped.docLocation.replace('<REQ>', req.id),
        advanced: advanced ? '' : '注意：draft → brainstorming 未推进成功，链会如实记为未推进。',
      },
    ),
    board_link: '/dashboard#pmboard?req=' + req.id,
  }
}