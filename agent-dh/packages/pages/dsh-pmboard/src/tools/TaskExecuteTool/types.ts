/**
 * TaskExecuteTool 类型定义
 */
import type { WorkflowRunStatus } from '../../domain/task/TaskStatus.js'

export interface TaskInfo {
  id: string
  title: string
  description: string
  acceptance: string
  implementation: string
  context: string
  side: 'backend' | 'frontend' | 'fullstack' | 'doc'
  requirementId: string
}

export interface StageDefinition {
  stage: number
  name: string
  description: string
  promptTemplate: string
}

export interface WorkflowResult {
  success: boolean
  workflowRunId: string
  agentsStarted: number
  stages: StageResult[]
  error?: string
}

export interface StageResult {
  stage: number
  name: string
  status: WorkflowRunStatus
  output?: any
  error?: string
}

export interface ExecuteTaskParams {
  task_id: string
  resume_from?: number
}

export interface ExecuteTaskResult {
  success: boolean
  task_id: string
  workflow_run_id?: string
  status: WorkflowRunStatus
  stages?: StageResult[]
  next_step?: string
  error?: string
}
