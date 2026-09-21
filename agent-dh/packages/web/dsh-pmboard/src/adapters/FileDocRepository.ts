/**
 * 文档仓储适配器（REQ-47939a t5 / ports.ts DocRepository）——产物落盘/读取/存在性校验的唯一入口。
 *
 * 收敛此前散在 host/agent-tools.ts（内嵌 writeFileSync/mkdirSync/existsSync）与
 * host/sync-artifacts.ts（readdirSync/statSync 扫描）的文件 I/O。工作区根默认 process.cwd()，
 * 与迁移前各处的 join(process.cwd(), relPath) 口径一致。
 *
 * read/write 用 node:fs/promises（异步）；exists/list 用同步 API——它们服务于渲染前的
 * 元数据探测，且既有调用点（以及 discoverArtifacts 的同步签名）依赖同步语义。
 *
 * @module dsh-pmboard/adapters/FileDocRepository
 */
import { existsSync, readdirSync, statSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, isAbsolute, join } from 'node:path'
import type { DocEntry, DocRepository } from '../application/ports.js'

export interface FileDocRepositoryOptions {
  /** 工作区根（默认 process.cwd()）。 */
  workspaceRoot?: string
}

export class FileDocRepository implements DocRepository {
  private readonly root: string

  constructor(options: FileDocRepositoryOptions = {}) {
    this.root = options.workspaceRoot ?? process.cwd()
  }

  workspaceRoot(): string {
    return this.root
  }

  /** 相对路径 → 绝对路径（已是绝对路径则原样返回）。 */
  resolve(relPath: string): string {
    return isAbsolute(relPath) ? relPath : join(this.root, relPath)
  }

  exists(relPath: string): boolean {
    return existsSync(this.resolve(relPath))
  }

  async read(relPath: string): Promise<string> {
    return readFile(this.resolve(relPath), 'utf8')
  }

  /** 写入（自动创建父目录）——产物落盘走这里，不再在工具壳里裸写 fs。 */
  async write(relPath: string, content: string): Promise<void> {
    const abs = this.resolve(relPath)
    await mkdir(dirname(abs), { recursive: true })
    await writeFile(abs, content, 'utf8')
  }

  /** 单文件元数据（不存在/不可读 → undefined）——done 凭证门的文件 mtime 证据。 */
  stat(relPath: string): { mtimeMs: number; size: number } | undefined {
    try {
      const st = statSync(this.resolve(relPath))
      return { mtimeMs: st.mtimeMs, size: st.size }
    } catch { return undefined }
  }

  /** 列出目录（不存在/不可读 → 空数组，不抛）。 */
  list(relDir: string): readonly DocEntry[] {
    const abs = this.resolve(relDir)
    let names: string[]
    try { names = readdirSync(abs) } catch { return [] }
    const out: DocEntry[] = []
    for (const name of names) {
      try {
        const st = statSync(join(abs, name))
        out.push({ name, isFile: st.isFile(), mtimeMs: st.mtimeMs, size: st.size })
      } catch { /* 条目在扫描间隙消失 → 跳过 */ }
    }
    return out
  }
}
