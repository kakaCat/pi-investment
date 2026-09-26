/**
 * RTM 文件读写与版本控制（REQ-260926140539-457b FR-1 / FR-6 / FR-9）。
 *
 * 契约：
 *  - 原子写入：先写同目录临时文件，再 rename 覆盖（避免半截 YAML）。
 *  - 版本递增：每次写入 metadata.version = 旧版本 + 1（FR-6 版本追踪）。
 *  - 失败响亮：解析错误记入 lastReadError 并返回 null（FR-9 不崩溃，但可查因）。
 *
 * @module @pi-investment/reqboard/rtm/file-io
 */
import { existsSync, mkdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { parse, stringify } from 'yaml'
import type { RTMMetadata, RTMWriteOptions } from './types.js'

/** 结构化 RTM 错误（FR-9：错误码 + 上下文）。 */
export class RTMError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message)
    this.name = 'RTMError'
  }
}

/** 最近一次读取失败原因（按绝对路径）。解析失败不抛异常，但必须留下证据。 */
const lastErrors = new Map<string, string>()

/** 取出某个文件最近一次读取/解析失败原因。 */
export function lastReadError(filePath: string): string | undefined {
  return lastErrors.get(filePath)
}

/** 清空错误记录（测试隔离用）。 */
export function clearReadErrors(): void {
  lastErrors.clear()
}

/** 需求目录：<workspaceRoot>/docs/requirements/<reqId>。 */
export function requirementsDir(workspaceRoot: string, reqId: string): string {
  return join(workspaceRoot, 'docs', 'requirements', reqId)
}

/** RTM 文件绝对路径（reqDir + 文件名；name 可含子目录，如 rtm-implementing/t-xxx.yml）。 */
export function getRTMPath(reqDir: string, name: string): string {
  return join(reqDir, name)
}

/** 确保目录存在（递归）。 */
export function ensureRTMDir(dir: string): void {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
}

/**
 * 读取 RTM YAML。文件不存在或解析失败返回 null（并记录错误），**不抛异常**。
 * 需要严格语义（解析失败必须炸）时用 readRTMStrict。
 */
export function readRTM<T = unknown>(filePath: string): T | null {
  if (!existsSync(filePath)) return null
  let text: string
  try {
    text = readFileSync(filePath, 'utf-8')
  } catch (err) {
    lastErrors.set(filePath, err instanceof Error ? err.message : String(err))
    return null
  }
  try {
    const parsed = parse(text)
    if (parsed === null || parsed === undefined || typeof parsed !== 'object') {
      lastErrors.set(filePath, 'YAML 内容不是对象')
      return null
    }
    lastErrors.delete(filePath)
    return parsed as T
  } catch (err) {
    lastErrors.set(filePath, err instanceof Error ? err.message : String(err))
    return null
  }
}

/** 严格读取：不存在或解析失败抛 RTMError。 */
export function readRTMStrict<T = unknown>(filePath: string): T {
  if (!existsSync(filePath)) {
    throw new RTMError('RTM_FILE_NOT_FOUND', `RTM 文件不存在：${filePath}`)
  }
  const text = readFileSync(filePath, 'utf-8')
  try {
    const parsed = parse(text)
    if (parsed === null || typeof parsed !== 'object') {
      throw new Error('YAML 内容不是对象')
    }
    return parsed as T
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    lastErrors.set(filePath, message)
    throw new RTMError('RTM_FILE_PARSE_ERROR', `RTM 文件解析失败：${filePath}（${message}）`, { filePath })
  }
}

/** 当前版本号（文件不存在或字段缺失 → 0）。 */
export function currentVersion(filePath: string): number {
  const existing = readRTM<{ metadata?: { version?: unknown } }>(filePath)
  const v = existing?.metadata?.version
  return typeof v === 'number' && Number.isFinite(v) ? v : 0
}

/**
 * 原子写入 RTM YAML，并按 opts 递增 metadata.version。
 * 返回**实际落盘**的对象（含最终 version），调用方可直接继续用。
 */
export function writeRTM<T>(filePath: string, data: T, opts: RTMWriteOptions = {}): T {
  ensureRTMDir(dirname(filePath))
  const rec = data as unknown as { metadata?: Partial<RTMMetadata> }
  const prev = currentVersion(filePath)
  const bump = opts.bumpVersion !== false
  const declared = typeof rec.metadata?.version === 'number' ? (rec.metadata.version as number) : undefined
  const version = opts.version ?? (bump ? prev + 1 : declared ?? (prev > 0 ? prev : 1))

  const meta: Partial<RTMMetadata> = { ...(rec.metadata ?? {}) }
  meta.version = version
  meta.last_updated = opts.now ?? new Date().toISOString()
  if (opts.generatedBy !== undefined) meta.generated_by = opts.generatedBy
  rec.metadata = meta as RTMMetadata

  const tmp = `${filePath}.tmp-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  try {
    writeFileSync(tmp, stringify(data, { lineWidth: 0 }), 'utf-8')
    renameSync(tmp, filePath)
  } catch (err) {
    if (existsSync(tmp)) {
      try {
        unlinkSync(tmp)
      } catch {
        /* 清理失败不影响主错误 */
      }
    }
    throw new RTMError('RTM_FILE_WRITE_ERROR', `RTM 文件写入失败：${filePath}`, {
      cause: err instanceof Error ? err.message : String(err),
    })
  }
  return data
}

/**
 * 读取 RTM；文件缺失/损坏时调用 regenerate 重建后再读（FR-9 降级模式）。
 */
export function readRTMWithFallback<T>(
  filePath: string,
  regenerate: () => T,
): T | null {
  const hit = readRTM<T>(filePath)
  if (hit !== null) return hit
  try {
    const fresh = regenerate()
    writeRTM(filePath, fresh)
    return readRTM<T>(filePath)
  } catch (err) {
    lastErrors.set(filePath, err instanceof Error ? err.message : String(err))
    return null
  }
}
