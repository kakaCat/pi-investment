/**
 * t2 · RTM 文件读写与版本控制测试（FR-1 / FR-6 / FR-9）。
 */
import { existsSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  clearReadErrors,
  currentVersion,
  ensureRTMDir,
  getRTMPath,
  lastReadError,
  readRTM,
  readRTMStrict,
  readRTMWithFallback,
  requirementsDir,
  RTMError,
  writeRTM,
} from '../../src/rtm/file-io.js'
import type { RTMLifecycle } from '../../src/rtm/types.js'

function tmpFile(name = 'rtm-lifecycle.yml'): string {
  const dir = mkdtempSync(join(tmpdir(), 'rtm-io-'))
  ensureRTMDir(dir)
  return join(dir, name)
}

function sample(version = 1): { metadata: { version: number }; lifecycle: { current_stage: string } } {
  return { metadata: { version }, lifecycle: { current_stage: 'draft' } }
}

describe('file-io', () => {
  it('写入后读取内容一致，且版本从 1 起', () => {
    const p = tmpFile()
    writeRTM(p, sample())
    const back = readRTM<{ lifecycle: { current_stage: string }; metadata: { version: number } }>(p)
    expect(back).not.toBeNull()
    expect(back?.lifecycle.current_stage).toBe('draft')
    expect(back?.metadata.version).toBe(1)
  })

  it('连续写入两次，版本 1 → 2', () => {
    const p = tmpFile()
    writeRTM(p, sample())
    writeRTM(p, sample())
    expect(currentVersion(p)).toBe(2)
  })

  it('读取不存在的文件返回 null 且不抛异常', () => {
    const p = join(tmpdir(), 'rtm-not-exists-' + Date.now() + '.yml')
    expect(readRTM(p)).toBeNull()
    expect(lastReadError(p)).toBeUndefined()
  })

  it('YAML 格式错误：宽读返回 null 并留因，严格读抛 RTM_FILE_PARSE_ERROR', () => {
    clearReadErrors()
    const p = tmpFile('broken.yml')
    writeFileSync(p, 'a: [1, 2\nb: 3\n', 'utf-8')
    expect(readRTM(p)).toBeNull()
    expect(lastReadError(p)).toBeTruthy()
    expect(() => readRTMStrict(p)).toThrowError(RTMError)
    try {
      readRTMStrict(p)
    } catch (err) {
      expect((err as RTMError).code).toBe('RTM_FILE_PARSE_ERROR')
    }
  })

  it('缺失时降级重建（readRTMWithFallback）', () => {
    const p = tmpFile('rtm-design.yml')
    const regenerated = readRTMWithFallback<{ metadata: { version: number } }>(p, () => ({ metadata: { version: 0 } }))
    expect(regenerated?.metadata.version).toBe(1)
    expect(existsSync(p)).toBe(true)
  })

  it('路径工具：requirementsDir / getRTMPath / ensureRTMDir', () => {
    expect(requirementsDir('/ws', 'REQ-1')).toBe(join('/ws', 'docs', 'requirements', 'REQ-1'))
    expect(getRTMPath('/r', 'rtm-implementing/t-1.yml')).toBe(join('/r', 'rtm-implementing', 't-1.yml'))
  })

  it('原子写入：不留 .tmp 临时文件', () => {
    const p = tmpFile()
    writeRTM(p, sample())
    expect(existsSync(p + '.tmp')).toBe(false)
  })

  it('写入 lifecyle 类型可正常序列化（回归：泛型不受类型形状限制）', () => {
    const p = tmpFile()
    const data: RTMLifecycle = {
      requirement: { id: 'REQ-1', title: 't', category: 'feature', created_at: '2026-01-01T00:00:00Z' },
      lifecycle: { current_stage: 'draft', stages: [{ stage: 'draft', status: 'in_progress' }] },
      metadata: { version: 0 },
    }
    writeRTM(p, data)
    expect(readRTM<RTMLifecycle>(p)?.lifecycle.stages).toHaveLength(1)
  })
})
