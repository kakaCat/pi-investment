/**
 * 注入留痕文件适配器（REQ-422af1 t6）—— state 目录下的 ring buffer JSON。
 *
 * I/O 只在本文件（application 层保持纯逻辑）：原子写沿用 JsonLedgerRepository 的
 * persistAtomic（temp + fsync + rename，断电不留半截 JSON）；写入串行队列避免并发覆盖；
 * 缺文件视为空（删除该文件不影响功能）；文件损坏则**响亮抛错**（不静默降级成空）。
 *
 * @module dsh-pmboard/adapters/InjectionLogFile
 */
import { readFile } from 'node:fs/promises'
import { persistAtomic } from './JsonLedgerRepository.js'
import { fmt } from '../domain/text/fmt.js'
import {
  appendToInjectionLog,
  isInjectionLogEntry,
  queryInjectionLog,
  type InjectionLogEntry,
  type InjectionLogInput,
  type InjectionLogPort,
} from '../application/internal/injection-log.js'

export class InjectionLogFile implements InjectionLogPort {
  private readonly file: string
  private readonly now: () => number
  private readonly onError: (error: unknown) => void
  private queue: Promise<void> = Promise.resolve()
  private cache: InjectionLogEntry[] | undefined

  constructor(file: string, now: () => number, onError: (error: unknown) => void = () => {}) {
    this.file = file
    this.now = now
    this.onError = onError
  }

  /** 记录一次注入（同步返回；落盘进入串行队列，失败走 onError，不静默）。 */
  record(entry: InjectionLogInput): void {
    this.enqueue(entry)
  }

  /** 等待队列清空（测试/对账用）。 */
  async flush(): Promise<void> {
    await this.queue
  }

  /** 只读全量（缺文件 → []；损坏 → 抛错）。 */
  async readAll(): Promise<InjectionLogEntry[]> {
    try {
      const raw = await readFile(this.file, 'utf8')
      const parsed = JSON.parse(raw) as unknown
      if (!Array.isArray(parsed)) {
        throw new Error(fmt('prompt-injection-log 顶层不是数组：{file}', { file: this.file }))
      }
      return parsed.map((item, i) => {
        if (!isInjectionLogEntry(item)) {
          throw new Error(fmt('prompt-injection-log 第 {i} 条记录残缺（缺字段）：{file}', { i, file: this.file }))
        }
        return item
      })
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw error
    }
  }

  /** 只读查询：最近 k 条。 */
  async queryLatest(k: number): Promise<InjectionLogEntry[]> {
    return queryInjectionLog(await this.readAll(), k)
  }

  private enqueue(entry: InjectionLogInput): void {
    const run = async (): Promise<void> => {
      const existing = this.cache ?? await this.readAll()
      const next = appendToInjectionLog(existing, { ...entry, at: this.now() })
      await persistAtomic(this.file, JSON.stringify(next, null, 2))
      this.cache = next
    }
    this.queue = this.queue.then(run, run).catch((error: unknown) => {
      this.onError(error)
    })
  }
}
