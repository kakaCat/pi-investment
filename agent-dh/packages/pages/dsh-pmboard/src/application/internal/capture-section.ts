/**
 * 捕获引导段文本组装（REQ-47939a t9 ← host/capture.ts）——systemPrompt 组装处按窗口条件取文本。
 *
 * 为什么在 application：这些函数是**纯文本编排**（给 LLM 看的过程纪律与立项引导文案），
 * 只读台账视图 + 窗口投影，无 I/O、无 ctx、不碰 fs。规则（窗口绑定/pending 判定）在
 * application/internal/window.ts，阶段提示词常量在 domain/stage/StagePromptSpec.ts。
 *
 * 搬迁口径（t9）：文本逐字保持（含全部中文字面量），既有 capture.test.ts /
 * stage-prompts.test.ts / acceptance-criteria.test.ts 的断言语义不变，仅 import 路径改到本模块。
 *
 * @module dsh-pmboard/application/internal/capture-section
 */
import type { ReqboardLedger } from '../../shared/protocol.js'
import { stageEnabledFor } from '../../shared/protocol.js'
import type { StageKey } from '../../domain/requirement/RequirementStatus.js'
import { resolveStagePrompt, isPromptStage } from '../../domain/prompt/index.js'
import {
  injectionLogInputFromResolved,
  type InjectionLogPort,
} from './injection-log.js'
import { isImplementing } from '../../domain/status/Predicates.js'
import { isInProgressTask } from '../../domain/status/Predicates.js'
import {
  windowKeyFromContext,
  isWindowBound,
  hasPendingSuggestion,
  openRequirementsFor,
} from './window.js'

/**
 * 待捕获消息登记（确定性消息 hook 写入、capture section 消费的瞬态信号）。
 * 不进台账——它是「用户消息刚到达、窗口需要走立项评估」的一次性触发信号，
 * turn/end 后由 hook 清除（消费完毕）。
 */
export interface PendingCaptureMessage {
  windowKey: string
  /** 清洗后的用户消息文本（供注入引用；纯系统块/噪声消息不会登记）。 */
  text: string
  capturedAt: number
}

/**
 * 该窗口的捕获引导 section 文本（乙：提示 agent 识别新工作 → 两问弹框确认 →
 * reqboard_create 直接立项）。bound / 已有遗留 pending / 无法取 windowKey →
 * 返回 ''（零噪音）。永不返回 undefined。
 *
 * 第三参 pending 为确定性消息 hook 登记的本窗口「待捕获候选」：命中时返回
 * 引用该用户消息原文的针对性立项提示（用户裁定：消息到达 → hook 检查窗口是否
 * 需要立项捕获 → 注入提示词让 LLM 弹两问确认 → 直接建 REQ），未命中维持静态引导。
 * 向后兼容：不传 pending 时行为与旧版完全一致（capture.test.ts 三分支不变）。
 */
export function captureSectionText(
  ledger: ReqboardLedger,
  context: unknown,
  pending?: PendingCaptureMessage | undefined,
): string {
  const windowKey = windowKeyFromContext(context as { agent?: { id?: unknown }; scope?: unknown })
  if (!windowKey) return ''
  if (isWindowBound(ledger, windowKey)) return ''
  if (hasPendingSuggestion(ledger, windowKey)) return ''
  if (pending && pending.windowKey === windowKey && pending.text.trim().length > 0) {
    return capturePromptForMessage(windowKey, pending.text)
  }
  return captureGuidanceText(windowKey)
}

/**
 * 绑定窗口的「推进纪律」段 —— 本窗口已绑定进行中需求时注入；未绑定 → ''。
 *
 * 为什么需要：此前 bound 窗口的 section 返回 ''（零噪音），窗口 agent 根本不知道
 * 自己名下有需求、更不知道可以推进状态 → 需求建卡后只能等人点按钮（用户反馈
 * 「agent 自己不能推进吗，还需要用户手动推进」）。本段把「状态由窗口自己维护」
 * 变成提示词里的明确纪律，窗口在里程碑处主动调 reqboard_move。
 */
export function boundSectionText(
  ledger: ReqboardLedger,
  context: unknown,
  injectionLog?: InjectionLogPort,
): string {
  const windowKey = windowKeyFromContext(context as { agent?: { id?: unknown }; scope?: unknown })
  if (windowKey === undefined) return ''
  const open = openRequirementsFor(ledger, windowKey)
  if (open.length === 0) return ''
  // 基础需求列表
  const lines: string[] = [
    `## 项目看板（reqboard · 本窗口 ${windowKey.slice(0, 16)} 已绑定需求）`,
    '',
    '本窗口名下有进行中的需求：',
    ...open.map(r => `- ${r.id}《${r.title}》当前状态：${r.status}`),
    '',
  ]
  
  // ========== implementing 阶段注入当前任务执行指引 ==========
  const implementingReq = open.find(isImplementing)
  if (implementingReq) {
    const inProgressTasks = ledger.tasks.filter(
      t => t.requirementId === implementingReq.id && isInProgressTask(t)
    )
    
    if (inProgressTasks.length > 0) {
      const task = inProgressTasks[0]
      lines.push('## 【当前任务执行中】')
      lines.push('')
      lines.push(`任务：${task.title}`)
      lines.push('')
      lines.push('**任务说明**：')
      lines.push(task.description || '（无）')
      lines.push('')
      lines.push('**需求背景**：')
      lines.push(task.context || '（无）')
      lines.push('')
      lines.push('**验收标准**：')
      lines.push(task.acceptance || '（无）')
      lines.push('')
      lines.push(`**阶段**：${task.phase} | **端侧**：${task.side}`)
      lines.push('')
      lines.push('---')
      lines.push('请按照任务说明执行。完成后推进任务状态：')
      lines.push(`- 开发完成 → reqboard_task_move({ task_id: '${task.id}', to: 'integrating', reason: '...' })`)
      lines.push(`- 联调完成 → reqboard_task_move({ task_id: '${task.id}', to: 'testing', reason: '...' })`)
      lines.push(`- 测试通过 → reqboard_task_move({ task_id: '${task.id}', to: 'in_review', reason: '...' })`)
      lines.push('')
      lines.push('查看所有任务：reqboard_status()')
      lines.push('')
    }
  }
  // ========== 任务执行指引结束 ==========
  
  // ========== 阶段提示词注入（REQ-31e11f t5：按当前阶段注入纪律提示词）==========
  // 被分类档案跳过的阶段（stageEnabledFor=false）不注入——跳过阶段不产生物、不设门、
  // 不注入提示词。同一窗口多个 open 需求时，取最近更新的那条。
  const stageReq = [...open].sort((a, b) => b.updatedAt - a.updatedAt)[0]
  if (stageReq !== undefined) {
    const stage = stageReq.status
    // draft/done/canceled 不是可注入节点（types.ts）：先过闸，避免只捞到 ⑤ 铁律而被当成有提示词。
    if (isPromptStage(stage) && stageEnabledFor(stageReq.category, stage as StageKey)) {
      // INV-1：取词唯一入口（分片库 + 回退链 + 预算）；不再直取常量表。
      // FR-16：带上需求实质，让唯一取词入口按它推断难度（动架构 / 跨子系统 / 改数据模型 → heavy），
      // 不再静默回落缺省 light——REQ-c9f899 被注入轻档提示词的根因就在这一行。
      const resolved = resolveStagePrompt({
        stage,
        category: stageReq.category,
        requirement: { title: stageReq.title, description: stageReq.description },
      })
      if (resolved.text.length > 0) {
        lines.push('')
        lines.push(resolved.text)
        // INV-6：注入即留痕（本次到底注入了什么，可被看板/人核查）。
        injectionLog?.record(injectionLogInputFromResolved(resolved, windowKey))
      }
    }
  }
  // ========== 阶段提示词注入结束 ==========

  lines.push(
    '流水线（状态就是阶段，从立项一路走到交付）：',
    '- draft 立项 → brainstorming 头脑风暴（探边界/方案）→ planning 写计划 →',
    '  decomposing 拆分（落库任务 DAG）→ implementing 执行 → accepting 验收 → done 完成；',
    '- 方案谈定 → reqboard_move 到 planning（写计划属于这个阶段）；',
    '',
    '计划模式（拆分的前置闸门 · 唯一需要人点头的地方）：',
    '- 评审阶段先把方案写成实施计划 → reqboard_submit(kind=plan)（path = 工作区计划文档，',
    '  summary = 一段人能读懂的目标+做法，tasks = 将来要落库的任务表：',
    '  key/title/phase/side/depends_on/acceptance，粒度与依赖在这里定死）；',
    '- 提交后请人在项目看板点「批准计划」——未批准时 reqboard_decompose 被代码级拒绝；',
    '- 获批后 reqboard_decompose 落库任务卡（不传 tasks = 直接落库批准的计划；',
    '  传了 tasks 则必须与计划 key 一致，防止「批了 A 落库 B」）；',
    '- 方案要改 → 重新 reqboard_submit(kind=plan)（旧批准自动作废，需重新批准）。',
    '',
    '状态推进纪律（计划批准之后，其余都由窗口自己维护，不需要用户手动点按钮）：',
    '- 方案敲定 → reqboard_decompose 把需求拆成任务 DAG 落库（真拆分：写台账任务卡，',
    '  看板「任务」页与甘特图据此渲染；depends_on 用批次内 key 引用同批任务）；',
    '- 拆分后需求会自动进入拆分态；任务开工/完成用 reqboard_task_move 推进',
    '  （todo → in_progress → testing → in_review → done；开工时会自动记一段执行时间）；',
    '- 任务全部 done 时系统自动把需求推进到 accepting（验收）；交付并自检通过后',
    '  用 reqboard_move 自行推进到 done。',
    '- 只有「取消需求/归档/取消任务」必须人操作（agent 调用会被代码级拒绝）。',
    '- 推进时用 reason 写清做了什么（进需求留痕，供复盘与验收）。',
    '',
    '验收（人工审核，别自己判过）：',
    '- 交付完成 → reqboard_submit(kind=verification)（summary = 交付结论；evidence = 可复核的证据：',
    '  命令+输出摘要 / 报告路径 / 截图路径），需求进入验收态等人审核；',
    '- 「验收通过」只有人能点；被退回 → 按人的意见返工后再提交。',
    '',
    '归档（先备材料，人再点）：',
    '- 需求完成后 → reqboard_submit(kind=archive)（需求目录 docs/requirements/REQ-xxxxxx、',
    '  目录内文档清单、合并去向 merged_into、一句话索引条目）；',
    '- 合并去向与必填文档按需求类型限定（feature→architecture/guides，bug→known-issues，',
    '  spike→research，refactor→architecture/work-logs，chore→work-logs），规范见',
    '  agent-dh/docs/architecture/requirement-archive.md；缺项会被代码级拒绝；',
    '- 归档材料里写了的合并去向，必须真的把那部分结论写进对应的项目文档；',
    '- 金字塔生长：feature/refactor/spike 必须在材料里申报 manual_updates（更新了哪份文档的哪一节、',
    '  多了什么认知），说明书是 docs/architecture/project-manual.md；bug/doc/chore 写 manual_note 说明即可；',
    '- docs 按 wiki 维护：新页面要有 front-matter 并挂进首页/上层页，未写的主题进首页「待写页」；',
    '  收工前可跑 python3 agent-dh/scripts/wiki_probe.py 自检死链/孤儿页。',
  )
  
  return lines.join('\n')
}

/**
 * 针对性立项提示（消息事件 hook 命中时注入）：引用刚到达的用户消息原文，
 * 指示 LLM 判断该输入是否值得立项——值得则【两问弹框 = 立项门 → 直接建 REQ】：
 * 先 ask_user_question 向用户弹两问——「需求名称」（选项由本条消息上下文推导、
 * 最贴切一项置首标注 (Recommended)、允许自定义）与「需求类型」（feature/bug/doc/
 * refactor/spike/chore，同 (Recommended) 置首可改选）；**用户作答即立项确认**，
 * 随后按确认值调 reqboard_create 直接创建 REQ（创建即立项，无待归类/建议卡
 * 中间态，看板立即可见）。只是闲聊 / 追问进度则正常回复，不弹框不立项。
 * 判定留给 LLM（窗口 agent 自身回合），hook 只保证确定性触发。全部字面量。
 */
export function capturePromptForMessage(windowKey: string, text: string): string {
  const trimmed = text.trim().replace(/\s+/g, ' ')
  const snippet = trimmed.slice(0, 300)
  return [
    `## 项目捕获（reqboard · 本窗口 ${windowKey.slice(0, 16)} 检测到用户新输入）`,
    '',
    '用户刚刚发来一条消息，其中可能包含值得立项的新工作意图（新功能 / 缺陷修复 /',
    '文档 / 重构 / 技术调研 / 维护事项）。请先判断该输入是否属于这类工作：',
    '',
    '- 值得立项 → 先弹「两问确认」（弹框即立项门，作答即立项）：',
    '  1) 调用 ask_user_question 一次发两个问题向用户确认——',
    '     问题一「需求名称」：按本条消息上下文给出候选标题选项，最贴切的一项放首位',
    '       并标注 (Recommended)，允许用户选择或自定义输入最终名称；',
    '     问题二「需求类型」：选项 feature / bug / doc / refactor / spike / chore，',
    '       最符合的一项放首位并标注 (Recommended)，允许用户改选或自定义；',
    '  2) 用户作答后（= 立项确认），立即按用户确认值调 reqboard_create 直接创建需求：',
    '     title = 用户确认的需求名称，category = 用户选择的需求类型，',
    '     summary = 本次工作摘要，reason = 立项依据（引用本条消息原文）；',
    '',
    '- 只是闲聊、询问进度、继续之前话题或无需立项 → 正常回复即可，不要弹框、不要立项。',
    '',
    '本次待判断的用户消息（节选，最多 300 字）：',
    '',
    `> ${snippet}${trimmed.length > 300 ? '…' : ''}`,
    '',
    '注意：reqboard_create 创建即立项（REQ 立即在看板 draft 泳道可见，无待归类/建议卡',
    '中间态）；本窗口创建后即绑定该需求。未弹框或用户未作答时不要调用、不要宣称"已立项"。',
  ].join('\n')
}

/** 引导文本（纯字面量）。窗口已完成/取消/归档全部需求后重新变为 unbound → 引导复现。 */
export function captureGuidanceText(windowKey: string): string {
  // 全部字面量，无 {{变量}}。短小精炼，避免挤占上下文预算。
  return [
    `## 项目捕获（reqboard · 本窗口 ${windowKey.slice(0, 16)} 未绑定需求）`,
    '',
    '本窗口当前没有进行中的需求记录。若用户在本窗口提出了新的工作意图',
    '（新功能 / 缺陷修复 / 文档 / 重构 / 技术调研 / 维护事项），且该工作值得立项，',
    '先调用 ask_user_question 弹「两问确认」：问题一「需求名称」（按上下文给出候选',
    '选项，最贴切一项置首标注 (Recommended)，允许用户自定义）；问题二「需求类型」',
    '（feature / bug / doc / refactor / spike / chore，同 (Recommended) 置首可改选）。',
    '用户作答即立项确认——按确认值调 reqboard_create 直接创建 REQ（创建即立项，',
    '无待归类/建议卡中间态）：title = 确认名称、category = 确认类型、',
    'summary = 工作摘要、reason = 立项依据。',
    '',
    '仅闲聊或询问已有需求进度时无需弹框、无需立项。',
  ].join('\n')
}