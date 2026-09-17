/**
 * 验收标准可证伪校验 + 计划任务依赖引用校验（REQ-47939a t2，REQ-2e9473 t03 规则）。
 *
 * 为什么单独成文件：验收标准的"空话黑名单 + 可验证锚点"与"任务依赖只能引用前面已定义
 * 的 key"是两条纯判定规则，此前内嵌在 protocol.ts 的 normalizePlanTasks 里——规则与
 * 落库校验耦合在一起，无法独立单测。搬到 domain 后它们有唯一归属地（INV-2），
 * protocol 的 normalizePlanTasks 只负责调用。
 *
 * 返回结构化原因（{ ok:false, reason }）而不是布尔：拒绝理由要回给模型（design §5.4）。
 * 消息文案与搬迁前逐字一致（硬约束：拒绝条件与消息一律保持原样），故 reason 是**完整**
 * 的中文提示，调用方直接 bad(reason)。
 *
 * 纯函数：零 import、不碰时间与随机数。
 */

export type AcceptanceVerdict = { ok: true } | { ok: false; code: 'invalid_input'; reason: string }

/** 空话验收标准的显式黑名单（命中即拒，不管有没有锚点）。 */
export const VACUOUS_ACCEPTANCE = /^(功能)?正常$|^(没|无)问题$|一切正常|运行正常|正常使用|正常工作|没什么问题|看起来没问题/
import { fmt } from '../text/fmt.js'

/** 可验证锚点：文件路径 / 命令 / 断言关键词——验收标准必须至少含一个，否则无法证伪。 */
export const VERIFIABLE_ANCHOR = /\.(ts|tsx|js|mjs|cjs|md|html|json|py|go|css)\b|\b(npx|npm|pnpm|vitest|node|curl|grep|python3?|bash)\b|通过|拒绝|报错|可见|显示|包含|返回|等于|失败|成功|截图|输出|存在|被拒|拦截|告警|提示|落库|推进|不变|一致|单测|全绿|绿/

/** 验收标准可证伪校验（REQ-2e9473 t03）：空话打回。key 用于拼拒绝消息。 */
export function checkAcceptance(key: string, acceptance: string): AcceptanceVerdict {
  if (acceptance.length === 0) {
    return { ok: false, code: 'invalid_input', reason: fmt('计划任务 {key} 缺验收标准（acceptance）——"怎么算做完"必须可验证（跑什么命令、看什么输出/路径）', { key }) }
  }
  if (VACUOUS_ACCEPTANCE.test(acceptance)) {
    return { ok: false, code: 'invalid_input', reason: fmt('计划任务 {key} 的验收标准是空话（"{acceptance}"）——必须可证伪：写清跑什么命令、看到什么算过（如"npx vitest run 全绿"、"详情页含 8 个进度点"）', { key, acceptance }) }
  }
  if (!VERIFIABLE_ANCHOR.test(acceptance)) {
    return { ok: false, code: 'invalid_input', reason: fmt('计划任务 {key} 的验收标准缺少可验证锚点（"{acceptance}"）——至少含一项：文件路径（.ts/.md/…）、命令（npx/vitest/curl/…）或断言（通过/拒绝/可见/包含/返回/一致/不变…）', { key, acceptance }) }
  }
  return { ok: true }
}

/** 计划任务依赖引用的最小投影（有序；key 唯一由调用方第一遍校验保证）。 */
export interface PlanTaskRef {
  key: string
  dependsOn: readonly string[]
}

/**
 * 计划任务依赖引用校验（有序两遍之一）：自依赖 / 悬空引用 / **前向引用**。
 *
 * 事故 G（REQ-2e9473）：decompose 按任务表顺序把 key 解析为真实 id，前向引用解析不到 →
 * invalid_dag，落库时才炸。提交时就把顺序问题打回，顺带给出修法。
 *
 * 三条报错按任务顺序、依赖顺序短路由第一条命中——与搬迁前逐字一致（含报错优先级）。
 */
export function checkPlanTaskReferences(tasks: readonly PlanTaskRef[]): AcceptanceVerdict {
  const keys = new Set<string>()
  const keyIndex = new Map<string, number>()
  tasks.forEach((t, i) => { keys.add(t.key); keyIndex.set(t.key, i) })
  for (const t of tasks) {
    for (const dep of t.dependsOn) {
      if (dep === t.key) {
        return { ok: false, code: 'invalid_input', reason: fmt('计划任务 {key} 不能依赖自身', { key: t.key }) }
      }
      if (!keys.has(dep)) {
        return { ok: false, code: 'invalid_input', reason: fmt('计划任务 {key} 依赖了计划中不存在的 key：{dep}', { key: t.key, dep }) }
      }
      // 事故 G：decompose 按任务表顺序把 key 解析为真实 id，前向引用解析不到 → invalid_dag
      // 落库时才炸。提交时就把顺序问题打回，顺带给出修法。
      if ((keyIndex.get(dep) ?? -1) > (keyIndex.get(t.key) ?? -1)) {
        return { ok: false, code: 'invalid_input', reason: fmt('计划任务 {key} 依赖了后定义的 key：{dep}（前向引用）——decompose 按任务表顺序解析依赖，请把被依赖任务排在前面', { key: t.key, dep }) }
      }
    }
  }
  return { ok: true }
}
