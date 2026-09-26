/**
 * 验收门禁单元测试（REQ-260925212722-96e7 FR-6）
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { acceptanceGateCheck } from '../../../src/application/gate/acceptance-gate.js'
import type { RequirementRecord } from '../../../src/shared/protocol.js'
import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import * as os from 'node:os'

describe('acceptanceGateCheck', () => {
  let tmpDir: string
  let reqId: string

  beforeEach(async () => {
    // 创建临时目录
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'acceptance-gate-test-'))
    reqId = 'REQ-test789'
    
    // 创建需求目录
    await fs.mkdir(path.join(tmpDir, 'docs', 'requirements', reqId), { recursive: true })
  })

  afterEach(async () => {
    // 清理临时目录
    await fs.rm(tmpDir, { recursive: true, force: true })
  })

  it('should pass when all FRs have acceptance_status passed', async () => {
    // 创建全部通过的 RTM 文件
    const rtmContent = `functional_requirements:
  - id: FR-1
    title: Test requirement 1
    acceptance_status: passed
  - id: FR-2
    title: Test requirement 2
    acceptance_status: passed
`
    await fs.writeFile(path.join(tmpDir, 'docs', 'requirements', reqId, 'rtm.yaml'), rtmContent)

    const req: RequirementRecord = {
      id: reqId,
      title: 'Test',
      description: '',
      status: 'accepting',
      blocked: false,
      createdAt: Date.now(),
      createdBy: { kind: 'human', sessionId: 'test' },
      comments: []
    }

    const result = await acceptanceGateCheck(req, tmpDir)

    expect(result.passed).toBe(true)
    expect(result.message).toContain('所有功能需求都已通过验收')
  })

  it('should fail when some FRs have pending or failed acceptance_status', async () => {
    // 创建部分未通过的 RTM 文件
    const rtmContent = `functional_requirements:
  - id: FR-1
    title: Test requirement 1
    acceptance_status: passed
  - id: FR-2
    title: Test requirement 2
    acceptance_status: pending
  - id: FR-3
    title: Test requirement 3
    acceptance_status: failed
`
    await fs.writeFile(path.join(tmpDir, 'docs', 'requirements', reqId, 'rtm.yaml'), rtmContent)

    const req: RequirementRecord = {
      id: reqId,
      title: 'Test',
      description: '',
      status: 'accepting',
      blocked: false,
      createdAt: Date.now(),
      createdBy: { kind: 'human', sessionId: 'test' },
      comments: []
    }

    const result = await acceptanceGateCheck(req, tmpDir)

    expect(result.passed).toBe(false)
    expect(result.code).toBe('acceptance_incomplete')
    expect(result.gaps).toEqual(['FR-2', 'FR-3'])
    expect(result.message).toContain('2 个功能需求未通过验收')
  })

  it('should fail when RTM file does not exist', async () => {
    const req: RequirementRecord = {
      id: reqId,
      title: 'Test',
      description: '',
      status: 'accepting',
      blocked: false,
      createdAt: Date.now(),
      createdBy: { kind: 'human', sessionId: 'test' },
      comments: []
    }

    const result = await acceptanceGateCheck(req, tmpDir)

    expect(result.passed).toBe(false)
    expect(result.code).toBe('rtm_not_found')
    expect(result.message).toContain('无法读取 RTM 文件')
  })
})
