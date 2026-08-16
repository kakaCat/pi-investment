import type { ToolDefinition } from '../index.js';
import { Type } from '@sinclair/typebox';
import { getAgentOSClient } from '../../../infrastructure/agent-os/client.js';
import { findSkillByName } from '../../../core/bootstrap/skill-registry.js';

export const skillGetTool: ToolDefinition = {
  name: 'skill_get',
  label: '获取 Skill 内容',
  description: `
获取 skill 的完整内容（包括指令、参数、示例等）。

用途：
- 查看 skill 的详细指令
- 了解 skill 的执行逻辑
- 调试 skill 内容
- 在执行任务前查看 skill 的具体要求

返回：skill 的完整 markdown 内容。
`,
  parameters: Type.Object({
    name: Type.String({
      description: 'Skill 名称（如 portfolio-review, market-analysis）',
    }),
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

      // 2. 从 Agent OS 获取完整内容
      const skill = await client.skills.get(metadata.id);

      const result = {
        id: skill.id,
        name: skill.name,
        description: skill.description,
        version: skill.version,
        content: skill.content,
        updated_at: skill.updated_at,
        category: skill.category,
      };

      return {
        content: [{ type: "text" as const, text: `# ${skill.name}\n\n${skill.content}` }],
        details: result,
      };
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: `Failed to get skill: ${error.message}` }],
        details: { error: error.message },
      };
    }
  },
};
