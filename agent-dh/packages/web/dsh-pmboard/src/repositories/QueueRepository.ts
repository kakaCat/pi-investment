/**
 * 队列文件仓储（REQ-260927202051-f6df · S-4 / I-2 / FR-1, FR-4）。
 *
 * 队列文件 = 某需求的**任务唯一存储**：`<workspaceRoot>/docs/requirements/<REQ>/queue.json`。
 * 本文件是队列文件 I/O 的**唯一入口**（读/写/路径），实现三件事：
 *
 * 1. **原子写**：复用 `adapters/JsonLedgerRepository.ts` 导出的 `persistAtomic`
 *    （临时文件 → fsync → rename）。**不另造第二套原子写**——两套实现必然在
 *    "谁先 fsync、谁负责 mkdir、失败时 temp 残留" 上漂移，而原子性是**断电才暴露**的性质，
 *    漂移不会在测试里露头。
 * 2. **写前校验**：`validateQueueFile` 不通过 → 抛 `QUEUE_VALIDATION_FAILED` 且**一个字节都不落盘**
 *    （校验必须先于任何 mkdir/临时文件创建，否则"校验失败但目录已被创建"会让调用方误判状态）。
 * 3. **坏文件隔离**：JSON 解析失败 → 改名 `<file>.corrupt-<ts>` + 告警 + 返回 `undefined`（降级，
 *    不拖垮宿主）。**只有解析失败才隔离**：校验失败不隔离——那是"内容不合规"而不是"文件损坏"，
 *    改名会毁掉用户还能手工修的数据。
 *
 * 与 `TaskStore`（端口，t5）的分工：本文件只认"需求 → 一个 QueueFile"，不做缓存、不做任务级 CRUD、
 * 不推导派生视图。缓存与任务语义在 `QueueTaskStore`。这样迁移脚本（t13）可以只依赖本文件写队列，
 * 不被迫拉起带缓存的 TaskStore。
 *
 * @module dsh-pmboard/repositories/QueueRepository
 */
import { readFile, readdir, rename } from 'node:fs/promises'
import { isAbsolute, join } from 'node:path'
import { persistAtomic } from '../adapters/JsonLedgerRepository.js'
import { REQUIREMENTS_DIR, QUEUE_FILENAME, queueRelativePath } from '../domain/queue/queuePath.js'
import type { QueueFile } from '../domain/queue/QueueTypes.js'
import { validateQueueFile } from '../domain/queue/validateQueue.js'

/**
 * 路径与文件名常量的**单一事实源在 domain**（`src/domain/queue/queuePath.ts`）。
 *
 * 这里只做**再导出**：既有调用方（`tests/queue/*`、迁移脚本等从本模块 import 的历史写法）
 * 继续可用，但**实现只有一份**——application 层（`Decompose` 返回体的 `queue_file`）直接
 * import domain 那份，不再就地拼字符串。
 * （REQ-260927202051-f6df · Lead 裁决「单一事实源，不留两份路径拼法」）
 */
export { REQUIREMENTS_DIR, QUEUE_FILENAME, queueRelativePath }

/** 队列相关错误码（design/interfaces.md「错误码」）。 */
export const QUEUE_ERROR = {
  /** 对无队列的需求执行写操作（写不隐式建档）——由 TaskStore.mutate 抛。 */
  NOT_FOUND: 'QUEUE_NOT_FOUND',
  /** 队列 JSON 解析失败（已隔离改名）。 */
  CORRUPTED: 'QUEUE_CORRUPTED',
  /** V-1~V-6 未通过。 */
  VALIDATION_FAILED: 'QUEUE_VALIDATION_FAILED',
  /** 读文件失败（非"不存在"，如权限/IO 错误）。 */
  READ_FAILED: 'QUEUE_READ_FAILED',
  /** 写入失败（权限/磁盘满）。 */
  WRITE_FAILED: 'WRITE_FAILED',
} as const

/** 构造带 `code` 的错误（本仓约定：`Object.assign(new Error(msg), { code })`）。 */
function codedError(code: string, message: string, extra: Record<string, unknown> = {}): Error {
  return Object.assign(new Error(message), { code, ...extra })
}

export interface QueueRepositoryOptions {
  /** 工作区根（默认 `process.cwd()`，与 FileDocRepository 同口径）。 */
  workspaceRoot?: string
  /**
   * 需求目录解析器（注入点）：默认 `<root>/docs/requirements/<REQ>`。
   * 迁移脚本与测试用它把队列写到别处（如临时副本目录），不必伪造工作区结构。
   */
  requirementDirOf?: (requirementId: string) => string
  /** 告警通道（默认 `console.warn`；测试可注入收集器断言"确实告警了"）。 */
  onWarn?: (message: string) => void
}

/** 队列文件 I/O 端口（I-2）。 */
export interface QueueRepository {
  /** 读取并解析（+ V-1~V-6 校验）；不存在 / 损坏 / 校验失败 → `undefined`（不抛错）。 */
  load(requirementId: string): Promise<QueueFile | undefined>
  /** 校验后原子写；校验失败抛 `QUEUE_VALIDATION_FAILED` 且不落盘。 */
  save(requirementId: string, file: QueueFile): Promise<void>
  /** 队列文件**绝对路径**（I/O 与错误信息用）。 */
  pathOf(requirementId: string): string
  /**
   * 枚举工作区内**存在需求目录**的需求 id（`docs/requirements/REQ-*` 的目录名）。
   *
   * 存在的理由：TaskStore 的 `listAll()`（看板首屏跨需求任务集合）与 `get(taskId)`
   * 的兜底索引都需要"有哪些需求"，这是文件系统层的事实，不该让上层 `readdir` 各写一遍。
   * **只返回目录**（忽略文件与测试残留）；目录不存在 → 空数组（不抛错）。
   * 返回**已排序**（字典序），因此调用方拼接结果天然稳定。
   */
  listRequirementIds(): Promise<readonly string[]>
  /**
   * 队列文件**工作区相对路径**（返回体 `queue_file` / 日志用）。
   *
   * 注意：这是**规范路径**（`docs/requirements/<REQ>/queue.json`），与 `requirementDirOf`
   * 注入无关。测试/迁移把队列写到临时目录时，`pathOf` 才是实际落点——别用本方法的返回值
   * 去反推 `pathOf`。
   */
  relativePathOf(requirementId: string): string
  /** 工作区根。 */
  workspaceRoot(): string
}

export class JsonQueueRepository implements QueueRepository {
  private readonly root: string
  private readonly requirementDirOf: (requirementId: string) => string
  private readonly onWarn: (message: string) => void

  constructor(options: QueueRepositoryOptions = {}) {
    this.root = options.workspaceRoot ?? process.cwd()
    this.requirementDirOf = options.requirementDirOf ?? ((requirementId) => join(this.root, REQUIREMENTS_DIR, requirementId))
    this.onWarn = options.onWarn ?? ((message) => console.warn(message))
  }

  workspaceRoot(): string {
    return this.root
  }

  relativePathOf(requirementId: string): string {
    return queueRelativePath(requirementId)
  }

  pathOf(requirementId: string): string {
    const dir = this.requirementDirOf(requirementId)
    const abs = isAbsolute(dir) ? dir : join(this.root, dir)
    return join(abs, QUEUE_FILENAME)
  }

  /**
   * 枚举 `docs/requirements/` 下的需求目录（只认 `REQ-` 前缀的**目录**）。
   *
   * 说明：枚举**始终扫描规范目录** `<workspaceRoot>/docs/requirements`，
   * 与 `requirementDirOf` 注入无关（注入只影响单个需求的读写落点）。
   * 结果排序后返回——上层（`listAll`）直接拼接即可得到稳定顺序。
   */
  async listRequirementIds(): Promise<readonly string[]> {
    const dir = join(this.root, REQUIREMENTS_DIR)
    let entries
    try {
      entries = await readdir(dir, { withFileTypes: true })
    } catch {
      return [] // 目录不存在/不可读：视为"没有需求"，不是错误
    }
    return entries
      .filter((e) => e.isDirectory() && /^REQ-/.test(e.name))
      .map((e) => e.name)
      .sort()
  }

  async load(requirementId: string): Promise<QueueFile | undefined> {
    const file = this.pathOf(requirementId)
    let raw: string
    try {
      raw = await readFile(file, 'utf8')
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code
      if (code === 'ENOENT') return undefined // 未拆分的需求：不是错误
      throw codedError(QUEUE_ERROR.READ_FAILED, `读取队列失败 ${file}：${(error as Error).message}`, { cause: error })
    }

    let parsed: unknown
    try {
      parsed = JSON.parse(raw)
    } catch (error) {
      // 损坏隔离：改名挪走（best effort），告警，降级返回 undefined。
      const quarantined = `${file}.corrupt-${Date.now()}`
      try {
        await rename(file, quarantined)
        this.onWarn(`[queue] 队列 JSON 解析失败，已隔离：${file} → ${quarantined}（${(error as Error).message}）`)
      } catch (renameError) {
        this.onWarn(`[queue] 队列 JSON 解析失败且隔离失败：${file}（解析：${(error as Error).message}；隔离：${(renameError as Error).message}）`)
      }
      return undefined
    }

    const result = validateQueueFile(parsed as QueueFile)
    if (!result.passed) {
      this.onWarn(
        `[queue] 队列未通过校验（${result.issues.length} 条），按不可用处理：${file} —— ${result.issues
          .slice(0, 5)
          .map((i) => `${i.rule}@${i.path ?? '-'} ${i.message}`)
          .join(' | ')}`,
      )
      return undefined
    }
    return parsed as QueueFile
  }

  async save(requirementId: string, file: QueueFile): Promise<void> {
    // ① 路径与文件自述的需求必须一致——否则"写进 A 需求目录、内容声称是 B"会造出串档文件，
    //    而 V-1~V-6 只校验文件内部自洽（task.requirementId == file.requirement_id），检不出这个。
    if (file?.requirement_id !== requirementId) {
      throw codedError(
        QUEUE_ERROR.VALIDATION_FAILED,
        `队列文件 requirement_id(${String(file?.requirement_id)}) 与写入目标需求(${requirementId}) 不一致，拒绝落盘`,
        { issues: [{ rule: 'V-3', message: 'requirement_id 与写入路径不一致', path: 'requirement_id' }] },
      )
    }

    // ② 校验**先于**任何文件系统动作（连 mkdir 都不能先做）：否则校验失败会留下一个空目录，
    //    调用方"断言文件不存在"的检查会连带看到目录，状态判断跟着变复杂。
    const result = validateQueueFile(file)
    if (!result.passed) {
      throw codedError(
        QUEUE_ERROR.VALIDATION_FAILED,
        `队列校验未通过（${result.issues.length} 条）：${result.issues
          .slice(0, 5)
          .map((i) => `${i.rule}@${i.path ?? '-'} ${i.message}`)
          .join(' | ')}`,
        { issues: result.issues },
      )
    }

    // ③ 原子写：temp(同目录) → fsync → rename。失败时目标文件保持旧内容。
    const target = this.pathOf(requirementId)
    try {
      await persistAtomic(target, JSON.stringify(file, null, 2))
    } catch (error) {
      throw codedError(QUEUE_ERROR.WRITE_FAILED, `写入队列失败 ${target}：${(error as Error).message}`, { cause: error })
    }
  }
}
