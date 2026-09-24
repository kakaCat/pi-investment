/**
 * 模板地址系统类型定义
 * Domain 局部结构类型，不 import shared
 */

/** 模板文件引用（相对 templates/ 的路径） */
export interface TemplateRef {
  /** 相对路径，如 'implementing/task-card.md' */
  relPath: string;
  /** 模板用途描述 */
  description?: string;
}

/** 文档类型引用 */
export interface DocRef {
  /** 文档类型：requirement/design/plan 等 */
  kind: string;
  /** 绝对路径（工作区相对） */
  path: string;
}

/** 地址段输入（节点注入时的参数） */
export interface AddressSectionInput {
  /** 需求 ID */
  requirementId: string;
  /** 需求类型 */
  category: 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore';
  /** 当前节点阶段 */
  stage: string;
}

/** 上游数据源 */
export interface UpstreamSource {
  /** 上游文档类型 */
  docKind: string;
  /** 上游文档路径 */
  docPath: string;
}
