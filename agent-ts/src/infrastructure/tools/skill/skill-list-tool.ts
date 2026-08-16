import type { ToolDefinition } from '../index.js';
import { Type } from '@sinclair/typebox';
import { getSkillRegistry, searchSkills } from '../../../core/bootstrap/skill-registry.js';

export const skillListTool: ToolDefinition = {
  name: 'skill_list',
  label: '列出 Skills',
  description: `
列出所有可用的 skills。可以通过关键词搜索。

用途：
- 查看系统有哪些 skills
- 搜索特定功能的 skill
- 了解 skill 的用途和分类

返回：包含 skill 元数据（id, name, description, category）的列表。
`,
  parameters: Type.Object({
    query: Type.Optional(Type.String({
      description: '搜索关键词（可选），用于模糊搜索 skill 名称或描述',
    })),
    category: Type.Optional(Type.String({
      description: '分类过滤（可选），如 general, analysis, trading 等',
    })),
  }),

  execute: async (_toolCallId: string, params: any) => {
    let skills = getSkillRegistry();

    // 搜索过滤
    if (params.query) {
      skills = searchSkills(params.query);
    }

    // 分类过滤
    if (params.category) {
      skills = skills.filter(s => s.category === params.category);
    }

    const result = {
      total: skills.length,
      skills: skills.map(s => ({
        id: s.id,
        name: s.name,
        description: s.description,
        category: s.category,
        schedule: s.metadata?.schedule,
      })),
    };

    return {
      content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
      details: result,
    };
  },
};
