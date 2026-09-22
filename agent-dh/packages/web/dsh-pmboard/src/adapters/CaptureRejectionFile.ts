// serves: FR-5
/**
 * 立项拒绝留痕文件适配器（REQ-260922012924-2e29 FR-5）—— <dshHome>/state/capture-rejections.json（ring buffer）。
 *
 * 与 IsolationTraceFile 同款纪律：原子写沿用 JsonLedgerRepository 的 persistAtomic
 * （temp + fsync + rename）；写入串行队列避免并发覆盖；缺文件视为空；文件损坏/写入失败
 * 走 onError——**只告警，绝不冒泡到立项路径**（留痕是旁路，不是流水线的一部分）。
 *
 * @module dsh-pmboard/adapters/CaptureRejectionFile
 */
import { readFile } from 'node:fs/promises'
import { persistAtomic } from './JsonLedgerRepository.js'
import { fmt } from '../domain/text/fmt.js'
import { appendCaptureRejection, isCaptureRejection } from '../application/internal/capture-rejections.js'
import type { CaptureRejection, CaptureRejectionPort } from '../application/ports.js'

export class CaptureRejectionFile implements CaptureRejectionPort {
  private readonly file: string
  private readonly onError: (error: unknown) => void
  private queue: Promise<void> = Promise.resolve()
  private cache: CaptureRejection[] | undefined

  constructor(file: string, onError: (error: unknown) => void = () => {}) {
    this.file = file
    this.onError = onError
  }

  /** 记录一次立项拒绝（同步返回；落盘进入串行队列，失败走 onError，不静默）。 */
  record(entry: CaptureRejection): void {
    this.enqueue(entry)
  }

  /** 等待队列清空（测试/对账用）。 */
  async flush(): Promise<void> {
    await this.queue
  }

  /** 只读全量（缺文件 → []；损坏 → 抛错，由调用方决定是否降级）。 */
  async readAll(): Promise<readonly CaptureRejection[]> {
    return await this.load()
  }

  private enqueue(entry: CaptureRejection): void {
    const run = async (): Promise<void> => {
      const existing = this.cache ?? await this.load()
      const next = appendCaptureRejection(existing, entry)
      await persistAtomic(this.file, JSON.stringify(next, null, 2))
      this.cache = next
    }
    this.queue = this.queue.then(run, run).catch((error: unknown) => {
      this.onError(error)
    })
  }

  private async load(): Promise<CaptureRejection[]> {
    try {
      const raw = await readFile(this.file, 'utf8')
      const parsed = JSON.parse(raw) as unknown
      if (!Array.isArray(parsed)) {
        throw new Error(fmt('capture-rejections 顶层不是数组：{file}', { file: this.file }))
      }
      return parsed.map((item, i) => {
        if (!isCaptureRejection(item)) {
          throw new Error(fmt('capture-rejections 第 {i} 条记录残缺：{file}', { i, file: this.file }))
        }
        return item
      })
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw error
    }
  }
}
