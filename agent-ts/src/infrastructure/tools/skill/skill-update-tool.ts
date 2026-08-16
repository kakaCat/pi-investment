import type { ToolDefinition } from '../index.js';
import { Type } from '@sinclair/typebox';
import { getAgentOSClient } from '../../../infrastructure/agent-os/client.js';
import { findSkillByName } from '../../../core/bootstrap/skill-registry.js';
import { loadSkillRegistry } from '../../../core/bootstrap/skill-registry.js';

export const skillUpdateTool: ToolDefinition = {
  name: 'skill_update',
  label: '更新 Skill',
  description: `
更新 skill 内容（进化系统使用）。

⚠️ 注意：此操作会创建新版本，需谨慎使用。

用途：
- 进化系统改进 skill 指令
- 修复 skill 的问题
- 优化 skill 的执行逻辑
- 根据实践经验调整 skill 参数

返回：更新结果和新版本信息。
`,
  parameters: Type.Object({
    name: Type.String({
      description: 'Skill 名称',
    }),
    new_content: Type.String({
      description: '新的 skill 内容（完整 markdown，包括 frontmatter）',
    }),
    reason: Type.String({
      description: '修改原因（commit message）',
    }),
    author: Type.Optional(Type.String({
      description: '作者标识',
      default: 'evolution-system',
    })),
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const client = getAgentOSClient();

      // 1. 从注册表找到 ID
      const metadata = findSkillByName(params.name);
      if (!metadata) {
        return {
          content: [{ type: "text" as const, text: `Skill not found: ${params.name}. Use skill_list tool to see available skills.` }],
          details: { error: `Skill not found: ${params.name}` },
        };
      }

      // 2. 更新 skill（创建新版本）
      const newVersion = await client.skills.update(metadata.id, {
        content: params.new_content,
        author: params.author || 'evolution-system',
        commit_message: params.reason,
      });

      // 3. 重新加载 skill registry（以反映更新）
      await loadSkillRegistry();

      const result = {
        success: true,
        skill_id: metadata.id,
        skill_name: params.name,
        new_version: newVersion.version,
        content_hash: newVersion.content_hash,
        commit_message: params.reason,
      };

      const message = `✅ Skill updated: ${params.name} → ${newVersion.version}\nReason: ${params.reason}`;

      return {
        content: [{ type: "text" as const, text: message }],
        details: result,
      };
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: `Failed to update skill: ${error.message}` }],
        details: { error: error.message },
      };
    }
  },
};
