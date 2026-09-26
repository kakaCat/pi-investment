/**
 * 设计门禁（REQ-260925212722-96e7 FR-4）
 *
 * 检查所有功能需求（FR）是否都有对应的设计文档引用（design_refs）。
 * 阻止在设计不完整的情况下推进到拆分阶段。
 *
 * @module dsh-pmboard/application/gate/design-gate
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
  /** 缺失的条款列表（设计门禁用） */
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
 * 设计门禁检查：所有 FR 必须有设计文档引用
 *
 * @param req 需求记录
 * @param workspaceRoot 工作区根路径（用于读取 RTM 文件）
 * @returns 门禁检查结果
 */
export async function designGateCheck(
  req: RequirementRecord,
  workspaceRoot: string
): Promise<GateResult> {
  try {
    // 1. 读取 RTM 文件
    const rtmPath = path.join(workspaceRoot, `docs/requirements/${req.id}/rtm.yaml`)
    const rtmContent = await fs.readFile(rtmPath, 'utf-8')
    const rtm: RTMData = yaml.parse(rtmContent)

    // 2. 检查所有 FR 的 design_refs
    const gaps: string[] = []
    
    for (const fr of rtm.functional_requirements) {
      if (!fr.design_refs || fr.design_refs.length === 0) {
        gaps.push(fr.id)
      }
    }

    // 3. 返回结果
    if (gaps.length === 0) {
      return {
        passed: true,
        message: '设计门禁通过：所有功能需求都有设计文档引用'
      }
    } else {
      return {
        passed: false,
        code: 'design_incomplete',
        gaps,
        message: `设计门禁未通过：${gaps.length} 个功能需求缺少设计文档引用（${gaps.join(', ')}）`
      }
    }
  } catch (error) {
    // RTM 文件不存在或解析失败
    return {
      passed: false,
      code: 'rtm_not_found',
      message: `设计门禁未通过：无法读取 RTM 文件（${error instanceof Error ? error.message : String(error)}）`
    }
  }
}
