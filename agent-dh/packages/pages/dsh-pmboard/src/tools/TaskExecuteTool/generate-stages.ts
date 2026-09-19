import type { TaskInfo, StageDefinition } from './types.js'
import { getStageTemplate } from './stage-templates.js'

function fillTemplate(template: string, vars: Record<string, any>): string {
  let result = template
  for (const [key, value] of Object.entries(vars)) {
    const placeholder = `{{${key}}}`
    const replacement = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
    result = result.replace(new RegExp(placeholder, 'g'), replacement)
  }
  return result
}

export function generateStages(task: TaskInfo, resumeFrom?: number): StageDefinition[] {
  const template = getStageTemplate(task.side)
  const stages = resumeFrom ? template.filter(s => s.stage >= resumeFrom) : template
  const taskVars = {
    title: task.title,
    description: task.description,
    acceptance: task.acceptance,
    implementation: task.implementation,
    context: task.context
  }
  return stages.map(stage => ({
    ...stage,
    promptTemplate: fillTemplate(stage.promptTemplate, taskVars)
  }))
}
