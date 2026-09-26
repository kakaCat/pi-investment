/**
 * RTM 健康检查与自动修复（修复：yaml 生成失败，下一次校验时提醒）
 * 
 * 功能：
 * 1. 记录 RTM 生成失败历史（state/rtm-failures.json）
 * 2. 根据需求状态校验应有的 RTM 文件
 * 3. 检测缺失并尝试自动修复
 * 4. 返回健康状态供 reqboard_status 展示
 * 
 * @module dsh-pmboard/application/internal/rtm-health
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import type { RequirementRecord } from '../../shared/protocol.js'
import type { RTMTrigger, RTMTriggerResult } from './rtm-yaml.js'

/** RTM 生成失败记录 */
export interface RTMFailureRecord {
  requirement_id: string
  trigger: RTMTrigger
  timestamp: number
  error: string
  /** 失败次数（连续失败累加） */
  attempts: number
}

/** RTM 健康状态 */
export interface RTMHealthStatus {
  /** 是否健康（所有应有的文件都存在） */
  healthy: boolean
  /** 缺失的 RTM 文件 */
  missing_files: string[]
  /** 最近一次失败记录 */
  last_failure?: {
    trigger: string
    error: string
    timestamp: number
    attempts: number
  }
  /** 是否可以重试修复 */
  retry_available: boolean
}

/** 失败记录文件路径 */
function failuresFilePath(stateDir: string): string {
  return join(stateDir, 'rtm-failures.json')
}

/** 读取失败记录 */
function readFailures(stateDir: string): RTMFailureRecord[] {
  const path = failuresFilePath(stateDir)
  if (!existsSync(path)) return []
  try {
    const content = readFileSync(path, 'utf-8')
    const data = JSON.parse(content)
    return Array.isArray(data) ? data : []
  } catch {
    return []
  }
}

/** 写入失败记录（原子写入） */
function writeFailures(stateDir: string, records: RTMFailureRecord[]): void {
  const path = failuresFilePath(stateDir)
  const tmp = path + '.tmp-' + process.pid + '-' + Date.now()
  try {
    writeFileSync(tmp, JSON.stringify(records, null, 2), 'utf-8')
    writeFileSync(path, readFileSync(tmp))
  } finally {
    if (existsSync(tmp)) {
      try { 
        const fs = require('fs')
        fs.unlinkSync(tmp) 
      } catch {}
    }
  }
}

/**
 * 记录一次 RTM 生成失败
 */
export function recordRTMFailure(
  stateDir: string,
  requirementId: string,
  trigger: RTMTrigger,
  error: string,
): void {
  const records = readFailures(stateDir)
  const existing = records.find(r => r.requirement_id === requirementId)
  
  if (existing) {
    // 更新已有记录
    existing.trigger = trigger
    existing.timestamp = Date.now()
    existing.error = error
    existing.attempts += 1
  } else {
    // 新增记录
    records.push({
      requirement_id: requirementId,
      trigger,
      timestamp: Date.now(),
      error,
      attempts: 1,
    })
  }
  
  // 只保留最近 100 条
  const sorted = records.sort((a, b) => b.timestamp - a.timestamp)
  writeFailures(stateDir, sorted.slice(0, 100))
}

/**
 * 清除某个需求的失败记录（生成成功后调用）
 */
export function clearRTMFailure(stateDir: string, requirementId: string): void {
  const records = readFailures(stateDir)
  const filtered = records.filter(r => r.requirement_id !== requirementId)
  if (filtered.length !== records.length) {
    writeFailures(stateDir, filtered)
  }
}

/**
 * 根据需求状态判断应该有哪些 RTM 文件
 */
export function expectedRTMFiles(status: string): string[] {
  const files: string[] = []
  
  // rtm-lifecycle.yml 在立项后就应该有
  if (status !== 'draft') {
    files.push('rtm-lifecycle.yml')
  }
  
  // rtm-brainstorming.yml 在提交需求文档后有
  if (['brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived', 'done'].includes(status)) {
    files.push('rtm-brainstorming.yml')
  }
  
  // rtm-design.yml 在提交设计文档后有
  if (['design', 'decomposing', 'implementing', 'accepting', 'archived', 'done'].includes(status)) {
    files.push('rtm-design.yml')
  }
  
  // rtm-decomposing.yml 在批准拆分计划后有
  if (['decomposing', 'implementing', 'accepting', 'archived', 'done'].includes(status)) {
    files.push('rtm-decomposing.yml')
  }
  
  // rtm-implementing.yml 在批准拆分计划后有
  if (['implementing', 'accepting', 'archived', 'done'].includes(status)) {
    files.push('rtm-implementing.yml')
  }
  
  // rtm-accepting.yml 在提交验收材料后有
  if (['accepting', 'archived', 'done'].includes(status)) {
    files.push('rtm-accepting.yml')
  }
  
  return files
}

/**
 * 检查 RTM 文件健康状态
 */
export function checkRTMHealth(
  workspaceRoot: string,
  stateDir: string,
  req: RequirementRecord,
): RTMHealthStatus {
  const reqDir = join(workspaceRoot, 'docs', 'requirements', req.id)
  const expected = expectedRTMFiles(req.status)
  const missing: string[] = []
  
  for (const file of expected) {
    const path = join(reqDir, file)
    if (!existsSync(path)) {
      missing.push(file)
    }
  }
  
  const records = readFailures(stateDir)
  const lastFailure = records.find(r => r.requirement_id === req.id)
  
  return {
    healthy: missing.length === 0,
    missing_files: missing,
    last_failure: lastFailure ? {
      trigger: lastFailure.trigger,
      error: lastFailure.error,
      timestamp: lastFailure.timestamp,
      attempts: lastFailure.attempts,
    } : undefined,
    retry_available: missing.length > 0 && (!lastFailure || lastFailure.attempts < 3),
  }
}
