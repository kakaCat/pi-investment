/**
 * TaskExecuteTool（REQ-260927144541-0481 FR-1 / design I-2）——reqboard_task_execute，**兼容别名**。
 *
 * 历史：原「6 阶段 workflow 工具」路径已下线（它依赖被禁用的 ctx.tools.workflow，且生成的脚本
 * 用了引擎不存在的 ctx.subagent——design/workflow-engine-contract §4 两条真实踩坑）。此后本工具
 * 虽自称"兼容别名"，实际却**另跑一套**：不写 autoRun、不返回 run_id、返回体也不同形（P4）——
 * 调用方按名字选工具会踩坑，"等价"只写在注释里。
 *
 * 现改为**真委托**：直接复用 reqboard_task_run 的同一 factory 产物（同 parameters / 同 output /
 * 同 execute），只换工具名与描述——autoRun 副作用与 job_id/run_id 因此天然一致，不存在第二套实现。
 * 保留工具名而不是删除：删除会让存量调用方硬断（decision D-1 选 A）。
 *
 * 注意：不写 `return { … }` 响应字面量——output-contract 的静态扫描会把工具返回体的顶层键
 * 当作**协议响应键**校验，而这种包装返回的是"工具对象"、不是响应体（新建对象只会制造假阳性）。
 *
 * @module dsh-pmboard/tools/TaskExecuteTool
 */
import type { UseCaseDeps } from '../../application/ports.js'
import { defineAdvanceTool } from '../AdvanceTool/AdvanceTool.js'

const ALIAS_DESCRIPTION = [
  '【已弃用：等价 reqboard_task_run，请改用后者】推进本窗口需求下的自动实施链',
  '（投递式，立即返回）：投递后台任务执行当前 ready 的一张子卡。参数给 task_id（父卡）或 requirement_id；',
  '⚠️ 调用即写 req.autoRun=true（开启自动链）；投递≠完成，查询运行态用 reqboard_run_status。',
].join('')

/** 已弃用的兼容别名：参数、返回体、autoRun 副作用与 reqboard_task_run 逐字一致。 */
export function defineTaskExecuteTool(deps: UseCaseDeps) {
  const impl = defineAdvanceTool(deps) as unknown as Record<string, unknown>
  return Object.assign({}, impl, { name: 'reqboard_task_execute', description: ALIAS_DESCRIPTION })
}
