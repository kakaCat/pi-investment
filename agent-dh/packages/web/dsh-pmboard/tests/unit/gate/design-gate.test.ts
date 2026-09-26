/**
 * 设计门禁单元测试（REQ-260925212722-96e7 FR-4）
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { designGateCheck } from '../../../src/application/gate/design-gate.js'
import type { RequirementRecord } from '../../../src/shared/protocol.js'
import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import * as os from 'node:os'

describe('designGateCheck', () => {
  let tmpDir: string
  let reqId: string

  beforeEach(async () => {
    // 创建临时目录
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'design-gate-test-'))
    reqId = 'REQ-test123'
    
    // 创建需求目录
    await fs.mkdir(path.join(tmpDir, 'docs', 'requirements', reqId), { recursive: true })
  })

  afterEach(async () => {
    // 清理临时目录
    await fs.rm(tmpDir, { recursive: true, force: true })
  })

  it('should pass when all FRs have design_refs', async () => {
    // 创建完整的 RTM 文件
    const rtmContent = `functional_requirements:
  - id: FR-1
    title: Test requirement 1
    design_refs:
      - design/architecture.md
  - id: FR-2
    title: Test requirement 2
    design_refs:
      - design/data-model.md
`
    await fs.writeFile(path.join(tmpDir, 'docs', 'requirements', reqId, 'rtm.yaml'), rtmContent)

    const req: RequirementRecord = {
      id: reqId,
      title: 'Test',
      description: '',
      status: 'design',
      blocked: false,
      createdAt: Date.now(),
      createdBy: { kind: 'human', sessionId: 'test' },
      comments: []
    }

    const result = await designGateCheck(req, tmpDir)

    expect(result.passed).toBe(true)
    expect(result.message).toContain('所有功能需求都有设计文档引用')
  })

  it('should fail when some FRs lack design_refs', async () => {
    // 创建部分缺失的 RTM 文件
    const rtmContent = `functional_requirements:
  - id: FR-1
    title: Test requirement 1
    design_refs:
      - design/architecture.md
  - id: FR-2
    title: Test requirement 2
    design_refs: []
  - id: FR-3
    title: Test requirement 3
`
    await fs.writeFile(path.join(tmpDir, 'docs', 'requirements', reqId, 'rtm.yaml'), rtmContent)

    const req: RequirementRecord = {
      id: reqId,
      title: 'Test',
      description: '',
      status: 'design',
      blocked: false,
      createdAt: Date.now(),
      createdBy: { kind: 'human', sessionId: 'test' },
      comments: []
    }

    const result = await designGateCheck(req, tmpDir)

    expect(result.passed).toBe(false)
    expect(result.code).toBe('design_incomplete')
    expect(result.gaps).toEqual(['FR-2', 'FR-3'])
    expect(result.message).toContain('2 个功能需求缺少设计文档引用')
  })

  it('should fail when RTM file does not exist', async () => {
    const req: RequirementRecord = {
      id: reqId,
      title: 'Test',
      description: '',
      status: 'design',
      blocked: false,
      createdAt: Date.now(),
      createdBy: { kind: 'human', sessionId: 'test' },
      comments: []
    }

    const result = await designGateCheck(req, tmpDir)

    expect(result.passed).toBe(false)
    expect(result.code).toBe('rtm_not_found')
    expect(result.message).toContain('无法读取 RTM 文件')
  })
})
