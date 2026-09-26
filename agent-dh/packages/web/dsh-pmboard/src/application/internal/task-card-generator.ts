/**
 * 任务卡生成器（需求追溯性改进 - 2026-09-26）
 * 
 * 负责从拆分计划生成任务卡骨架，自动填充追溯信息：
 * - 设计方案引用
 * - 需求背景
 * - 设计落点
 * - 测试用例
 * 
 * @module dsh-pmboard/application/internal/task-card-generator
 */
import type { DocsReader } from './content-gates.js'
import type { RequirementRecord, TaskRecord } from '../../shared/protocol.js'
import {
  extractAllDesignSections,
  findDesignSectionsForFRs,
  type DesignSection,
} from './content-trace.js'
import { parseDocument, extractClauseDefinitions } from './content-gates.js'

/**
 * 计划任务（来自拆分计划）
 */
export interface PlanTask {
  key: string
  title: string
  description?: string
  implementation?: string
  acceptance?: string
  phase?: string
  side?: string
  requirement_refs?: string[]
  depends_on?: string[]
}

/**
 * 任务卡占位符数据
 */
export interface TaskCardPlaceholders {
  TASK_ID: string
  TASK_TITLE: string
  TASK_DESCRIPTION: string
  DESIGN_REFERENCE: string
  REQUIREMENT_BACKGROUND: string
  DESIGN_SUMMARY: string
  EXPECTED_IMPACT: string
  TASK_PHASE: string
  TASK_SIDE: string
  REQUIREMENT_REFS: string
  DESIGN_SERVES: string
  TEST_CASES: string
  ACCEPTANCE_CRITERIA: string
  IMPLEMENTATION_PLAN: string
  DEPENDS_SUMMARY: string
  EXECUTOR_HINT: string
  RISKS: string
  ROLLBACK_ACTIONS: string
}

/**
 * 从需求文档提取条款内容
 */
function extractRequirementClause(
  requirementDoc: string,
  frId: string
): { title: string; description: string } | null {
  // 匹配格式：- **FR-1 标题**：描述内容
  const pattern = new RegExp(
    `\\*\\*${frId}[:\\s]+([^\\*]+?)\\*\\*[:\\s]*(.+?)(?=\\n-|\\n\\*\\*|$)`,
    's'
  )
  const match = requirementDoc.match(pattern)
  if (!match) return null
  
  return {
    title: match[1].trim(),
    description: match[2].trim()
  }
}

/**
 * 提取章节摘要（前3-5行）
 */
function extractSectionSummary(content: string, maxLines: number = 5): string {
  const lines = content.split('\n').filter(l => l.trim().length > 0)
  return lines.slice(0, maxLines).join('\n')
}

/**
 * 生成任务卡占位符数据
 * 
 * @param planTask 计划任务
 * @param taskId 分配的任务ID
 * @param docs 文档读取器
 * @param requirement 需求记录
 * @returns 占位符数据
 */
export function generateTaskCardPlaceholders(
  planTask: PlanTask,
  taskId: string,
  docs: DocsReader,
  requirement: RequirementRecord
): TaskCardPlaceholders {
  const frRefs = planTask.requirement_refs || []
  const designDir = `docs/requirements/${requirement.id}/design`
  const requirementPath = `docs/requirements/${requirement.id}/requirement.md`
  
  // 1. 提取设计章节
  const designSections = extractAllDesignSections(docs, designDir)
  const relatedSections = findDesignSectionsForFRs(designSections, frRefs)
  
  // 2. 读取需求文档
  const requirementDoc = docs.read?.(requirementPath) || ''
  
  // 3. 生成设计引用
  let designReference = ''
  let designSummary = ''
  let designServes = ''
  
  if (relatedSections.length > 0) {
    const mainSection = relatedSections[0]
    designReference = `${mainSection.file} § ${mainSection.section} "${mainSection.title}"`
    designSummary = extractSectionSummary(mainSection.content, 5)
    designServes = relatedSections
      .map(s => `${s.file}#${s.section}`)
      .join(', ')
  } else if (frRefs.length > 0) {
    designReference = `（从需求 ${frRefs.join(', ')} 拆分而来，参考设计文档）`
    designSummary = '（设计文档中暂无明确章节标注）'
    designServes = '（待补充设计落点）'
  }
  
  // 4. 生成需求背景
  let requirementBackground = ''
  if (frRefs.length > 0 && requirementDoc) {
    const clauses = frRefs
      .map(fr => {
        const clause = extractRequirementClause(requirementDoc, fr)
        return clause ? `${fr} ${clause.title}` : fr
      })
      .join('；')
    requirementBackground = clauses
    
    // 提取第一个条款的详细说明
    if (frRefs[0]) {
      const firstClause = extractRequirementClause(requirementDoc, frRefs[0])
      if (firstClause) {
        requirementBackground += `\n\n${firstClause.description}`
      }
    }
  } else {
    requirementBackground = '（待补充需求背景）'
  }
  
  // 5. 生成预期影响（从设计章节提取）
  let expectedImpact = ''
  if (relatedSections.length > 0) {
    // 尝试从设计内容中提取"影响"相关的段落
    const content = relatedSections[0].content
    const impactMatch = content.match(/(?:影响|变更|改动|调整)[：:](.*?)(?=\n#{1,3}|$)/s)
    if (impactMatch) {
      expectedImpact = impactMatch[1].trim().split('\n').slice(0, 3).join('\n')
    }
  }
  if (!expectedImpact) {
    expectedImpact = '（待补充：改动会影响哪些模块/接口）'
  }
  
  // 6. 组装占位符
  return {
    TASK_ID: taskId,
    TASK_TITLE: planTask.title,
    TASK_DESCRIPTION: planTask.description || planTask.title,
    DESIGN_REFERENCE: designReference,
    REQUIREMENT_BACKGROUND: requirementBackground,
    DESIGN_SUMMARY: designSummary,
    EXPECTED_IMPACT: expectedImpact,
    TASK_PHASE: planTask.phase || 'implement',
    TASK_SIDE: planTask.side || 'fullstack',
    REQUIREMENT_REFS: frRefs.join(', '),
    DESIGN_SERVES: designServes,
    TEST_CASES: '（待补充：TC-x）',
    ACCEPTANCE_CRITERIA: planTask.acceptance || '（待补充验收标准）',
    IMPLEMENTATION_PLAN: planTask.implementation || '（待补充实施方案）',
    DEPENDS_SUMMARY: planTask.depends_on?.length
      ? `依赖任务：${planTask.depends_on.join(', ')}`
      : '（无依赖）',
    EXECUTOR_HINT: '优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史',
    RISKS: '（待补充风险）',
    ROLLBACK_ACTIONS: '（待补充回退方案）'
  }
}

/**
 * 使用占位符渲染任务卡模板
 * 
 * @param template 模板内容（包含 {{PLACEHOLDER}} 占位符）
 * @param placeholders 占位符数据
 * @returns 渲染后的内容
 */
export function renderTaskCard(
  template: string,
  placeholders: TaskCardPlaceholders
): string {
  let result = template
  
  // 替换所有占位符
  for (const [key, value] of Object.entries(placeholders)) {
    const placeholder = `{{${key}}}`
    result = result.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), value)
  }
  
  return result
}

/**
 * 生成任务卡骨架（完整流程）
 * 
 * @param planTask 计划任务
 * @param taskId 分配的任务ID
 * @param docs 文档读取器
 * @param requirement 需求记录
 * @param templateContent 模板内容
 * @returns 渲染后的任务卡内容
 */
export function generateTaskCardSkeleton(
  planTask: PlanTask,
  taskId: string,
  docs: DocsReader,
  requirement: RequirementRecord,
  templateContent: string
): string {
  const placeholders = generateTaskCardPlaceholders(planTask, taskId, docs, requirement)
  return renderTaskCard(templateContent, placeholders)
}
