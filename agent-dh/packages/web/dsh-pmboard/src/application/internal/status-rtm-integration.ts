/**
 * Status RTM 集成辅助函数（REQ-260925172227-2d61）
 * 为 QueryState 用例提供 FR 覆盖度和验收进度统计
 */
import { CoverageChecker } from '../../../../../tools/reqboard/src/rtm/coverage-checker.js'
import { AcceptanceGate } from '../../../../../tools/reqboard/src/rtm/acceptance-gate.js'
import { scanFRDirectory } from '../../../../../tools/reqboard/src/rtm/fr-parser.js'
import type { TaskRecord, VerificationSheet } from '../../shared/protocol.js'

export interface StatusRTMResult {
  fr_coverage: {
    total_frs: number
    covered_frs: number
    unreceived_clauses: string[]
    coverage_rate: number
  }
  fr_acceptance_progress?: {
    total: number
    passed: number
    failed: number
    pending: number
    pass_rate: number
    gate_status: 'passed' | 'blocked' | 'pending'
  }
}

/**
 * 生成 FR 覆盖度和验收进度统计
 * @param reqDir 需求目录（如 docs/requirements/REQ-xxx）
 * @param tasks 任务列表
 * @param verificationSheet 验收单（可选，仅在验收阶段有）
 * @returns FR 覆盖度和验收进度
 */
export function generateStatusRTM(
  reqDir: string,
  tasks: TaskRecord[],
  verificationSheet?: VerificationSheet
): StatusRTMResult {
  // 1. 扫描 FR 文件
  const frMetadata = scanFRDirectory(reqDir)
  
  // 2. 生成 task_coverage（简化版，只需要 covers_frs）
  const tasksWithRefs = tasks.map(t => ({
    key: t.id,
    title: t.title,
    requirement_refs: t.requirementRefs ?? []
  }))
  
  // 创建简化的 task_coverage（只包含 covers_frs）
  const taskCoverage = tasksWithRefs.map(task => ({
    task_key: task.key,
    task_title: task.title,
    covers_frs: task.requirement_refs.filter(ref => 
      frMetadata.some(fr => fr.id === ref)
    ),
    covers_acceptance: [] // 不需要详细验收项
  }))
  
  // 3. 检查覆盖度
  const coverageCheck = CoverageChecker.checkCoverage(frMetadata, taskCoverage)
  
  const result: StatusRTMResult = {
    fr_coverage: {
      total_frs: coverageCheck.total_frs,
      covered_frs: coverageCheck.covered_frs,
      unreceived_clauses: coverageCheck.unreceived_clauses,
      coverage_rate: coverageCheck.coverage_rate
    }
  }
  
  // 4. 如果有验收单，添加验收进度
  if (verificationSheet && verificationSheet.items.length > 0) {
    const acceptanceTracking = verificationSheet.items.map(item => ({
      acceptance_id: item.id,
      fr_id: item.source.kind === 'requirement' ? 'REQ-LEVEL' : (item.source.taskId ?? 'UNKNOWN'),
      description: item.criterion,
      verification: item.howToVerify ?? item.criterion,
      status: item.status,
      evidence: item.evidence ?? null,
      judged_at: item.decidedAt ?? null,
      judged_by: item.decidedBy?.sessionId ?? null,
      user_feedback: item.opinion ?? null
    }))
    
    const gateResult = AcceptanceGate.checkGate(acceptanceTracking)
    
    result.fr_acceptance_progress = {
      total: gateResult.total,
      passed: gateResult.passed,
      failed: gateResult.failed,
      pending: gateResult.pending,
      pass_rate: gateResult.pass_rate,
      gate_status: gateResult.gate_status
    }
  }
  
  return result
}
