/**
 * Workflow Schema 适配器
 * 
 * 封装引擎 agent(prompt, {schema}) 调用，
 * 确保子卡产出符合结构化契约
 */

/**
 * 子卡输出 Schema
 */
export interface SubtaskOutputSchema {
  /** 改动的文件路径列表（写集） */
  filesChanged: string[]
  /** 执行摘要 */
  summary: string
}

/**
 * Workflow 接口（抽象，适配 DSH workflow）
 */
export interface Workflow {
  agent(prompt: string, options?: { schema?: any }): Promise<any>
}

/**
 * 使用 Schema 执行 workflow
 * 
 * @param workflow Workflow 实例
 * @param prompt 提示词
 * @param schema 输出 schema
 * @returns 结构化输出
 */
export async function executeWithSchema<T = SubtaskOutputSchema>(
  workflow: Workflow,
  prompt: string,
  schema: any
): Promise<T> {
  try {
    // 调用引擎，传递 schema
    const result = await workflow.agent(prompt, { schema })
    
    // 检查返回值是否有效
    if (!result || typeof result !== 'object') {
      console.warn('[workflow-schema] Engine returned invalid result, falling back to empty structure')
      return {
        filesChanged: [],
        summary: 'schema validation failed'
      } as T
    }
    
    // 引擎应该返回符合 schema 的结构化对象
    return result as T
  } catch (error) {
    // 引擎拒绝或校验失败时，降级为结构化空值
    console.warn('[workflow-schema] Engine rejected or validation failed, falling back to empty structure:', error)
    
    // 返回符合 schema 的空值
    return {
      filesChanged: [],
      summary: 'schema validation failed'
    } as T
  }
}

/**
 * 验证输出是否符合 SubtaskOutputSchema
 */
export function isValidSubtaskOutput(output: unknown): output is SubtaskOutputSchema {
  if (typeof output !== 'object' || output === null) {
    return false
  }
  
  const obj = output as Record<string, unknown>
  
  // filesChanged 必须是字符串数组
  if (!Array.isArray(obj.filesChanged)) {
    return false
  }
  
  if (!obj.filesChanged.every(item => typeof item === 'string')) {
    return false
  }
  
  // summary 必须是字符串
  if (typeof obj.summary !== 'string') {
    return false
  }
  
  return true
}

/**
 * 创建默认的子卡输出
 */
export function createEmptySubtaskOutput(reason = 'no output'): SubtaskOutputSchema {
  return {
    filesChanged: [],
    summary: reason
  }
}
