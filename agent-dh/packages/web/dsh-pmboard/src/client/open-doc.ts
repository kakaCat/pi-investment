/**
 * 文档打开统一入口（REQ-ff20ca t5）——走 DSH 官方右侧栏文档预览。
 *
 * 为什么：REQ-31e11f 设计的人机回路第一环是「人看文档 → 对话交流改进」，
 * 弹窗是模态遮挡、看文档时无法对话 → 回路断裂。官方 sidebarRight 支持并排常驻。
 *
 * 按 G2 **不保留弹窗降级**：sidebarRight 不可用时打印诊断，不做静默回退。
 *
 * @module dsh-pmboard/client/open-doc
 */
import { sessionFileAddress } from './file-address.ts'

/** 官方右侧栏导航面对（只用 openResource 这一项）。 */
interface SidebarRightLike {
  openResource?: (address: string, options?: unknown) => void
}

/** 取 ctx.sidebarRight —— 可选服务，缺失不影响插件加载（不得加入 inject）。 */
function sidebarRightOf(ctx: unknown): SidebarRightLike | undefined {
  const raw = (ctx as { sidebarRight?: unknown } | undefined)?.sidebarRight
  if (raw === null || typeof raw !== 'object') return undefined
  return raw as SidebarRightLike
}

/**
 * 读「当前会话」id —— 看板等无槽位注入的场景用
 * （sessions 服务的 list 快照 current / currentSessionId）。
 */
export function resolveCurrentSessionId(): string | undefined {
  try {
    const w = window as unknown as {
      __dshPmSessions?: { list?: { getSnapshot?: () => { current?: unknown; currentSessionId?: unknown } } }
      __dshPmCtx?: { sessions?: { list?: { getSnapshot?: () => { current?: unknown; currentSessionId?: unknown } } } }
    }
    const svc = w.__dshPmSessions ?? w.__dshPmCtx?.sessions
    const snap = svc?.list?.getSnapshot?.()
    const cur = snap?.current ?? snap?.currentSessionId
    if (typeof cur === 'string' && cur.length > 0) return cur
  } catch { /* 拿不到 → 返回 undefined，由调用方诊断 */ }
  return undefined
}

// ---------------------------------------------------------------------------
// REQ-260922012924-2e29 FR-4：文档路径绝对化
// 相对文档路径（docs/requirements/...）若以"当前会话工作区"为根解析，在非 agent-dh
// 工作区的会话里必打不开（2026-09-24 用户现场：w-9faaac35 工作区=dsh-pmboard）。
// 故看板 fetchState 后把服务端 workspaceRoot/homeDir 缓存到这里，打开与显示统一走绝对路径。
// ---------------------------------------------------------------------------

let cachedWorkspaceRoot: string | undefined
let cachedHomeDir: string | undefined

/** 缓存服务端工作区根与 homeDir（board-mount 在 fetchState 成功后调用；旧服务端无字段 → 保持 undefined 降级为相对解析）。 */
export function setDocWorkspaceContext(workspaceRoot: string | undefined, homeDir: string | undefined): void {
  cachedWorkspaceRoot = typeof workspaceRoot === 'string' && workspaceRoot.length > 0 ? workspaceRoot : undefined
  cachedHomeDir = typeof homeDir === 'string' && homeDir.length > 0 ? homeDir : undefined
}

/** 相对路径 → 绝对路径（已是绝对路径原样返回；无缓存根 → 原样返回，相对解析降级）。 */
export function absolutizeDocPath(path: string): string {
  if (path.startsWith('/') || /^[A-Za-z]:/.test(path)) return path
  if (cachedWorkspaceRoot === undefined) return path
  const root = cachedWorkspaceRoot.split('\\').join('/').replace(/\/+$/, '')
  const rel = path.split('\\').join('/').replace(/^(?:\.\/)+/, '')
  return root + '/' + rel
}

/** 显示用路径：绝对化后把 homeDir 前缀缩写为 ~（无缓存 → 原样）。 */
export function displayDocPath(path: string): string {
  const abs = absolutizeDocPath(path)
  if (cachedHomeDir !== undefined && abs.startsWith(cachedHomeDir + '/')) return '~' + abs.slice(cachedHomeDir.length)
  return abs
}

/**
 * 在官方右侧栏打开工作区文档。
 *
 * @returns true=已发起打开；false=未发起（原因已 console.error 说明）
 */
export function openDocInSidebar(ctx: unknown, path: string, sessionId: string | undefined): boolean {
  if (typeof sessionId !== 'string' || sessionId.length === 0) {
    console.error('[dsh-pmboard] open-doc: 取不到会话 id，无法构造 session 地址', { path })
    return false
  }
  const sr = sidebarRightOf(ctx)
  if (sr === undefined || typeof sr.openResource !== 'function') {
    console.error('[dsh-pmboard] open-doc: ctx.sidebarRight 不可用（官方右侧栏未加载）', { path })
    return false
  }
  // FR-4：相对路径先按服务端工作区根绝对化——dsh-resource 协议支持绝对路径（前导斜杠保留），
  // Host 按绝对路径读，不再依赖查看会话的工作区。
  const address = sessionFileAddress(sessionId, absolutizeDocPath(path))
  try {
    sr.openResource(address)
    return true
  } catch (error) {
    console.error('[dsh-pmboard] open-doc: openResource 调用失败', { address, error: String(error) })
    return false
  }
}
