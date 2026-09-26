/**
 * RTM 健康检查功能测试
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdirSync, rmSync, existsSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { 
  recordRTMFailure, 
  clearRTMFailure, 
  checkRTMHealth, 
  expectedRTMFiles 
} from '../../src/application/internal/rtm-health.js'
import type { RequirementRecord } from '../../src/shared/protocol.js'

describe('RTM 健康检查', () => {
  const testDir = join(process.cwd(), '.test-rtm-health')
  const stateDir = join(testDir, '.dsh-data', 'state')
  const reqDir = join(testDir, 'docs', 'requirements', 'REQ-test-001')

  beforeEach(() => {
    // 创建测试目录
    mkdirSync(stateDir, { recursive: true })
    mkdirSync(reqDir, { recursive: true })
  })

  afterEach(() => {
    // 清理测试目录
    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true })
    }
  })

  it('应该根据需求状态返回期望的 RTM 文件列表', () => {
    expect(expectedRTMFiles('draft')).toEqual([])
    expect(expectedRTMFiles('brainstorming')).toContain('rtm-lifecycle.yml')
    expect(expectedRTMFiles('brainstorming')).toContain('rtm-brainstorming.yml')
    expect(expectedRTMFiles('design')).toContain('rtm-design.yml')
    expect(expectedRTMFiles('implementing')).toContain('rtm-implementing.yml')
  })

  it('应该记录 RTM 生成失败', () => {
    recordRTMFailure(stateDir, 'REQ-test-001', 'create', '测试错误')
    
    const failuresFile = join(stateDir, 'rtm-failures.json')
    expect(existsSync(failuresFile)).toBe(true)
    
    const failures = JSON.parse(require('fs').readFileSync(failuresFile, 'utf-8'))
    expect(failures).toHaveLength(1)
    expect(failures[0].requirement_id).toBe('REQ-test-001')
    expect(failures[0].trigger).toBe('create')
    expect(failures[0].error).toBe('测试错误')
    expect(failures[0].attempts).toBe(1)
  })

  it('应该累加连续失败次数', () => {
    recordRTMFailure(stateDir, 'REQ-test-001', 'create', '错误1')
    recordRTMFailure(stateDir, 'REQ-test-001', 'submit:requirement', '错误2')
    
    const failures = JSON.parse(
      require('fs').readFileSync(join(stateDir, 'rtm-failures.json'), 'utf-8')
    )
    expect(failures).toHaveLength(1)
    expect(failures[0].attempts).toBe(2)
    expect(failures[0].error).toBe('错误2')
  })

  it('应该在成功后清除失败记录', () => {
    recordRTMFailure(stateDir, 'REQ-test-001', 'create', '测试错误')
    clearRTMFailure(stateDir, 'REQ-test-001')
    
    const failures = JSON.parse(
      require('fs').readFileSync(join(stateDir, 'rtm-failures.json'), 'utf-8')
    )
    expect(failures).toHaveLength(0)
  })

  it('应该检测缺失的 RTM 文件', () => {
    const req: RequirementRecord = {
      id: 'REQ-test-001',
      title: '测试需求',
      status: 'brainstorming',
      category: 'feature',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      version: 1,
      comments: [],
      blocked: false,
      statusHistory: [],
    } as any

    const health = checkRTMHealth(testDir, stateDir, req)
    
    expect(health.healthy).toBe(false)
    expect(health.missing_files).toContain('rtm-lifecycle.yml')
    expect(health.missing_files).toContain('rtm-brainstorming.yml')
    expect(health.retry_available).toBe(true)
  })

  it('应该在所有文件存在时返回健康状态', () => {
    // 创建所需的 RTM 文件
    writeFileSync(join(reqDir, 'rtm-lifecycle.yml'), 'test')
    writeFileSync(join(reqDir, 'rtm-brainstorming.yml'), 'test')
    
    const req: RequirementRecord = {
      id: 'REQ-test-001',
      title: '测试需求',
      status: 'brainstorming',
      category: 'feature',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      version: 1,
      comments: [],
      blocked: false,
      statusHistory: [],
    } as any

    const health = checkRTMHealth(testDir, stateDir, req)
    
    expect(health.healthy).toBe(true)
    expect(health.missing_files).toHaveLength(0)
  })

  it('应该在失败次数超过3次后禁用重试', () => {
    recordRTMFailure(stateDir, 'REQ-test-001', 'create', '错误1')
    recordRTMFailure(stateDir, 'REQ-test-001', 'create', '错误2')
    recordRTMFailure(stateDir, 'REQ-test-001', 'create', '错误3')
    
    const req: RequirementRecord = {
      id: 'REQ-test-001',
      title: '测试需求',
      status: 'brainstorming',
      category: 'feature',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      version: 1,
      comments: [],
      blocked: false,
      statusHistory: [],
    } as any

    const health = checkRTMHealth(testDir, stateDir, req)
    
    expect(health.retry_available).toBe(false)
    expect(health.last_failure?.attempts).toBe(3)
  })
})
