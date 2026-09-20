/**
 * 更新任务卡 Markdown（添加 Workflow 执行记录）
 */

import type { WorkflowResult } from './types.js'
import * as fs from 'node:fs/promises'

/**
 * 格式化时间戳
 */
function formatTimestamp(date: Date = new Date()): string {
  return date.toISOString().replace('T', ' ').substring(0, 19)
}

/**
 * 生成执行记录 Markdown
 */
function generateExecutionRecord(result: WorkflowResult): string {
  const status = result.success ? '✅ 已完成' : '❌ 失败'
  const timestamp = formatTimestamp()
  
  let md = `
## Workflow 执行记录

**Workflow Run ID**: \`${result.workflowRunId}\`  
**状态**: ${status}  
**执行时间**: ${timestamp}  
**Sub-agents**: ${result.agentsStarted} 个

### 阶段执行详情

`

  // 添加每个阶段的详情
  for (const stage of result.stages) {
    const stageStatus = stage.status === 'completed' ? '✅' : '❌'
    md += `
#### ${stageStatus} 阶段 ${stage.stage}：${stage.name}

`
    
    if (stage.error) {
      md += `**错误**: ${stage.error}\n\n`
    } else if (stage.output) {
      const outputStr = typeof stage.output === 'string' 
        ? stage.output 
        : JSON.stringify(stage.output, null, 2)
      
      // 限制输出长度
      const preview = outputStr.length > 500 
        ? outputStr.substring(0, 500) + '...（已截断）'
        : outputStr
      
      md += `<details>
<summary>查看输出</summary>

\`\`\`json
${preview}
\`\`\`

</details>

`
    }
  }
  
  if (result.error) {
    md += `
### 错误信息

\`\`\`
${result.error}
\`\`\`
`
  }
  
  return md
}

/**
 * 更新任务卡文件
 */
export async function updateTaskCard(
  taskId: string, 
  result: WorkflowResult
): Promise<void> {
  try {
    // 1. 构建任务卡路径（需要从 repo 获取 requirementId）
    // 简化版：假设任务卡路径可以推断
    const taskCardPath = `docs/requirements/${taskId.split('-')[0]}/tasks/${taskId}.md`
    
    // 2. 读取现有内容
    let content: string
    try {
      content = await fs.readFile(taskCardPath, 'utf-8')
    } catch (err: any) {
      if (err.code === 'ENOENT') {
        console.warn(`任务卡文件不存在: ${taskCardPath}`)
        return
      }
      throw err
    }
    
    // 3. 生成执行记录
    const executionRecord = generateExecutionRecord(result)
    
    // 4. 检查是否已有执行记录节
    if (content.includes('## Workflow 执行记录')) {
      // 替换现有记录
      content = content.replace(
        /## Workflow 执行记录[\s\S]*?(?=\n## |$)/,
        executionRecord
      )
    } else {
      // 追加到文件末尾
      content = content.trimEnd() + '\n\n' + executionRecord + '\n'
    }
    
    // 5. 写回文件
    await fs.writeFile(taskCardPath, content, 'utf-8')
    
    console.log(`✅ 任务卡已更新: ${taskCardPath}`)
    
  } catch (error: any) {
    console.error(`更新任务卡失败: ${error.message}`)
    // 不抛出错误，避免影响主流程
  }
}

