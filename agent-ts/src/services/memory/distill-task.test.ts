/**
 * Memory Distillation 提示词测试（2026-10-05 重写 · REQ-261004202231-bb99）
 *
 * 主题变化：原来验证 runQuantV2 的 memory_distill_inputs / memory_distill_candidates 命令契约；
 * 这两个 v2 端点已随记忆子系统下线，蒸馏链路改走 agent-os（memory_search 读入 / memory_write 提交）。
 * 现在测的是「提示词确实不再指向已退役端点，且指向了新通道」。
 */
import { describe, it, expect } from '@jest/globals';
import { WEEKLY_MEMORY_DISTILL_PROMPT } from '../scheduler/tasks/memory-distill-task.js';

describe('WEEKLY_MEMORY_DISTILL_PROMPT（agent-os 版）', () => {
  it('不再指示调用已退役的 v2 蒸馏命令', () => {
    expect(WEEKLY_MEMORY_DISTILL_PROMPT).not.toContain('memory_distill_inputs');
    expect(WEEKLY_MEMORY_DISTILL_PROMPT).not.toContain('memory_distill_candidates');
  });

  it('指向 agent-os 通道（memory_search 读入 / memory_write 提交）', () => {
    expect(WEEKLY_MEMORY_DISTILL_PROMPT).toContain('memory_search');
    expect(WEEKLY_MEMORY_DISTILL_PROMPT).toContain('memory_write');
  });

  it('保留蒸馏的目标与候选格式要求', () => {
    expect(WEEKLY_MEMORY_DISTILL_PROMPT).toContain('周记忆蒸馏任务');
    expect(WEEKLY_MEMORY_DISTILL_PROMPT).toContain('触发条件');
  });
});
