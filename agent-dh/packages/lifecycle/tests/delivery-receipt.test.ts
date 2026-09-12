import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { buildDeliveryReceipt, promptDigest } from '../src/deliveryReceipt';

/**
 * 任务投递回执防污染回归（2026-09-12，w-adb088f2）
 *
 * 缺陷：回执把**整段 prompt**写进记忆库 → 检索被任务文本污染（R-008 拿到任务信封而非知识）。
 * 契约：回执不得包含 prompt 全文（只留 sha256 摘要+长度+短预览），且写入点必须走 builder。
 */

const LONG_PROMPT = ['【定时任务】evolution-distill-daily', 'A'.repeat(200), 'UNIQUE_TAIL_MARKER_600919'].join(' | ');

describe('buildDeliveryReceipt', () => {
  it('不含 prompt 全文（第 61 字之后的独有内容不得出现）', () => {
    const receipt = buildDeliveryReceipt({ task: 'evolution-distill-daily', task_id: 't1', prompt: LONG_PROMPT, window: 'w-x' });
    const blob = JSON.stringify(receipt);
    expect(blob).not.toContain('UNIQUE_TAIL_MARKER_600919');
    expect(blob).not.toContain('A'.repeat(100));
  });

  it('保留可溯标识：task/task_id/window/时间/执行者/摘要', () => {
    const receipt: any = buildDeliveryReceipt({
      task: 'evolution-distill-daily', task_id: 'task-42', prompt: LONG_PROMPT, window: 'w-adb088f2',
      fired_at: '2026-09-12T15:00:00Z', executor: { mode: 'online' },
    });
    expect(receipt.task).toBe('evolution-distill-daily');
    expect(receipt.task_id).toBe('task-42');
    expect(receipt.window).toBe('w-adb088f2');
    expect(receipt.fired_at).toBe('2026-09-12T15:00:00Z');
    expect(receipt.executor).toEqual({ mode: 'online' });
    expect(receipt.delivered).toBe(true);
    expect(String(receipt.prompt_sha256)).toHaveLength(16);
    expect(receipt.prompt_length).toBe(LONG_PROMPT.length);
    // 2026-09-13 第三批审阅 A8：预览收紧到 24 字（60 字已足够长到污染检索）
    expect(String(receipt.prompt_preview).length).toBeLessThanOrEqual(24);
  });

  it('摘要稳定且可区分不同 prompt', () => {
    expect(promptDigest('abc').prompt_sha256).toBe(promptDigest('abc').prompt_sha256);
    expect(promptDigest('abc').prompt_sha256).not.toBe(promptDigest('abd').prompt_sha256);
  });

  it('extra 字段透传（离线信箱等场景）', () => {
    const receipt: any = buildDeliveryReceipt({ task: 'x', prompt: 'p', extra: { from: 'w-a', message: 'hi' } });
    expect(receipt.from).toBe('w-a');
    expect(receipt.message).toBe('hi');
  });
});

describe('写入点源码级护栏', () => {
  it('lifecycle 的 memory_write 回执必须走 buildDeliveryReceipt（禁止直传 prompt 全文）', () => {
    const here = path.dirname(fileURLToPath(import.meta.url));
    const src = fs.readFileSync(path.join(here, '../src/index.ts'), 'utf-8');
    // 只约束"任务投递回执"（title 含 reminder）——index.ts 另有窗口上线/信箱补投两处
    // memory_write 与 prompt 无关，不强行改造。
    const segments = src.split("osWrite('memory_write'").slice(1);
    const reminderSegs = segments.filter((s) => s.slice(0, 300).includes('reminder'));
    expect(reminderSegs.length).toBeGreaterThan(0);
    for (const seg of reminderSegs) {
      expect(seg.slice(0, 600)).toContain('buildDeliveryReceipt');
    }
  });
});
