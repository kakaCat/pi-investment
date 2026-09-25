/**
 * 拆分门禁（REQ-260925212722-96e7 FR-5）
 *
 * 检查所有功能需求（FR）是否都有对应的任务引用（task_refs）。
 * 阻止在任务覆盖不完整的情况下推进到实施阶段。
 *
 * @module dsh-pmboard/application/gate/task-coverage-gate
 */

import type { RequirementRecord } from '../../shared/protocol.js'
import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import * as yaml from 'yaml'

/** 门禁检查结果 */
export interface GateResult {
  /** 是否通过 */
  passed: boolean
  /** 错误代码（未通过时） */
  code?: string
  /** 缺失的条款列表（orphan_clauses：孤儿条款，未被任何任务覆盖） */
  gaps?: string[]
  /** 人类可读的消息 */
  message: string
}

/** RTM 文件中的功能需求条目 */
interface FunctionalRequirement {
  id: string
  title: string
  design_refs?: string[]
  task_refs?: string[]
  acceptance_status?: 'pending' | 'passed' | 'failed'
}

/** RTM 文件结构 */
interface RTMData {
  functional_requirements: FunctionalRequirement[]
}

/**
 * 拆分门禁检查：所有 FR 必须有任务引用
 *
 * @param req 需求记录
 * @param workspaceRoot 工作区根路径（用于读取 RTM 文件）
 * @returns 门禁检查结果
 */
export async function taskCoverageGateCheck(
  req: RequirementRecord,
  workspaceRoot: string
): Promise<GateResult> {
  try {
    // 1. 读取 RTM 文件
    const rtmPath = path.join(workspaceRoot, `docs/requirements/${req.id}/rtm.yaml`)
    const rtmContent = await fs.readFile(rtmPath, 'utf-8')
    const rtm: RTMData = yaml.parse(rtmContent)

    // 2. 检查所有 FR 的 task_refs
    const orphanClauses: string[] = []
    
    for (const fr of rtm.functional_requirements) {
      if (!fr.task_refs || fr.task_refs.length === 0) {
        orphanClauses.push(fr.id)
      }
    }

    // 3. 返回结果
    if (orphanClauses.length === 0) {
      return {
        passed: true,
        message: '拆分门禁通过：所有功能需求都有任务引用'
      }
    } else {
      return {
        passed: false,
        code: 'task_coverage_incomplete',
        gaps: orphanClauses,
        message: `拆分门禁未通过：${orphanClauses.length} 个功能需求未被任务覆盖（孤儿条款：${orphanClauses.join(', ')}）`
      }
    }
  } catch (error) {
    // RTM 文件不存在或解析失败
    return {
      passed: false,
      code: 'rtm_not_found',
      message: `拆分门禁未通过：无法读取 RTM 文件（${error instanceof Error ? error.message : String(error)}）`
    }
  }
}
