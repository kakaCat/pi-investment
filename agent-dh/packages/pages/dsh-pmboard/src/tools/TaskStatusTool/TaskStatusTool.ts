/**
 * TaskStatusTool - 查询任务执行状态
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { UseCaseDeps } from '../../application/ports.js'
import { TASK_STATUS_PROGRESS, WORKFLOW_RUN_STATUS, isWorkflowRunCompleted } from '../../domain/task/TaskStatus.js'
import * as fs from 'node:fs/promises'
import { renderSmart } from '../shared.js'
import { taskStatusSummary } from '../render-summaries.js'

interface TaskStatusParams {
  task_id: string
}

interface TaskStatusResult {
  success: boolean
  task_id: string
  status: string
  progress: number
  workflow?: {
    run_id: string
    status: string
    started_at: string
    stages: {
      stage: number
      name: string
      status: string
    }[]
  }
  error?: string
}

async function parseWorkflowFromTaskCard(taskId: string, requirementId: string): Promise<any> {
  try {
    const taskCardPath = `docs/requirements/${requirementId}/tasks/${taskId}.md`
    const content = await fs.readFile(taskCardPath, 'utf-8')
    
    if (!content.includes('## Workflow')) {
      return null
    }
    
    const lines = content.split('\n')
    const workflowInfo: any = { stages: [] }
    let inSection = false
    
    for (const line of lines) {
      if (line.includes('## Workflow')) {
        inSection = true
        continue
      }
      
      if (inSection) {
        if (line.startsWith('## ') && !line.includes('Workflow')) break
        
        // 反引号写作 \x60：正则里出现裸 ` 会被 output-contract 静态扫描器误判为模板串起点
        const runIdMatch = line.match(/Run ID.*\x60([^\x60]+)\x60/)
        if (runIdMatch) workflowInfo.run_id = runIdMatch[1]
        
        if (line.includes('状态')) {
          workflowInfo.status = line.includes('✅') ? WORKFLOW_RUN_STATUS.Completed : WORKFLOW_RUN_STATUS.Failed
        }
        
        const stageMatch = line.match(/####\s+(✅|❌)\s+阶段\s+(\d+)/)
        if (stageMatch) {
          workflowInfo.stages.push({
            stage: parseInt(stageMatch[2]),
            status: stageMatch[1] === '✅' ? WORKFLOW_RUN_STATUS.Completed : WORKFLOW_RUN_STATUS.Failed
          })
        }
      }
    }
    
    return workflowInfo.run_id ? workflowInfo : null
  } catch {
    return null
  }
}

function calculateProgress(status: string, workflow?: any): number {
  // 状态 → 进度映射单点在 domain（TASK_STATUS_PROGRESS，REQ-f0579a t4：tools 不得写状态字面量）
  let progress = (TASK_STATUS_PROGRESS as Record<string, number>)[status] ?? 0
  
  if (workflow?.stages?.length > 0) {
    const completed = workflow.stages.filter((s: any) => isWorkflowRunCompleted(s.status)).length
    const total = workflow.stages.length
    progress = Math.round((completed / total) * 100)
  }
  
  return Math.min(100, Math.max(0, progress))
}

export function defineTaskStatusTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_status',
    description: '查询任务执行状态和进度',
    parameters: {
      task_id: {
        type: 'string',
        description: '任务 id（t-xxxxxx）',
        required: true
      }
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          status: { type: 'string' },
          progress: { type: 'number' },
          workflow: { type: 'object', additionalProperties: true },
          error: { type: 'string' },
        }
      },
      render: renderSmart(taskStatusSummary)
    },
    async execute(args: TaskStatusParams): Promise<TaskStatusResult> {
      try {
        const snapshot = deps.repo.snapshot()
        const task = snapshot.tasks.find(t => t.id === args.task_id)
        
        if (!task) {
          return {
            success: false,
            task_id: args.task_id,
            status: 'not_found',
            progress: 0,
            error: `任务不存在: ${args.task_id}`
          }
        }
        
        const workflow = await parseWorkflowFromTaskCard(task.id, task.requirementId)
        const progress = calculateProgress(task.status, workflow)
        
        return {
          success: true,
          task_id: task.id,
          status: task.status,
          progress,
          ...(workflow && { workflow })
        }
        
      } catch (error: any) {
        return {
          success: false,
          task_id: args.task_id,
          status: 'error',
          progress: 0,
          error: error.message
        }
      }
    }
  } as any)
}
