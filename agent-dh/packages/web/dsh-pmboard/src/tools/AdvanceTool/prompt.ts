/**
 * AdvanceTool 提示词（REQ-260927144541-0481 FR-1）——reqboard_task_run 的工具描述：
 * 参数语义与 autoRun 副作用必须**写在描述里**（P1/P3：此前靠读源码才知道）。
 * @module dsh-pmboard/tools/AdvanceTool/prompt
 */
export const ADVANCE_PROMPT = [
  '用于：推进本窗口需求下的自动实施链——**唯一链入口**（reqboard_task_execute 是已弃用的别名）。',
  '投递式，立即返回：投递后台任务执行当前 ready 的一张子卡，返回 {status:"dispatched", job_id, run_id}。',
  '参数给 task_id（父卡，用于绑定与目标校验）或 requirement_id（缺省取本窗口绑定需求）；',
  '注意：本工具推进的是**该需求**当前 ready 事件，传同需求的任意一张卡等效。',
  '⚠️ 副作用：调用即写 req.autoRun=true（开启自动链，等价于"推倒第一张骨牌"）。',
  '⚠️ 投递≠完成：调用返回 <1s，实际执行在后台 ctx.jobs 中进行。',
  '查询运行态：用 reqboard_run_status（传 run_id 或 requirement_id）；看父子结构用 reqboard_task_tree；',
  '看单卡 run 结果用 reqboard_task_status。',
  '父卡链全部子卡完成后自动汇总收尾，全部父卡完成后需求自动进入验收。',
  '父卡开工时会自动展开固定子卡链（按需求类型）；已有子卡则幂等跳过。',
  '失败即暂停并告警（不自动重试），需人工处置后再次调用本工具续跑。',
].join('')
