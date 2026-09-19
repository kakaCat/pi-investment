import type { TaskInfo } from './types.js'
import { generateStages } from './generate-stages.js'

export function generateWorkflowScript(task: TaskInfo, resumeFrom?: number): string {
  const stages = generateStages(task, resumeFrom)

  const stageCode = stages.map(stage => `
  const stage${stage.stage}_result = await ctx.subagent({
    description: '阶段${stage.stage}：${stage.name}',
    prompt: \`${stage.promptTemplate}\`,
    run_in_background: false
  });
  results.push({ stage: ${stage.stage}, name: '${stage.name}', output: stage${stage.stage}_result.output });
  `).join('\n')

  return `const results = [];
${stageCode}
return { success: true, stages: results };`
}
