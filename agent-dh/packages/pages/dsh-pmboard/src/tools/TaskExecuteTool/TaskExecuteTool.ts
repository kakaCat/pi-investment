/**
 * TaskExecuteTool - 使用 DSH Workflow 执行任务
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { UseCaseDeps } from '../../application/ports.js'
import type { ExecuteTaskParams, ExecuteTaskResult, TaskInfo } from './types.js'
import { generateWorkflowScript } from './generate-workflow-script.js'
import { updateTaskCard } from './update-task-card.js'

const TOOL_DESCRIPTION = `执行任务（使用 DSH Workflow 自动拆解为6阶段）

适用于：开工后执行任务，Agent 自动拆解为多个阶段并逐个执行

参数：
- task_id: 任务 ID（必填）
- resume_from: 从第几阶段恢复（可选，失败重试用）

工作流程：
1. 读取任务卡
2. 生成 Workflow 脚本（6阶段）
3. 调用 DSH workflow 工具
4. 更新任务卡进度
5. 返回执行结果
`

export function defineTaskExecuteTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_execute',
    description: TOOL_DESCRIPTION,
    parameters: {
      task_id: { 
        type: 'string', 
        description: '任务 id（t-xxxxxx）', 
        required: true 
      },
      resume_from: { 
        type: 'number', 
        description: '从第几阶段恢复（1-6）' 
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          workflow_run_id: { type: 'string' },
          status: { type: 'string' },
        },
      },
      render: (_args: any, value: any) => [
        { type: 'text', text: JSON.stringify(value, null, 2) }
      ],
    },
    timeoutMs: 600000, // 10分钟（workflow 可能很长）
    async execute(args: ExecuteTaskParams, ctx: any): Promise<ExecuteTaskResult> {
      try {
        // 1. 读取任务信息
        const snapshot = deps.repo.snapshot()
        const task = snapshot.tasks.find(t => t.id === args.task_id)
        
        if (!task) {
          return {
            success: false,
            task_id: args.task_id,
            status: 'failed',
            error: `任务不存在: ${args.task_id}`
          }
        }
        
        // 2. 构建 TaskInfo
        const taskInfo: TaskInfo = {
          id: task.id,
          title: task.title,
          description: task.description || '',
          acceptance: task.acceptance || '',
          implementation: task.implementation || '',
          context: task.context || '',
          side: (task.side || 'backend') as any,
          requirementId: task.requirementId
        }
        
        // 3. 生成 Workflow 脚本
        const script = generateWorkflowScript(taskInfo, args.resume_from)
        
        // 4. 调用 DSH workflow 工具
        const workflowResult = await ctx.tools.workflow({
          meta: {
            name: `执行任务 ${task.id}`,
            description: task.title,
            phases: ['分析', '设计', '实现', '测试', '文档', '汇报']
          },
          script,
          args: { task: taskInfo }
        })
        
        // 5. 更新任务卡
        await updateTaskCard(task.id, {
          success: true,
          workflowRunId: workflowResult.runId,
          agentsStarted: workflowResult.agentsStarted,
          stages: workflowResult.result?.stages || []
        })
        
        // 6. 返回结果
        return {
          success: true,
          task_id: task.id,
          workflow_run_id: workflowResult.runId,
          status: 'completed',
          stages: workflowResult.result?.stages
        }
        
      } catch (error: any) {
        return {
          success: false,
          task_id: args.task_id,
          status: 'failed',
          error: error.message,
          next_step: args.resume_from 
            ? '检查错误后重试' 
            : `可以用 resume_from 参数从失败阶段恢复`
        }
      }
    },
  } as any)
}
