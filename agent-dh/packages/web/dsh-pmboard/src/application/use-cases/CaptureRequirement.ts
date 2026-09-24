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
import type { AskAnswer, AskQuestion, CaptureRejection, UseCaseDeps } from '../ports.js'
import { canReqTransition, normalizeText, normalizeTitle } from '../../shared/protocol.js'
import { LIMITS } from '../../domain/limits.js'
import { fmt } from '../../domain/text/fmt.js'
import { captureSnapshot, transitionRequirement } from '../internal/token-usage.js'
import { openRequirementsFor } from '../internal/window.js'
import { recentCaptureRejection } from '../internal/capture-rejections.js'
import {
  buildCaptureIntentQuestions,
  buildCaptureDetailQuestions,
  mapCaptureAnswers,
  type CaptureMapping,
} from '../internal/capture-mapping.js'
import {
  agentIdFromExec,
  createRequirementDirect,
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
  // ①.5 拒绝粘滞（REQ-260922012924-2e29 FR-5）：同窗口 30 分钟内已在弹框选择"不需要立项"
  // → 不再弹框。场景：上次 capture 调用超时/中断，用户答复随死掉的调用丢失，agent 不知
  // 已拒绝而重弹（2026-09-21 现场：用户点"不立项"后需求仍被创建推进）。留痕读失败/损坏
  // 按无记录降级（留痕是增强不是门槛——绝不因留痕故障误拦截）。
  if (deps.rejections !== undefined) {
    let rejections: readonly CaptureRejection[] = []
    try { rejections = await deps.rejections.readAll() } catch { rejections = [] }
    const recent = recentCaptureRejection(rejections, windowKey, deps.clock.now())
    if (recent !== undefined) {
      return notCreated(undefined, {
        note: fmt(
          '用户已于 {t} 在弹框选择「不需要立项」（30 分钟内不再弹框，FR-5 拒绝粘滞）。本次未立项；如需立项请用户明确告知后重试。',
          { t: new Date(recent.at).toISOString() },
        ),
      })
    }
  }

  // ② 弹框（闸门声明 G0：装饰器在此刻登记后置链；本用例不碰链）
  if (!deps.questions.available()) {
    return notCreated(undefined, {
      fallback: 'board',
      note: '弹框通道不可用（userQuestions 服务缺失）：本次未立项。可稍后重试 reqboard_capture，或请用户直接给出名称/类型/难度/文档位置后调 reqboard_create 立项。',
    })
  }
  /**
   * 一次弹框（两段共用）——失败语义与改造前逐字一致：
   * 无弹框权限 → fallback=board；用户取消/暂离 → 中性未立项。
   *
   * 失败回执写进 `failure` 并返回 undefined：**不新增返回对象键**——本文件的每个 return 分支
   * 都要经 tests/output-contract 的静态扫描（按 defineCaptureTool 声明的响应键校验），
   * 自造的 `{ ok, out }` 包装会被判成未声明字段。
   */
  let failure: Record<string, unknown> | undefined
  const askOrFail = async (
    questions: readonly AskQuestion[],
    gate?: 'G0',
  ): Promise<readonly AskAnswer[] | undefined> => {
    try {
      return await deps.questions.ask(questions, {
        ...(exec?.agent !== undefined ? { agent: exec.agent } : {}),
        signal: (exec as { signal?: unknown } | undefined)?.signal,
        ...(gate === undefined ? {} : { gate }),
      })
    } catch (err) {
      const code = (err as { code?: string }).code ?? ''
      failure = code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE'
        ? notCreated(undefined, {
          fallback: 'board',
          note: '当前调用方无弹框权限（subagent / 非活窗口）：本次未立项。请顶层窗口在直接人工回合重试，或由用户直接给出名称/类型/难度/文档位置后调 reqboard_create。',
        })
        : notCreated(undefined, {
          note: '用户未作答（取消 / 暂离）：本次未立项。稍后可重新发起 reqboard_capture。',
        })
      return undefined
    }
  }

  // ② 第一段：立项意愿 + 需求名称（含终止项「✖️ 不需要立项」）。**不带 gate**——拒绝不是一次
  // 闸门作答；若在这里声明 G0，用户拒绝后链会把它当"未通过"向窗口回发告警（REQ-260924002956-f37c BUG-2）。
  const first = await askOrFail(buildCaptureIntentQuestions(titleOptions))
  if (first === undefined) return failure as Record<string, unknown>

  // ②.5 拒绝即终端（BUG-1）：命中终止项 → 写留痕 + 立即返回，**不发起第二段**
  //（不再追问类型/难度/文档位置；回执也不再带未作答三问的 defaults_used）。
  const intent = mapCaptureAnswers(first)
  if (intent.rejected) {
    try {
      deps.rejections?.record({ windowKey, at: deps.clock.now() })
    } catch { /* 留痕失败不阻断「未立项」返回——留痕是增强不是门槛 */ }
    return notCreated(undefined, {
      note: '用户选择不立项：本次未创建需求（已留痕，30 分钟内本窗口不再弹立项框）。如后续需要立项，请用户明确告知后重新发起 reqboard_capture。',
    })
  }

  // ③ 第二段：类型 / 难度 / 文档位置。**G0 登记在这里**——肯定分支才是一次闸门作答，
  // H1 在回合结束以台账实时状态校验（draft→brainstorming 已发生 = affirmative）。
  const rest = await askOrFail(buildCaptureDetailQuestions(), 'G0')
  if (rest === undefined) return failure as Record<string, unknown>

  // ③.5 映射（缺项回落默认并记 defaults_used；名称为空 → 响亮失败）
  const mapped = mapCaptureAnswers([...first, ...rest])
  
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
      '已立项并绑定本窗口：{id}（{category} / {difficulty}）。文档将存放在：{docPath}（相对路径：{relPath}，根=服务端工作区）。四问作答即立项，按 brainstorming 阶段纪律继续（无需用户再发消息）。{advanced}',
      {
        id: req.id,
        category: mapped.category,
        difficulty: mapped.difficulty,
        // FR-4：回执直接给绝对路径（用户反馈"不知道绝对路径是哪里"）；相对路径口径不变。
        docPath: deps.docs.resolve(mapped.docLocation.replace('<REQ>', req.id)),
        relPath: mapped.docLocation.replace('<REQ>', req.id),
        advanced: advanced ? '' : '注意：draft → brainstorming 未推进成功，链会如实记为未推进。',
      },
    ),
    board_link: '/dashboard#pmboard?req=' + req.id,
  }
}