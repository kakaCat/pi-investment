/**
 * 零参绑定守护测试：@deepseek-ai/dsh-ptc-runtime-node 的零参绑定补丁。
 *
 * 【为什么要有这道门】
 * PTC 运行时把宿主声明的绑定暴露成程序里的全局函数（如 'tools.foo()'）。
 * Node 版实现在 'lib/process.js' 的 makeNamespaces 里把每个绑定写成：
 *     value: (args) => { ... snapshotPtcJsonValue(args) ... }
 * 程序**零参调用**（'tools.foo()'，DSH 里绝大多数工具调用都走零参/全默认）时
 * 'args === undefined'，快照判非法 JSON → 在发出控制帧之前就 reject，宿主根本
 * 收不到这一帧：工具调用表现为"什么都没发生"的静默失败。
 *
 * 【修复】
 * 'patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch' 只改一行：
 *     value: (args) => {   →   value: (args = {}) => {
 * 让零参等同于空对象。根 package.json 的 'pnpm.patchedDependencies' 负责登记该补丁。
 *
 * 【四层守护（任一层被回退即红）】
 *   1. 根 package.json 仍登记该 patch（登记被摘 = pnpm install 后补丁静默失效）；
 *   2. patch 文件本身仍把绑定工厂改成 '(args = {})'；
 *   3. **已安装产物** 'lib/process.js' 真的带上了默认参数（patch 没生效即红）；
 *   4. 跨进程行为：零参调用的 call 帧 args 编码为 '{}'，且能拿到宿主回包。
 * 常见回退场景：pnpm install 重置 node_modules、上游发版后忘记重打补丁，
 * 都会在这里显形。
 */
import { describe, it, expect } from 'vitest'
import { spawn, type StdioOptions } from 'node:child_process'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import type { Duplex } from 'node:stream'
import { fileURLToPath } from 'node:url'

const PACKAGE_NAME = '@deepseek-ai/dsh-ptc-runtime-node'
const SOURCE_RELATIVE_PATH = join('lib', 'process.js')
const PATCHED_BINDING = 'value: (args = {}) => {'
const ORIGINAL_BINDING = 'value: (args) => {'

interface RootManifest {
  pnpm?: { patchedDependencies?: Record<string, string> }
}

interface PatchEnvironment {
  root: string
  patchKey: string
  patchPath: string
  patchText: string
  installedDir: string
  installedSource: string
  installedProcessEntry: string
}

/** 从本测试文件向上找到仓库根（以 package.json 的 pnpm.patchedDependencies 为锚）。 */
function findRepoRoot(start: string): string {
  let dir = resolve(start)
  for (;;) {
    const manifestPath = join(dir, 'package.json')
    if (existsSync(manifestPath)) {
      try {
        const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as RootManifest
        if (manifest.pnpm?.patchedDependencies !== undefined) return dir
      } catch {
        // 不是我们要找的清单，继续向上
      }
    }
    const parent = dirname(dir)
    if (parent === dir) throw new Error('向上未找到含 pnpm.patchedDependencies 的仓库根 package.json')
    dir = parent
  }
}

/** 找到 pnpm 实际安装的该包目录（先看 .pnpm 提升层，再回退虚拟店扫描）。 */
function findInstalledPackageDir(root: string): string {
  const candidates: string[] = [
    join(root, 'node_modules', '.pnpm', 'node_modules', '@deepseek-ai', 'dsh-ptc-runtime-node'),
  ]
  const pnpmStore = join(root, 'node_modules', '.pnpm')
  if (existsSync(pnpmStore)) {
    for (const entry of readdirSync(pnpmStore)) {
      if (!entry.startsWith('@deepseek-ai+dsh-ptc-runtime-node@')) continue
      candidates.push(join(pnpmStore, entry, 'node_modules', '@deepseek-ai', 'dsh-ptc-runtime-node'))
    }
  }
  const found = candidates.find((dir) => existsSync(join(dir, SOURCE_RELATIVE_PATH)))
  if (found === undefined) {
    throw new Error('未找到已安装的 ' + PACKAGE_NAME + '（先执行 pnpm install）；候选路径：' + candidates.join(' | '))
  }
  return found
}

let cachedEnvironment: PatchEnvironment | null = null

function environment(): PatchEnvironment {
  if (cachedEnvironment !== null) return cachedEnvironment
  const root = findRepoRoot(dirname(fileURLToPath(import.meta.url)))
  const manifest = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')) as RootManifest
  const patched = manifest.pnpm?.patchedDependencies ?? {}
  const patchKey = Object.keys(patched).find((key) => key.startsWith(PACKAGE_NAME + '@'))
  if (patchKey === undefined) throw new Error('根 package.json 未登记 ' + PACKAGE_NAME + ' 的 patchedDependencies')
  const patchPath = join(root, patched[patchKey])
  const installedDir = findInstalledPackageDir(root)
  const installedProcessEntry = join(installedDir, SOURCE_RELATIVE_PATH)
  cachedEnvironment = {
    root,
    patchKey,
    patchPath,
    patchText: readFileSync(patchPath, 'utf8'),
    installedDir,
    installedSource: readFileSync(installedProcessEntry, 'utf8'),
    installedProcessEntry,
  }
  return cachedEnvironment
}

interface WireMessage {
  type?: string
  id?: number
  ok?: boolean
  global?: string
  name?: string
  args?: unknown
  data?: unknown
  value?: unknown
  error?: unknown
}

/** 控制通道帧：uint32BE 长度前缀 + UTF-8 JSON 体（与进程内 JsonChannel 同协议）。 */
class FrameChannel {
  private buffer: Buffer = Buffer.alloc(0)
  private readonly queue: WireMessage[] = []
  private readonly waiters: Array<(message: WireMessage) => void> = []

  constructor(private readonly stream: Duplex) {
    stream.on('data', (chunk: Buffer) => {
      this.push(chunk)
    })
  }

  private push(chunk: Buffer): void {
    this.buffer = Buffer.concat([this.buffer, chunk])
    while (this.buffer.length >= 4) {
      const length = this.buffer.readUInt32BE(0)
      if (this.buffer.length < 4 + length) return
      const body = this.buffer.subarray(4, 4 + length).toString('utf8')
      this.buffer = this.buffer.subarray(4 + length)
      const message = JSON.parse(body) as WireMessage
      const waiter = this.waiters.shift()
      if (waiter === undefined) this.queue.push(message)
      else waiter(message)
    }
  }

  next(timeoutMs = 10_000): Promise<WireMessage> {
    const queued = this.queue.shift()
    if (queued !== undefined) return Promise.resolve(queued)
    return new Promise<WireMessage>((resolvePromise, rejectPromise) => {
      let timer: ReturnType<typeof setTimeout>
      const waiter = (message: WireMessage): void => {
        clearTimeout(timer)
        resolvePromise(message)
      }
      timer = setTimeout(() => {
        const index = this.waiters.indexOf(waiter)
        if (index >= 0) this.waiters.splice(index, 1)
        rejectPromise(new Error('等待子进程控制帧超时（' + String(timeoutMs) + 'ms）'))
      }, timeoutMs)
      this.waiters.push(waiter)
    })
  }

  send(message: WireMessage): void {
    const body = Buffer.from(JSON.stringify(message), 'utf8')
    const header = Buffer.alloc(4)
    header.writeUInt32BE(body.length, 0)
    this.stream.write(Buffer.concat([header, body]))
  }

  close(): void {
    this.stream.end()
  }
}

describe('零参绑定守护：dsh-ptc-runtime-node 补丁', () => {
  it('根 package.json 仍登记该包的 patchedDependencies', () => {
    const env = environment()
    expect(env.patchKey).toBe(PACKAGE_NAME + '@0.1.6-alpha.2')
    expect(existsSync(env.patchPath)).toBe(true)
  })

  it('patch 文件仍把绑定工厂改成 (args = {})', () => {
    const env = environment()
    expect(env.patchText).toContain(ORIGINAL_BINDING)
    expect(env.patchText).toContain(PATCHED_BINDING)
  })

  it('已安装产物 lib/process.js 带上了默认参数（patch 未生效即红）', () => {
    const env = environment()
    expect(env.installedSource).toContain(PATCHED_BINDING)
  })

  it('零参调用跨进程生效：call 帧 args 编码为 {} 且能拿到回包', async () => {
    const env = environment()
    // 额外管道挂在 fd 7：与 @deepseek-ai/dsh-ptc-runtime-node 的 openInheritedControlChannel 约定一致。
    const stdio: StdioOptions = ['ignore', 'pipe', 'pipe', 'ignore', 'ignore', 'ignore', 'ignore', 'pipe']
    const child = spawn(process.execPath, [env.installedProcessEntry, String(1024 * 1024)], {
      env: { PATH: process.env.PATH ?? '', DSH_SUBPROCESS_CONTROL: 'pipe' },
      stdio,
    })
    let channel: FrameChannel | null = null
    let stderr = ''
    child.stderr?.on('data', (chunk: Buffer) => {
      stderr += chunk.toString('utf8')
    })
    try {
      const controlStream = (child.stdio as unknown as ReadonlyArray<Duplex | null | undefined>)[7]
      expect(controlStream, 'fd 7 控制管道未建立').toBeDefined()
      channel = new FrameChannel(controlStream as Duplex)

      const ready = await channel.next()
      expect(ready.type).toBe('ready')

      channel.send({
        type: 'boot',
        data: {
          namespaces: [{ global: 'tools', names: ['ping'] }],
          code: 'const value = await tools.ping(); return { got: value };',
          maxOutputBytes: 1024 * 1024,
        },
      })

      // 未打补丁时程序会在发出 call 帧之前 reject，这里先收到 done(exception) → 直接红。
      const call = await channel.next()
      expect(call.type, '期望先收到 call 帧，实际收到：' + JSON.stringify(call) + ' stderr=' + stderr).toBe('call')
      expect(call.global).toBe('tools')
      expect(call.name).toBe('ping')
      // 零参 = 空对象快照 → wire 预序编码恰为 [{kind:'object',keys:[]}]
      expect(call.args).toEqual([{ kind: 'object', keys: [] }])

      channel.send({ id: call.id, ok: true, value: ['pong'] })

      const done = await channel.next()
      expect(done.type, '期望 done 帧，实际：' + JSON.stringify(done) + ' stderr=' + stderr).toBe('done')
      expect(done.error).toBeUndefined()
      expect(done.value).toEqual([{ kind: 'object', keys: ['got'] }, 'pong'])
    } finally {
      channel?.close()
      child.kill()
    }
  }, 30_000)
})
