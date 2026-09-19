/**
 * TaskStatusTool - 查询任务执行状态
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { UseCaseDeps } from '../../application/ports.js'
import * as fs from 'node:fs/promises'

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
        
        const runIdMatch = line.match(/Run ID.*`([^`]+)`/)
        if (runIdMatch) workflowInfo.run_id = runIdMatch[1]
        
        if (line.includes('状态')) {
          workflowInfo.status = line.includes('✅') ? 'completed' : 'failed'
        }
        
        const stageMatch = line.match(/####\s+(✅|❌)\s+阶段\s+(\d+)/)
        if (stageMatch) {
          workflowInfo.stages.push({
            stage: parseInt(stageMatch[2]),
            status: stageMatch[1] === '✅' ? 'completed' : 'failed'
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
  const statusProgress: Record<string, number> = {
    'todo': 0,
    'in_progress': 20,
    'integrating': 50,
    'testing': 70,
    'in_review': 85,
    'done': 100
  }
  
  let progress = statusProgress[status] ?? 0
  
  if (workflow?.stages?.length > 0) {
    const completed = workflow.stages.filter((s: any) => s.status === 'completed').length
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
        }
      },
      render: (_args: any, value: any) => [
        { type: 'text', text: JSON.stringify(value, null, 2) }
      ]
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
