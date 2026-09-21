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
import { captureDiag } from './diag-log.js'
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
 * 该窗口的捕获引导 section 文本（乙：提示 agent 识别新工作 → 调 reqboard_capture
 * 弹立项三问（名称/类型/难度）并在同一次调用内创建即立项）。bound / 已有遗留 pending / 无法取 windowKey →
 * 返回 ''（零噪音）。永不返回 undefined。
 *
 * 第三参 pending 为确定性消息 hook 登记的本窗口「待捕获候选」：命中时返回
 * 引用该用户消息原文的针对性立项提示（用户裁定：消息到达 → hook 检查窗口是否
 * 需要立项捕获 → 注入提示词让 LLM 调 reqboard_capture 弹三问 → 直接建 REQ），未命中维持静态引导。
 * 向后兼容：不传 pending 时行为与旧版完全一致（capture.test.ts 三分支不变）。
 */
export function captureSectionText(
  ledger: ReqboardLedger,
  context: unknown,
  pending?: PendingCaptureMessage | undefined,
): string {
  const windowKey = windowKeyFromContext(context as { agent?: { id?: unknown }; scope?: unknown })
  if (!windowKey) {
    // 【诊断日志-节点5】返回空串原因：windowKey undefined
    captureDiag(`reqboard-capture [NODE-5]: captureSectionText returns '' (reason: windowKey=undefined)`);
    return '';
  }
  if (isWindowBound(ledger, windowKey)) {
    captureDiag(`reqboard-capture [NODE-5]: captureSectionText returns '' (reason: windowBound=true, windowKey=${windowKey.slice(0, 16)})`);
    return '';
  }
  if (hasPendingSuggestion(ledger, windowKey)) {
    captureDiag(`reqboard-capture [NODE-5]: captureSectionText returns '' (reason: hasPendingSuggestion=true, windowKey=${windowKey.slice(0, 16)})`);
    return '';
  }
  if (pending && pending.windowKey === windowKey && pending.text.trim().length > 0) {
    const promptText = capturePromptForMessage(windowKey, pending.text);
    // 【诊断日志-节点5】返回动态提示词
    captureDiag(`reqboard-capture [NODE-5]: captureSectionText returns DYNAMIC PROMPT (windowKey=${windowKey.slice(0, 16)}, text.length=${promptText.length}, pending.text.length=${pending.text.length})`);
    return promptText;
  }
  const guidanceText = captureGuidanceText(windowKey);
  captureDiag(`reqboard-capture [NODE-5]: captureSectionText returns STATIC GUIDANCE (windowKey=${windowKey.slice(0, 16)}, text.length=${guidanceText.length})`);
  return guidanceText;
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
    '- draft 立项 → brainstorming 需求分析（探边界/方案）→ design 设计（只写设计文档）→',
    '  decomposing 拆分（写拆分计划 → 人批准 → 落库任务 DAG）→ implementing 执行 → accepting 验收 → done 完成；',
    '- 方案谈定 → reqboard_move 到 design（设计属于这个阶段）；',
    '',
    '设计阶段（2026-09-21 用户裁定：只写设计文档，不写计划）：',
    '- 把设计写进 docs/requirements/<REQ>/design/ 目录（按类型模板：架构/接口/数据模型等）；',
    '- 写完调 reqboard_ask_confirm（target=artifact, kind=design）弹框请人确认设计——确认后进入拆分；',
    '',
    '拆分阶段（拆分计划在这里写 · 唯一需要人点头的地方）：',
    '- 把设计落成拆分计划 → reqboard_submit(kind=plan)（path = docs/requirements/<REQ>/decomposition.md，',
    '  summary = 一段人能读懂的目标+做法，tasks = 将来要落库的任务表：',
    '  key/title/phase/side/depends_on/acceptance，粒度与依赖在这里定死）；',
    '- 提交后调 reqboard_ask_confirm（target=plan）弹框请人批准（看板「批准计划」同样有效）',
    '  ——未批准时 reqboard_decompose 被代码级拒绝；',
    '- 批准后自动落库任务卡并进入实施（不传 tasks = 直接落库批准的计划；',
    '  传了 tasks 则必须与计划 key 一致，防止「批了 A 落库 B」）；',
    '- 计划要改 → 重新 reqboard_submit(kind=plan)（旧批准自动作废，需重新批准）。',
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
 * 指示 LLM 判断该输入是否值得立项——值得则【调 reqboard_capture（pm 专有立项弹框）
 * 一次完成「立项三问 + 创建 + 绑定」】：三问为「需求名称」（候选由本条消息上下文
 * 推导、最贴切一项置首推荐、允许自定义输入）「需求类型」（feature/bug/doc/refactor/
 * spike/chore）「提示词难度」（simple/standard/advanced/expert）；**用户作答即立项确认**，
 * 工具在同一次调用内创建 REQ 并绑定本窗口（创建即立项，无待归类/建议卡中间态，看板
 * 立即可见）。
 *
 * **措辞已硬化（2026-09-20 t-3e11bf E2E 走查后的返工）**：走查实测（窗口 session-361c2879，
 * 15:23–15:30 四个回合）——hook 登记、pending 命中、本段注入**全部正常**，但窗口内 35 次
 * PTC 子调用只有 read/grep，**零次 reqboard_capture**；其中"修复 FR-6 任务状态机"这种
 * 明确工作意图也被模型判成"对当前审查的追问"而跳过。根因：原文案是"请先判断**可能**包含
 * 值得立项的意图 / 只是闲聊则正常回复"——二元裁量 + 零后果，模型默认选"先答问题"。
 * 故改为：①必须显式裁定（判不准按值得立项处理）②值得立项时**本回合第一个工具调用**即
 * reqboard_capture ③不立项时必须在回复首行写明理由（把沉默变成可审计表态）。
 * 判定仍留给 LLM（窗口 agent 自身回合），hook 只保证确定性触发。全部字面量。
 */
export function capturePromptForMessage(windowKey: string, text: string): string {
  const trimmed = text.trim().replace(/\s+/g, ' ')
  const snippet = trimmed.slice(0, 300)
  return [
    `## 项目捕获（reqboard · 本窗口 ${windowKey.slice(0, 16)} 检测到用户新输入）`,
    '',
    '用户刚发来一条消息。**本回合你必须先做一次显式裁定、再回答用户**——沉默跳过等于',
    '本回合未完成（会被留痕，走查时按失败计）。',
    '',
    '**判据（只看本条消息里有没有"要动手做的事"，不看它是否夹在提问里）**：',
    '- 出现「修复 / 改 / 新增 / 实现 / 重构 / 优化 / 补充 / 调研 / 做 / 支持」+ **具体对象**，',
    '  或用户要求对某个模块 / 功能 / 文档做出改动 → 判为**值得立项**，走下面「值得立项时」；',
    '- 纯提问、咨询完成度、追问进度、继续之前话题、闲聊 → 判为**不立项**，走「不立项时」。',
    '',
    '**值得立项时（必须执行）**：',
    '1) **本回合的第一个工具调用必须是 reqboard_capture**（pm 专有立项弹框）——',
    '   不要先回答问题、不要先做分析、不要先调别的工具；',
    '   问题一「需求名称」：把由本条消息推导出的候选标题经 title_options 传入（最多 3 个），',
    '   最贴切的一项放首位（弹框里标注「推荐」），允许用户改选或自定义输入；',
    '   问题二「需求类型」：选项 feature / bug / doc / refactor / spike / chore；',
    '   问题三「提示词难度」：选项 simple / standard / advanced / expert；',
    '2) 用户作答后（= 立项确认），本工具在**同一次调用内**创建需求并绑定本窗口——',
    '   不要再另调 reqboard_create，也不要用宿主通用弹框（两段式会在答案与创建之间断链）；',
    '3) 弹框通道不可用时该工具返回 fallback=board：此时改为文字向用户取值，再调 reqboard_create',
    '   （title = 需求名称，category = 需求类型，prompt_difficulty = 难度，',
    '   summary = 本次工作摘要，reason = 立项依据（引用本条消息原文））。',
    '',
    '**不立项时（同样必须显式表态，不许沉默）**：',
    '- 在回复的**第一行**写明「本条不立项：<一句话理由>」，然后才正常回答用户；',
    '- **判不准时按"值得立项"处理**——弹框本身就是一次询问，用户可以在框里选"不需要"；',
    '  宁可多问一次，也不要替用户决定"这件事不用立项"。',
    '',
    '本次待裁定的用户消息（节选，最多 300 字）：',
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
    '直接调 reqboard_capture（pm 专有立项弹框）——一次调用弹出「立项三问」并在同一次调用内',
    '完成创建与窗口绑定：问题一「需求名称」（可经 title_options 传候选，最贴切一项推荐置首，',
    '允许自定义输入）；问题二「需求类型」（feature / bug / doc / refactor / spike / chore）；',
    '问题三「提示词难度」（simple / standard / advanced / expert）。用户作答即立项确认',
    '（创建即立项，无待归类/建议卡中间态），**不需要**再补调 reqboard_create。',
    '弹框通道不可用时该工具返回 fallback=board：此时改为文字向用户取值后再调 reqboard_create',
    '（title / category / prompt_difficulty / summary / reason）。',
    '',
    '判不准是否值得立项时按"值得"处理——直接调 reqboard_capture 弹框问用户（框里可以选"不需要"，',
    '比沉默跳过安全）；仅闲聊或询问已有需求进度时无需弹框、无需立项。',
  ].join('\n')
}