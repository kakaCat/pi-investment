import { createHash } from 'node:crypto';

/**
 * 任务投递回执构造（2026-09-12，w-adb088f2）
 *
 * 缺陷（实测）：lifecycle 在把定时任务/唤醒任务投递给窗口后，会把**整段 prompt**
 * 连同 task/task_id 一起写进记忆库作为投递回执（namespace=data）。后果：
 *  ① 记忆检索被任务文本污染 —— 关键词（如 pool_changed 事件里的股票代码）会命中
 *     这些回执，R-008「决策前检索历史教训」拿到的是任务信封而非知识（假命中）；
 *  ② 每日任务累积大量富文本，放大检索噪声（召回审计：wake-event 12 万次、注入率 7%）。
 *
 * 处理：回执只保留**可溯标识**（task/task_id/window/时间/执行者）+ prompt 摘要
 * （sha256 前 16 位、长度、前 60 字预览）。完整 prompt 仍由 OS 任务注册表持有，
 * 需要时按 task_id 取回——回执的职责是幂等与审计，不是存全文。
 */

export interface DeliveryReceiptInput {
  task?: string;
  task_id?: string;
  prompt?: string;
  window?: string;
  fired_at?: string;
  executor?: unknown;
  /** 额外透传字段（如离线信箱的 from/message 等） */
  extra?: Record<string, unknown>;
}

/** prompt 摘要：仅保留可识别信息，不落全文 */
export function promptDigest(prompt: string): {
  prompt_sha256: string;
  prompt_length: number;
  prompt_preview: string;
} {
  const text = String(prompt ?? '');
  return {
    prompt_sha256: createHash('sha256').update(text).digest('hex').slice(0, 16),
    prompt_length: text.length,
    prompt_preview: text.slice(0, 60),
  };
}

export function buildDeliveryReceipt(input: DeliveryReceiptInput): Record<string, unknown> {
  return {
    ...(input.extra ?? {}),
    task: input.task,
    task_id: input.task_id,
    window: input.window,
    fired_at: input.fired_at,
    ...promptDigest(String(input.prompt ?? '')),
    delivered: true,
    delivered_at: new Date().toISOString(),
    executor: input.executor,
    receipt_note: '回执不含 prompt 全文（防检索污染）；全文见 OS 任务注册表 payload.prompt',
  };
}
