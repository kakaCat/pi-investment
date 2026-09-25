/**
 * RTM 集成辅助函数（REQ-260925172227-2d61）
 * 为 Decompose 用例提供 RTM 数据生成和覆盖度检查
 */
import { RTMManager } from '../../../../../tools/reqboard/src/rtm/rtm-manager.js'
import { CoverageChecker } from '../../../../../tools/reqboard/src/rtm/coverage-checker.js'
import { scanFRDirectory } from '../../../../../tools/reqboard/src/rtm/fr-parser.js'
import type { TaskRecord } from '../../shared/protocol.js'

export interface RTMIntegrationResult {
  task_coverage: Array<{
    task_id: string
    task_key: string
    task_title: string
    covers_frs: string[]
    covers_acceptance: string[]
  }>
  coverage_check: {
    total_frs: number
    covered_frs: number
    unreceived_clauses: string[]
    coverage_rate: number
  }
}

/**
 * 生成 RTM 数据并检查覆盖度
 * @param reqDir 需求目录（如 docs/requirements/REQ-xxx）
 * @param tasks 已落库的任务列表
 * @returns RTM 数据和覆盖度统计
 */
export async function generateRTMData(
  reqDir: string,
  tasks: TaskRecord[]
): Promise<RTMIntegrationResult> {
  // 1. 扫描 FR 文件
  const frMetadata = scanFRDirectory(reqDir)
  
  // 2. 生成 task_coverage
  const tasksWithRefs = tasks.map(t => ({
    key: t.id,
    title: t.title,
    requirement_refs: t.requirementRefs ?? []
  }))
  
  const taskCoverage = RTMManager.fillTaskCoverage(reqDir, tasksWithRefs)
  
  // 3. 检查覆盖度
  const coverageCheck = CoverageChecker.checkCoverage(frMetadata, taskCoverage)
  
  // 4. 格式化返回
  return {
    task_coverage: taskCoverage.map(tc => ({
      task_id: tasks.find(t => t.id === tc.task_key)?.id ?? tc.task_key,
      task_key: tc.task_key,
      task_title: tc.task_title,
      covers_frs: tc.covers_frs,
      covers_acceptance: tc.covers_acceptance
    })),
    coverage_check: {
      total_frs: coverageCheck.total_frs,
      covered_frs: coverageCheck.covered_frs,
      unreceived_clauses: coverageCheck.unreceived_clauses,
      coverage_rate: coverageCheck.coverage_rate
    }
  }
}
