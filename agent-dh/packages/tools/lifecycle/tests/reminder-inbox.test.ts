import { describe, expect, it } from 'vitest';
import {
  classifyInboxItem,
  collectDeliveredKeys,
  deliveryKey,
  parsePayload,
} from '../src/reminder-inbox.js';

/**
 * 提醒收件箱判定故障注入测试（2026-10-07）
 *
 * 背景（均为实测复现，见 memory：空提醒自循环核验）：
 *  - 2026-10-07 19:04-19:13 每分钟一条空提醒：收件箱检索（q=reminder，服务端 tag 过滤是
 *    no-op、q 为模糊检索）命中的 16 条里 15 条是回执/知识记录，唯一被投递的是一条
 *    「mainline 2026-10-07: ...」知识记录——它是 JSON、无 delivered、无 task/prompt，
 *    旧守卫（只有 !p || p.delivered）拦不住 → 每分钟投递一次并留下空回执。
 *  - wip d7c7154a 引入的回归：去重收集写成 `if (ep.delivered) continue;`（把回执全排除），
 *    导致 ① 去重失效 ② 模糊检索带进来的待投递信件被自己标记为已投递而首投即跳过
 *    （2026-10-07 探针信件 7 分钟零投递的实测原因）。
 */

const receipt = (task?: string, fired_at?: string, extra: Record<string, unknown> = {}) => ({
  content: JSON.stringify({
    task,
    task_id: task ? `tid-${task}` : undefined,
    fired_at,
    delivered: true,
    delivered_at: '2026-10-07T19:04:31.000Z',
    executor: { mode: 'direct' },
    ...extra,
  }),
});
const letter = (task: string | undefined, prompt: string | undefined, fired_at = '2026-10-07T19:50:00+08:00') => ({
  content: JSON.stringify({ task, task_id: 'os-1', prompt, fired_at, window: 'investor-session-x' }),
});
/** 空提醒真驱动记录：纯知识 JSON，无 task/prompt/delivered */
const knowledgeRecord = {
  content: JSON.stringify({ date: '2026-10-07', sectors: ['玻璃行业', '船舶制造', '传媒娱乐'] }),
};

describe('parsePayload', () => {
  it('JSON 字符串对象 → 解析；数组/标量/坏 JSON → null', () => {
    expect(parsePayload('{"a":1}')).toEqual({ a: 1 });
    expect(parsePayload({ a: 1 })).toEqual({ a: 1 });
    expect(parsePayload('[1,2]')).toBeNull();
    expect(parsePayload('"text"')).toBeNull();
    expect(parsePayload('{bad json')).toBeNull();
    expect(parsePayload(null)).toBeNull();
    expect(parsePayload(undefined)).toBeNull();
  });
});

describe('collectDeliveredKeys：只从回执收集键（回归防线）', () => {
  it('回执（delivered=true + task）→ 产生键', () => {
    const keys = collectDeliveredKeys([receipt('daily-scan', '2026-10-07T09:00:00+08:00')]);
    expect([...keys]).toEqual(['daily-scan|2026-10-07T09:00:00+08:00']);
  });

  it('回归：待投递信件自身出现在该批结果里时不得产生键（自抑制防线）', () => {
    const keys = collectDeliveredKeys([letter('lifecycle-verify-probe', '验证探针')]);
    expect(keys.size).toBe(0);
  });

  it('无 task 的回执不产生键（宁可不去重也不误抑制）', () => {
    const keys = collectDeliveredKeys([receipt(undefined, undefined)]);
    expect(keys.size).toBe(0);
  });

  it('fired_at 缺失时键仍可对齐（task| 形式）', () => {
    const keys = collectDeliveredKeys([receipt('t1', undefined)]);
    expect([...keys]).toEqual(['t1|']);
    const noFiredAt = { content: JSON.stringify({ task: 't1', prompt: 'p' }) };
    expect(deliveryKey(parsePayload(noFiredAt.content)!)).toBe('t1|');
    expect(classifyInboxItem(noFiredAt, keys).reason).toBe('dup-key');
  });

  it('坏 JSON / 非对象载荷被忽略，不抛异常', () => {
    expect(collectDeliveredKeys([{ content: '{oops' }, { content: '3' }, receipt('ok', 'T')]).size).toBe(1);
    expect(collectDeliveredKeys([]).size).toBe(0);
    expect(collectDeliveredKeys(undefined as any).size).toBe(0);
  });
});

describe('classifyInboxItem：投递判定', () => {
  it('空载荷知识记录（空提醒真驱动）→ skip empty-payload', () => {
    const d = classifyInboxItem(knowledgeRecord, new Set());
    expect(d.deliver).toBe(false);
    expect(d.reason).toBe('empty-payload');
  });

  it('task 与 prompt 都为空但 delivered 缺失 → 仍跳过（不得投递空提醒）', () => {
    expect(classifyInboxItem({ content: JSON.stringify({ task_id: 'x' }) }, new Set()).reason).toBe('empty-payload');
    expect(classifyInboxItem({ content: JSON.stringify({ task: '', prompt: '' }) }, new Set()).reason).toBe('empty-payload');
  });

  it('回执 → skip already-delivered', () => {
    expect(classifyInboxItem(receipt('t', 'F'), new Set()).reason).toBe('already-delivered');
  });

  it('坏 JSON → skip unparsable', () => {
    expect(classifyInboxItem({ content: 'nope' }, new Set()).reason).toBe('unparsable');
  });

  it('真信件（task + prompt，未投递）→ 投递', () => {
    const d = classifyInboxItem(letter('daily-scan', '扫描买点'), new Set());
    expect(d.deliver).toBe(true);
    expect(d.payload?.task).toBe('daily-scan');
    expect(d.key).toBe('daily-scan|2026-10-07T19:50:00+08:00');
  });

  it('仅有 prompt（无 task）的信件也要投递', () => {
    expect(classifyInboxItem(letter(undefined, '执行盘后复盘'), new Set()).deliver).toBe(true);
  });

  it('键命中回执 → skip dup-key（防每分钟重复投递）', () => {
    const keys = collectDeliveredKeys([receipt('daily-scan', '2026-10-07T19:50:00+08:00')]);
    const d = classifyInboxItem(letter('daily-scan', '扫描买点'), keys);
    expect(d.deliver).toBe(false);
    expect(d.reason).toBe('dup-key');
  });
});

describe('端到端重放：2026-10-07 真实收件箱快照', () => {
  it('旧守卫放行 3 条（其中 2 条空载荷 = 空提醒源头），新判定只放行真信件 1 条', () => {
    const probe = letter('lifecycle-verify-probe', '验证探针（收到后无需操作）');
    const inbox = [
      probe,                                                            // 探针，未投递
      receipt(undefined, undefined),                                    // 旧空回执 ×2
      receipt(undefined, undefined),
      { content: '{"id":"m1","title":"修复空提醒自循环"}' },            // 知识记录（无 task/prompt）
      knowledgeRecord,                                                  // ← 实测每分钟被投递的空提醒源头
      receipt('daily-scan', '2026-10-07T09:00:00+08:00'),               // 已投递信件的回执
    ];
    const execItems = [
      ...inbox.filter((x: any) => String(x.content).includes('"delivered":true')),
      probe,                                                            // 模糊检索把信件本身也带进来
    ];

    // 旧守卫（只有 !p || p.delivered）→ 放行 3 条：探针 + 2 条无 task/prompt 的知识记录
    const legacyDeliver = inbox.filter((x: any) => {
      const p = parsePayload(x.content);
      return !!p && p.delivered !== true;
    });
    expect(legacyDeliver.length).toBe(3);
    const legacyEmpty = legacyDeliver.filter((x: any) => {
      const p = parsePayload(x.content);
      return !p.task && !p.prompt;
    });
    expect(legacyEmpty.length).toBe(2);                              // 空提醒源头
    expect(parsePayload(legacyEmpty[1].content)?.sectors).toBeDefined(); // 实测那条 mainline 记录

    // 旧逻辑（wip 之后，去重反转）：探针因「自身出现在 exec 结果里」而被跳过
    const legacyKeys = new Set<string>();
    for (const e of execItems) {
      const ep = parsePayload((e as any).content);
      if (!ep || ep.delivered) continue;            // ← 反转的判据
      if (ep.task != null) legacyKeys.add(deliveryKey(ep));
    }
    expect(legacyKeys.has('lifecycle-verify-probe|2026-10-07T19:50:00+08:00')).toBe(true);
    expect(classifyInboxItem(probe, legacyKeys).reason).toBe('dup-key');  // 探针被自身抑制

    // 新判定：只有探针投递；空提醒源头被 empty-payload 拦下；已投递信件走 dup-key
    const keys = collectDeliveredKeys(execItems);
    const decisions = inbox.map((x) => classifyInboxItem(x, keys));
    const delivering = decisions.filter((d) => d.deliver);
    expect(delivering.length).toBe(1);
    expect(delivering[0].payload?.task).toBe('lifecycle-verify-probe');
    expect(decisions.filter((d) => d.reason === 'empty-payload').length).toBe(2);
    expect(decisions.filter((d) => d.reason === 'already-delivered').length).toBe(3);
  });
});
