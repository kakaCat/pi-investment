/**
 * SelfFinalizeTool - 提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface SelfFinalizeParams {
  reason: string;
  /**
   * 收尾动作（RFC 002 自修复闭环）：
   * - merge：把 self_restart 的 wip 检查点分支合并回基线分支，更新 last-known-good，清理 pending。验证通过后使用。
   * - rollback：放弃 wip 检查点分支的改动，回基线分支，清理 pending。验证失败后使用。
   * - exit：仅保存状态并退出（无 pending 合并/回滚动作，等效旧版 self_finalize）。
   * 默认 merge（有 pending 检查点分支时）；无 pending 时自动降级为 exit 语义（只保存状态）。
   */
  action?: 'merge' | 'rollback' | 'exit';
  save_state?: boolean;
}

export interface SelfFinalizeResult {
  success: boolean;
  message: string;
  finalized: boolean;
  /** 实际执行的收尾动作（merge/rollback/exit） */
  action: string;
  /** merge 后的基线分支 HEAD（仅 merge 成功时） */
  merged_hash?: string;
}

export const selfFinalizePrompt: ToolPrompt<SelfFinalizeParams, SelfFinalizeResult> = {
  description: '终止 Agent 生命周期并收尾：merge=合并 wip 检查点回基线并更新 last-known-good（验证通过后）；rollback=放弃 wip 改动回基线（验证失败后）；exit=仅保存状态退出。',
  useCases: ['验证通过后合并改动', '验证失败后放弃改动', '优雅关闭并退出'],
  examples: [
    {
      title: '验证通过，合并改动回 main',
      params: { reason: '验证通过', action: 'merge', save_state: true },
      expectedResult: '合并成功并更新 last-known-good',
    },
    {
      title: '验证失败，放弃改动',
      params: { reason: '验证失败', action: 'rollback', save_state: true },
      expectedResult: '回滚到基线并清理 pending',
    },
    {
      title: '仅保存状态并退出',
      params: { reason: '任务完成', action: 'exit', save_state: true },
      expectedResult: '返回终止确认',
    },
  ],
  parameters: {
    reason: { type: 'string', required: true, description: '终止原因' },
    action: { type: 'string', required: false, description: '收尾动作：merge（默认）/ rollback / exit', enum: ['merge', 'rollback', 'exit'] },
    save_state: { type: 'boolean', required: false, description: '是否保存状态' },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' },
        finalized: { type: 'boolean' },
        action: { type: 'string' },
        merged_hash: { type: 'string' },
      },
    },
    render: (args, data) => {
      let output = '## 🛑 终止已调度\n\n';
      output += `- **原因**: ${args.reason}\n`;
      output += `- **动作**: ${data.action}\n`;
      output += `- **保存状态**: ${args.save_state ? '是' : '否'}\n`;
      if (data.merged_hash) output += `- **合并 HEAD**: ${data.merged_hash}\n`;
      output += `- ${data.message}\n`;
      return [{ type: 'text', text: output }];
    },
  },
};
