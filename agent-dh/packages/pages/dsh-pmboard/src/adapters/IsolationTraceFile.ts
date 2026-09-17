/**
 * 隔离留痕文件适配器（REQ-422af1 t10）—— <dshHome>/state/node-isolation-log.json（ring buffer）。
 *
 * I/O 只在本文件（application 层保持纯逻辑）：原子写沿用 JsonLedgerRepository 的
 * persistAtomic（temp + fsync + rename，断电不留半截 JSON）；写入串行队列避免并发覆盖；
 * 缺文件视为空（删除该文件不影响功能）；文件损坏/写入失败走 onError——
 * **只告警，绝不冒泡到节点结算点**（留痕是旁路，不是流水线的一部分）。
 *
 * @module dsh-pmboard/adapters/IsolationTraceFile
 */
import { readFile } from 'node:fs/promises'
import { persistAtomic } from './JsonLedgerRepository.js'
import { fmt } from '../domain/text/fmt.js'
import { appendToIsolationTrace, isIsolationTraceEntry } from '../application/internal/isolation-trace.js'
import type {
  IsolationTraceEntry,
  IsolationTracePort,
} from '../application/use-cases/IsolateNodeContext.js'

export class IsolationTraceFile implements IsolationTracePort {
  private readonly file: string
  private readonly onError: (error: unknown) => void
  private queue: Promise<void> = Promise.resolve()
  private cache: IsolationTraceEntry[] | undefined

  constructor(file: string, onError: (error: unknown) => void = () => {}) {
    this.file = file
    this.onError = onError
  }

  /** 记录一次隔离尝试（同步返回；落盘进入串行队列，失败走 onError，不静默）。 */
  record(entry: IsolationTraceEntry): void {
    this.enqueue(entry)
  }

  /** 等待队列清空（测试/对账用）。 */
  async flush(): Promise<void> {
    await this.queue
  }

  /** 只读全量（缺文件 → []；损坏 → 抛错，由调用方决定是否降级）。 */
  async readAll(): Promise<IsolationTraceEntry[]> {
    return await this.load()
  }

  private enqueue(entry: IsolationTraceEntry): void {
    const run = async (): Promise<void> => {
      const existing = this.cache ?? await this.load()
      const next = appendToIsolationTrace(existing, entry)
      await persistAtomic(this.file, JSON.stringify(next, null, 2))
      this.cache = next
    }
    this.queue = this.queue.then(run, run).catch((error: unknown) => {
      this.onError(error)
    })
  }

  private async load(): Promise<IsolationTraceEntry[]> {
    try {
      const raw = await readFile(this.file, 'utf8')
      const parsed = JSON.parse(raw) as unknown
      if (!Array.isArray(parsed)) {
        throw new Error(fmt('node-isolation-log 顶层不是数组：{file}', { file: this.file }))
      }
      return parsed.map((item, i) => {
        if (!isIsolationTraceEntry(item)) {
          throw new Error(fmt('node-isolation-log 第 {i} 条记录残缺：{file}', { i, file: this.file }))
        }
        return item
      })
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw error
    }
  }
}
