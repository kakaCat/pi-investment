/**
 * 节点模板地址映射表
 * 规则：只登记门禁启用的节点×类型组合
 */

import type { TemplateRef } from './types';

interface NodeTemplateEntry {
  stage: string;
  category: 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore';
  templates: {
    requirement?: TemplateRef;
    designDocs?: TemplateRef[];
    decomposition?: TemplateRef;
    taskCard?: TemplateRef;
    testEvidence?: TemplateRef;
    review?: TemplateRef;
    verification?: TemplateRef;
    archiveIndex?: TemplateRef;
    retro?: TemplateRef;
  };
}

/**
 * NODE_TEMPLATES 映射表
 * 按节点（stage）组织，每个节点列出启用的类型及其模板
 */
export const NODE_TEMPLATES: NodeTemplateEntry[] = [
  // brainstorming - 需求文档
  { stage: 'brainstorming', category: 'feature', templates: { requirement: { relPath: 'brainstorming/feature.md' } } },
  { stage: 'brainstorming', category: 'bug', templates: { requirement: { relPath: 'brainstorming/bug.md' } } },
  { stage: 'brainstorming', category: 'doc', templates: { requirement: { relPath: 'brainstorming/doc.md' } } },
  { stage: 'brainstorming', category: 'refactor', templates: { requirement: { relPath: 'brainstorming/refactor.md' } } },
  { stage: 'brainstorming', category: 'spike', templates: { requirement: { relPath: 'brainstorming/spike.md' } } },
  { stage: 'brainstorming', category: 'chore', templates: { requirement: { relPath: 'brainstorming/chore.md' } } },

  // design - 设计文档（feature 5份，refactor 2份，其余无）
  {
    stage: 'design',
    category: 'feature',
    templates: {
      designDocs: [
        { relPath: 'design/architecture.md', description: '架构设计' },
        { relPath: 'design/data-model.md', description: '数据模型' },
        { relPath: 'design/interfaces.md', description: '接口设计' },
        { relPath: 'design/test-cases.md', description: '测试用例' },
        { relPath: 'design/use-cases.md', description: '用例设计' },
      ],
    },
  },
  {
    stage: 'design',
    category: 'refactor',
    templates: {
      designDocs: [
        { relPath: 'design/architecture.md', description: '架构设计' },
        { relPath: 'design/migration.md', description: '迁移方案' },
      ],
    },
  },

  // decomposing - 拆分计划（全类型通用）
  { stage: 'decomposing', category: 'feature', templates: { decomposition: { relPath: 'decomposing/decomposition.md' } } },
  { stage: 'decomposing', category: 'bug', templates: { decomposition: { relPath: 'decomposing/decomposition.md' } } },
  { stage: 'decomposing', category: 'doc', templates: { decomposition: { relPath: 'decomposing/decomposition.md' } } },
  { stage: 'decomposing', category: 'refactor', templates: { decomposition: { relPath: 'decomposing/decomposition.md' } } },
  { stage: 'decomposing', category: 'spike', templates: { decomposition: { relPath: 'decomposing/decomposition.md' } } },
  { stage: 'decomposing', category: 'chore', templates: { decomposition: { relPath: 'decomposing/decomposition.md' } } },

  // implementing - 任务卡、测试证据、评审（全类型通用）
  {
    stage: 'implementing',
    category: 'feature',
    templates: {
      taskCard: { relPath: 'implementing/task-card.md' },
      testEvidence: { relPath: 'implementing/test-evidence.md' },
      review: { relPath: 'implementing/review.md' },
    },
  },
  {
    stage: 'implementing',
    category: 'bug',
    templates: {
      taskCard: { relPath: 'implementing/task-card.md' },
      testEvidence: { relPath: 'implementing/test-evidence.md' },
      review: { relPath: 'implementing/review.md' },
    },
  },
  {
    stage: 'implementing',
    category: 'doc',
    templates: {
      taskCard: { relPath: 'implementing/task-card.md' },
      testEvidence: { relPath: 'implementing/test-evidence.md' },
      review: { relPath: 'implementing/review.md' },
    },
  },
  {
    stage: 'implementing',
    category: 'refactor',
    templates: {
      taskCard: { relPath: 'implementing/task-card.md' },
      testEvidence: { relPath: 'implementing/test-evidence.md' },
      review: { relPath: 'implementing/review.md' },
    },
  },
  {
    stage: 'implementing',
    category: 'spike',
    templates: {
      taskCard: { relPath: 'implementing/task-card.md' },
      testEvidence: { relPath: 'implementing/test-evidence.md' },
      review: { relPath: 'implementing/review.md' },
    },
  },
  {
    stage: 'implementing',
    category: 'chore',
    templates: {
      taskCard: { relPath: 'implementing/task-card.md' },
      testEvidence: { relPath: 'implementing/test-evidence.md' },
      review: { relPath: 'implementing/review.md' },
    },
  },

  // accepting - 验收清单（全类型通用）
  { stage: 'accepting', category: 'feature', templates: { verification: { relPath: 'accepting/verification.md' } } },
  { stage: 'accepting', category: 'bug', templates: { verification: { relPath: 'accepting/verification.md' } } },
  { stage: 'accepting', category: 'doc', templates: { verification: { relPath: 'accepting/verification.md' } } },
  { stage: 'accepting', category: 'refactor', templates: { verification: { relPath: 'accepting/verification.md' } } },
  { stage: 'accepting', category: 'spike', templates: { verification: { relPath: 'accepting/verification.md' } } },
  { stage: 'accepting', category: 'chore', templates: { verification: { relPath: 'accepting/verification.md' } } },

  // archived - 归档文档（全类型通用）
  {
    stage: 'archived',
    category: 'feature',
    templates: {
      archiveIndex: { relPath: 'archived/index.md' },
      retro: { relPath: 'archived/retro.md' },
    },
  },
  {
    stage: 'archived',
    category: 'bug',
    templates: {
      archiveIndex: { relPath: 'archived/index.md' },
      retro: { relPath: 'archived/retro.md' },
    },
  },
  {
    stage: 'archived',
    category: 'doc',
    templates: {
      archiveIndex: { relPath: 'archived/index.md' },
      retro: { relPath: 'archived/retro.md' },
    },
  },
  {
    stage: 'archived',
    category: 'refactor',
    templates: {
      archiveIndex: { relPath: 'archived/index.md' },
      retro: { relPath: 'archived/retro.md' },
    },
  },
  {
    stage: 'archived',
    category: 'spike',
    templates: {
      archiveIndex: { relPath: 'archived/index.md' },
      retro: { relPath: 'archived/retro.md' },
    },
  },
  {
    stage: 'archived',
    category: 'chore',
    templates: {
      archiveIndex: { relPath: 'archived/index.md' },
      retro: { relPath: 'archived/retro.md' },
    },
  },
];

/**
 * 查询指定节点的模板
 */
export function getNodeTemplates(stage: string, category: string): NodeTemplateEntry['templates'] | null {
  const entry = NODE_TEMPLATES.find(e => e.stage === stage && e.category === category);
  return entry?.templates || null;
}
