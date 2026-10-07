/**
 * 提醒收件箱判定（纯逻辑，2026-10-07 自 setupOsReminderPoller 抽出）
 *
 * 为什么抽出来：轮询器整体依赖 Agent OS 语义检索 + 在线 agent 树，无法在单测里端到端
 * 复现；但「这条记忆记录该不该当信件投递」是纯函数，而历史上出问题的恰恰是这层判定
 * （空载荷自循环、回执去重反转）。抽成纯函数后可故障注入实测。
 *
 * 数据口径（来自 agent-os-client MemoryClient.search → GET /api/v1/memory/search）：
 *   - 返回 { memories: [{ id, title, content, category, tags, created_at }], total }
 *   - content 是 JSON 字符串；信件 = {task, task_id, prompt, fired_at, window}（无 delivered）
 *   - 回执 = buildDeliveryReceipt() 产物，恒含 delivered: true 与 task/fired_at
 *   - 实测（2026-10-07）：服务端 tag 过滤是 no-op、q 为模糊/语义检索，因此收件箱里
 *     既有信件、回执，也有语义/时序邻近的无关记忆（后者常是纯 JSON 知识记录，不带
 *     task/prompt —— 这就是「空提醒」的来源）。
 */

export type InboxSkipReason = 'unparsable' | 'already-delivered' | 'empty-payload' | 'dup-key';

export interface InboxDecision {
  deliver: boolean;
  /** 解析后的载荷（deliver=true 时有意义） */
  payload: Record<string, any> | null;
  reason?: InboxSkipReason;
  /** 去重键 task|fired_at */
  key: string;
}

/** 解析记忆记录载荷；非 JSON / 非对象（null、数组、标量）一律返回 null */
export function parsePayload(content: unknown): Record<string, any> | null {
  try {
    const p = typeof content === 'string' ? JSON.parse(content) : content;
    if (!p || typeof p !== 'object' || Array.isArray(p)) return null;
    return p as Record<string, any>;
  } catch {
    return null;
  }
}

/** 去重键：task|fired_at（空值用空串占位，保证两侧可对齐） */
export function deliveryKey(p: Record<string, any> | null): string {
  return `${p?.task ?? ''}|${p?.fired_at ?? ''}`;
}

/**
 * 从「已投递」查询结果里收集去重键。
 *
 * ⚠️ 只认回执（delivered === true）——回执是投递的唯一凭据。
 * 2026-10-07 回归（wip d7c7154a 引入，本次修正）：曾把判据写成 `if (ep.delivered) continue;`，
 * 即把回执全部排除、只从**未投递的信件自身**收集键。后果两重：
 *   ① 去重彻底失效（回执不再产生键）→ 真信件每分钟重复投递（正是 2026-08-25 修过的老 bug）；
 *   ② 自抑制：模糊检索会把待投递信件本身带进这批结果，于是信件的键被自己「标记为已投递」，
 *      首投即被跳过（实测：探针信件 7 分钟零投递）。
 */
export function collectDeliveredKeys(execItems: any[]): Set<string> {
  const keys = new Set<string>();
  for (const e of execItems ?? []) {
    const ep = parsePayload(e?.content);
    if (!ep) continue;
    if (ep.delivered !== true) continue;      // 只认回执
    if (ep.task == null) continue;            // 无 task 的回执无法构成键（宁可不去重也不误抑制）
    keys.add(deliveryKey(ep));
  }
  return keys;
}

/** 判定单条收件箱记录：该投递吗？不该则给出可审计的原因 */
export function classifyInboxItem(item: any, deliveredKeys: Set<string>): InboxDecision {
  const p = parsePayload(item?.content);
  if (!p) return { deliver: false, payload: null, reason: 'unparsable', key: '' };
  if (p.delivered === true) return { deliver: false, payload: p, reason: 'already-delivered', key: deliveryKey(p) };
  // task 与 prompt 同时为空 → 不是任务，是邻近的无关联记忆/畸形回声；投递出去就是空提醒
  if (!p.task && !p.prompt) return { deliver: false, payload: p, reason: 'empty-payload', key: deliveryKey(p) };
  const key = deliveryKey(p);
  if (deliveredKeys.has(key)) return { deliver: false, payload: p, reason: 'dup-key', key };
  return { deliver: true, payload: p, key };
}
