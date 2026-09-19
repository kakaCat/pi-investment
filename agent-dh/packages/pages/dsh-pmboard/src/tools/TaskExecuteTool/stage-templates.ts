/**
 * 阶段定义模板
 */

import type { StageDefinition } from './types.js'

export const BACKEND_STAGES: StageDefinition[] = [
  {
    stage: 1,
    name: '需求分析',
    description: '分析任务目标、验收标准和关键风险',
    promptTemplate: `任务：{{title}}

请分析：
1. 任务的核心目标
2. 验收标准：{{acceptance}}
3. 关键风险

输出 JSON：{ "objective": "...", "risks": [...] }`
  },
  {
    stage: 2,
    name: '方案设计',
    description: '设计技术方案',
    promptTemplate: `基于需求分析：{{stage1_output}}

请设计：
1. 数据结构
2. 关键函数
3. 模块划分`
  },
  {
    stage: 3,
    name: '代码实现',
    description: '编写核心代码',
    promptTemplate: `基于设计：{{stage2_output}}

请实现核心代码`
  },
  {
    stage: 4,
    name: '单元测试',
    description: '编写和运行测试',
    promptTemplate: `验收标准：{{acceptance}}

请编写并运行单元测试`
  },
  {
    stage: 5,
    name: '集成测试',
    description: '运行验收测试',
    promptTemplate: `运行验收测试：{{acceptance}}`
  },
  {
    stage: 6,
    name: '文档汇报',
    description: '更新文档并汇报',
    promptTemplate: `生成完工汇报（JSON）：
{ "summary": "...", "files_changed": [...] }`
  }
]

export const DOC_STAGES: StageDefinition[] = [
  {
    stage: 1,
    name: '需求分析',
    description: '分析文档目标',
    promptTemplate: `分析文档目标和受众`
  },
  {
    stage: 2,
    name: '内容规划',
    description: '规划文档结构',
    promptTemplate: `规划文档大纲`
  },
  {
    stage: 3,
    name: '编写文档',
    description: '编写内容',
    promptTemplate: `编写完整文档`
  },
  {
    stage: 4,
    name: '审校',
    description: '审校完善',
    promptTemplate: `审校并完善`
  }
]

export function getStageTemplate(side: string): StageDefinition[] {
  return side === 'doc' ? DOC_STAGES : BACKEND_STAGES
}
