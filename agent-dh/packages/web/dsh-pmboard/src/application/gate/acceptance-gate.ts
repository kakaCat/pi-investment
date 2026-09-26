/**
 * 验收门禁（REQ-260925212722-96e7 FR-6）
 *
 * 检查所有功能需求（FR）是否都已通过验收（acceptance_status === 'passed'）。
 * 阻止在验收未通过的情况下归档需求。
 *
 * @module dsh-pmboard/application/gate/acceptance-gate
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
  /** 失败的条款列表 */
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
 * 验收门禁检查：所有 FR 必须通过验收
 *
 * @param req 需求记录
 * @param workspaceRoot 工作区根路径（用于读取 RTM 文件）
 * @returns 门禁检查结果
 */
export async function acceptanceGateCheck(
  req: RequirementRecord,
  workspaceRoot: string
): Promise<GateResult> {
  try {
    // 1. 读取 RTM 文件
    const rtmPath = path.join(workspaceRoot, `docs/requirements/${req.id}/rtm.yaml`)
    const rtmContent = await fs.readFile(rtmPath, 'utf-8')
    const rtm: RTMData = yaml.parse(rtmContent)

    // 2. 检查所有 FR 的 acceptance_status
    const failedClauses: string[] = []
    
    for (const fr of rtm.functional_requirements) {
      // 未通过验收：pending（待验收）或 failed（验收失败）
      if (fr.acceptance_status !== 'passed') {
        failedClauses.push(fr.id)
      }
    }

    // 3. 返回结果
    if (failedClauses.length === 0) {
      return {
        passed: true,
        message: '验收门禁通过：所有功能需求都已通过验收'
      }
    } else {
      return {
        passed: false,
        code: 'acceptance_incomplete',
        gaps: failedClauses,
        message: `验收门禁未通过：${failedClauses.length} 个功能需求未通过验收（${failedClauses.join(', ')}）`
      }
    }
  } catch (error) {
    // RTM 文件不存在或解析失败
    return {
      passed: false,
      code: 'rtm_not_found',
      message: `验收门禁未通过：无法读取 RTM 文件（${error instanceof Error ? error.message : String(error)}）`
    }
  }
}
