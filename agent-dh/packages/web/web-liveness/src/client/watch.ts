/**
 * web-liveness · 判定逻辑（纯函数，无 DOM / 无计时器 —— 单测直接覆盖这一层）。
 *
 * 机制（2026-09-16 实测确认，见 docs/architecture/web-liveness.md）：
 *   框架的 `@deepseek-ai/dsh-client-hmr` 在 `/plugins/events` 上开了一条**免鉴权** SSE，
 *   连上就推一帧 `{"type":"graph","graph":{"rev":…}}`。而每条 bundle 的 rev 在进程启动时
 *   是 `randomBytes(8)` 生成的**进程 nonce**（`dsh-client-modules` 的
 *   `initialRevisionNonce`），graph.rev 又是这些 rev 的哈希。于是：
 *
 *     SSE 的 graph.rev === 页面加载时注入的 window.__DSH_BOOT__.rev
 *         ⟺ 同一个进程、同一版客户端代码
 *     ≠  ⟹ 服务端重启过，或 bundle 被改写（HMR）—— 两种情况都该刷新页面
 *
 *   同进程断线重连不会改变 rev，因此"网络抖一下"不会误刷新。
 *
 * @module web-liveness/client/watch
 */

/** 从 SSE `data:` 里解析出来的最小帧形状（其余帧型一律忽略）。 */
export interface LivenessFrame {
  type: string
  /** 仅 `type === 'graph'` 时有值。 */
  rev?: string
}

/** SSE 连接用户可见的三种状态。 */
export type LivenessPhase =
  /** 正常：连得上，且与服务端同版本。 */
  | 'ok'
  /** 连不上：服务端正在重启 / 网络断了。 */
  | 'offline'
  /** 连上了，但服务端已换进程或客户端已换版 —— 页面是旧的。 */
  | 'stale'

/** 一帧 graph 该导致的动作。 */
export type GraphDecision =
  /** 不做任何事（信息不足，宁可不动）。 */
  | 'ignore'
  /** 同一进程 —— 若之前在 offline，则收起横幅。 */
  | 'recover'
  /** 换过进程/换过版 —— 该刷新页面。 */
  | 'reload'

/** 用户最近 5s 内有过输入就暂不自动刷新（避免刷掉还没发出去的草稿）。 */
export const DEFAULT_QUIET_MS = 5_000

/** 两次自动刷新之间的最小间隔；防止"刷新后仍拿到旧 HTML"造成的刷新死循环。 */
export const RELOAD_GUARD_MS = 15_000

/** detection 之后轮询"现在能不能刷"的间隔。 */
export const RELOAD_POLL_MS = 1_000

/** offline 横幅的显示宽限：短到看不见的抖动不闪横幅。 */
export const OFFLINE_GRACE_MS = 1_000

/**
 * 从未收到过任何 SSE 帧、且已过去这么久 —— 认定该端点不可用（框架改动/HMR 被禁用），
 * 关闭流并撤下横幅，退化为"本插件不存在"，而不是让横幅常驻。
 */
export const STREAM_UNAVAILABLE_MS = 90_000

/**
 * 开机自检的探测时机：页面加载后等这么久，让页面自己的启动读取先跑完再下结论。
 *
 * 背景（2026-09-22 用户事故）：页面在服务未完全就绪的瞬间加载，框架的**一次性读取**
 * （cordis 插件清单 / 模型列表 / 设置）失败且永不重试 —— 插件页、设置页空白、模型
 * 选择器不加载、输入发不出去，且此时 rev 与进程一致，SSE 比对不会触发任何刷新。
 * 探测目标与插件页同源（`POST /api/dynamicCordisRunner/inventory`）：它失败 ⟹ 页面
 * 自己的启动读取也几乎必然失败过 ⟹ 这页已经半初始化，唯一修复是重载。
 */
export const BOOT_CHECK_DELAY_MS = 8_000

/** 开机自检的动作。 */
export type BootCheckAction =
  /** 不该探测：offline/stale 由既有 SSE 流程接管（避免"服务重启中把页面刷到错误页"）。 */
  | 'skip'
  /** 探测通过：RPC 层就绪，页面完好。 */
  | 'healthy'
  /** 探测失败：页面在服务未就绪时加载，已半初始化 —— 重载是唯一修复。 */
  | 'reload'

/**
 * 开机自检判定。
 * @param phase - 当前 SSE 相位（仅 `ok` = 同进程确认后才探测；其余相位自有流程接管）。
 * @param probeOk - 对 RPC 层的探测是否成功（fetch 网络错误或非 2xx 都算失败）。
 */
export function bootCheckDecision(phase: LivenessPhase, probeOk: boolean): BootCheckAction {
  if (phase !== 'ok') return 'skip'
  return probeOk ? 'healthy' : 'reload'
}

/**
 * 读取页面加载时注入的 boot graph 版本号。
 * @param boot - `window.__DSH_BOOT__` 的原始值（形状随框架版本可能变，一律宽容读取）。
 * @returns rev 字符串；读不到则 undefined（调用方据此退化为"只提示、不刷新"）。
 */
export function bootRevOf(boot: unknown): string | undefined {
  if (typeof boot !== 'object' || boot === null) return undefined
  const rev = (boot as { rev?: unknown }).rev
  return typeof rev === 'string' && rev !== '' ? rev : undefined
}

/**
 * 解析一帧 SSE data。
 * @param raw - `MessageEvent.data` 原文。
 * @returns 帧对象；非 JSON、非对象、缺 `type` 时返回 undefined。
 */
export function parseFrame(raw: string): LivenessFrame | undefined {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return undefined
  }
  if (typeof parsed !== 'object' || parsed === null) return undefined
  const record = parsed as { type?: unknown; graph?: unknown }
  if (typeof record.type !== 'string') return undefined
  const graph = record.graph
  const rev =
    typeof graph === 'object' && graph !== null && typeof (graph as { rev?: unknown }).rev === 'string'
      ? ((graph as { rev: string }).rev)
      : undefined
  return rev === undefined ? { type: record.type } : { type: record.type, rev }
}

/**
 * 判定一帧 graph 该做什么。
 * @param bootRev - 页面加载时的 rev（`bootRevOf` 的结果）。
 * @param graphRev - 刚收到的 graph 帧的 rev。
 * @returns 见 {@link GraphDecision}；任一 rev 读不到时一律 `ignore`（信息不足时不动比乱刷安全）。
 */
export function decideGraph(bootRev: string | undefined, graphRev: string | undefined): GraphDecision {
  if (bootRev === undefined || graphRev === undefined) return 'ignore'
  return bootRev === graphRev ? 'recover' : 'reload'
}

/**
 * 现在是否可以自动刷新：页面在后台（没人在看）或用户已停顿足够久。
 * @param hidden - `document.hidden`。
 * @param lastInputAt - 最后一次用户输入的时间戳（ms）。
 * @param now - 当前时间戳（ms）。
 * @param quietMs - 停顿阈值，默认 {@link DEFAULT_QUIET_MS}。
 */
export function shouldReloadNow(opts: {
  hidden: boolean
  lastInputAt: number
  now: number
  quietMs?: number
}): boolean {
  if (opts.hidden) return true
  return opts.now - opts.lastInputAt >= (opts.quietMs ?? DEFAULT_QUIET_MS)
}

/**
 * 刷新防抖闸门：距上次自动刷新不足 {@link RELOAD_GUARD_MS} 就拒绝再刷。
 * @param lastReloadAt - 上次自动刷新的时间戳；从未刷过传 undefined。
 * @param now - 当前时间戳（ms）。
 * @param guardMs - 闸门宽度，默认 {@link RELOAD_GUARD_MS}。
 */
export function reloadAllowed(lastReloadAt: number | undefined, now: number, guardMs = RELOAD_GUARD_MS): boolean {
  if (lastReloadAt === undefined || !Number.isFinite(lastReloadAt)) return true
  return now - lastReloadAt >= guardMs
}
