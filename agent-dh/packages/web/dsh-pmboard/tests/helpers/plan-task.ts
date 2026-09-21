/**
 * 计划任务工厂（测试辅助，REQ-4842fe t8）——避免各测试重复写全字段。
 */
import type { PlanTask } from '../../src/shared/protocol.js'

export function planTask(over: Partial<PlanTask> & { key: string; title: string }): PlanTask {
  return {
    phase: 'implement',
    side: 'backend',
    dependsOn: [],
    acceptance: '跑测试看到绿',
    implementation: '改 x.ts',
    ...over,
  }
}
