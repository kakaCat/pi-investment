/**
 * @pi-investment/web-liveness · client 半（浏览器端）。
 *
 * 解决的事故（2026-09-16）：**服务端一重启，已经打开的标签页就"废"了** ——
 * 页面能开、消息发不出去、只能手动开新标签页。根因不是鉴权（cookie 跨重启有效），
 * 而是**没有任何机制在重启后刷新页面**：
 *   - 客户端 bundle 是 `Cache-Control: immutable` + `?rev=<进程 nonce>`，唯一能发现新版的
 *     入口是 index.html，而没人去重新拉它；
 *   - 框架自带的 HMR 只在**进程运行期间**发现 bundle 被改写才推 `rebuilt`，重启后不补发；
 *   - 我们自己的 5 个页面插件都只做裸 fetch 轮询，没有任何 reload / 重连感知。
 *
 * 本插件订阅框架在 `/plugins/events` 上的免鉴权 SSE（连上即推一帧 `graph`），把它的
 * `graph.rev` 与页面加载时注入的 `window.__DSH_BOOT__.rev` 比对：
 *   - 相同 → 同一进程（含同进程断线重连）→ 不做任何事；
 *   - 不同 → 服务端换过进程或 bundle 换过版 → 刷新页面（等用户停手后自动刷，也能手动点）；
 *   - 连不上 → 顶部横幅提示"服务重启中"，避免用户对着发不出去的消息干等。
 *
 * 判定逻辑全在 `watch.ts`（纯函数、有单测），本文件只做副作用编排。
 * @module web-liveness/client
 */
import { createBanner, type Banner } from './banner.js'
import { injectStyles } from './styles.js'
import {
  BOOT_CHECK_DELAY_MS,
  BOOT_PROBE_TIMEOUT_MS,
  DEFAULT_QUIET_MS,
  OFFLINE_GRACE_MS,
  RELOAD_GUARD_MS,
  RELOAD_POLL_MS,
  STREAM_UNAVAILABLE_MS,
  bootCheckDecision,
  bootRevOf,
  decideGraph,
  parseFrame,
  reloadAllowed,
  shouldReloadNow,
  type LivenessPhase,
} from './watch.js'

export const name = '@pi-investment/web-liveness/client'

// 不依赖任何 client 服务：boot graph 是页面内联脚本注入的全局量，SSE 是同源 HTTP。
export const inject: string[] = []

/** 上次自动刷新的时间戳（sessionStorage 跨 reload 保留 —— 刷新死循环的唯一闸门）。 */
const RELOAD_MARK_KEY = 'dsh-wlv-reload-at'

/** 免鉴权的 HMR/插件事件流；连上即推当前进程的 graph 帧。 */
const EVENTS_PATH = '/plugins/events'

/**
 * 开机自检的探测端点：插件页的数据源 RPC。它失败 ⟹ 页面启动时框架的一次性读取
 * （插件清单/模型/设置）也失败过 ⟹ 页面半初始化（空白插件页/模型不加载/输入发不出）。
 */
const BOOT_PROBE_PATH = '/api/dynamicCordisRunner/inventory'

const LOG = '[web-liveness]'

declare global {
  interface Window {
    /** HMR / 重复 apply 的清理句柄（各插件惯例：__dshXxxClient）。 */
    __dshWlvClient?: { dispose(): void }
  }
}

/** 读 sessionStorage（隐私模式等场景会抛，一律降级为 undefined）。 */
function readReloadMark(): number | undefined {
  try {
    const raw = window.sessionStorage.getItem(RELOAD_MARK_KEY)
    if (raw === null) return undefined
    const value = Number(raw)
    return Number.isFinite(value) ? value : undefined
  } catch {
    return undefined
  }
}

function writeReloadMark(now: number): void {
  try {
    window.sessionStorage.setItem(RELOAD_MARK_KEY, String(now))
  } catch {
    /* 存不进去就没有防抖 —— 可接受，readReloadMark 会返回 undefined */
  }
}

/** 用户还在不在打字：这些事件任一发生就更新"最后活动时刻"。 */
const INPUT_EVENTS = ['keydown', 'input', 'compositionstart', 'paste', 'pointerdown'] as const

export function apply(ctx: { logger?: (name: string) => { info(msg: string): void; warn(msg: string): void } }): void {
  try {
    injectStyles()
    // HMR / 壳重载先清理上一份挂载，防重复挂载（同 holdings/ bulletin 惯例）。
    window.__dshWlvClient?.dispose?.()

    const log = ctx.logger?.(name) ?? { info: () => {}, warn: () => {} }
    const bootRev = bootRevOf((window as unknown as { __DSH_BOOT__?: unknown }).__DSH_BOOT__)
    if (bootRev === undefined) {
      // 框架换了 boot 注入形状 —— 只提示、不刷新（信息不足时不动，比乱刷安全）。
      log.warn(`${LOG} window.__DSH_BOOT__.rev 读不到：只保留"服务重启中"提示，不做自动刷新`)
    }

    let lastInputAt = Date.now()
    const markInput = (): void => {
      lastInputAt = Date.now()
    }
    for (const type of INPUT_EVENTS) document.addEventListener(type, markInput, true)

    const startedAt = Date.now()
    let phase: LivenessPhase = 'ok'
    let everFramed = false
    let reloadScheduled = false
    /** 防抖闸门已拦下一次自动刷新 —— 本页生命周期内不再自动刷（防死循环）。 */
    let reloadBlocked = false
    let reloadPoll: number | undefined
    let offlineGrace: number | undefined
    let bootCheck: number | undefined

    const banner: Banner = createBanner(() => {
      // 手动点按不受"停顿/防抖"限制，但同样写标记，防止连点造成连环刷新。
      reload()
    })

    const setPhase = (next: LivenessPhase, options?: { pending?: boolean }): void => {
      if (next !== phase) {
        log.info(`${LOG} ${phase} → ${next}`)
        phase = next
      }
      banner.render(next, options)
    }

    /** 真正刷新（唯一的 location.reload 出口）。 */
    function reload(): void {
      writeReloadMark(Date.now())
      window.location.reload()
    }

    /** 停掉"等用户停手"的轮询。 */
    const stopReloadPoll = (): void => {
      if (reloadPoll !== undefined) {
        window.clearInterval(reloadPoll)
        reloadPoll = undefined
      }
    }

    /** stale 态：等一个可以刷新的时机（后台标签 / 用户停手 且 不在防抖窗口内）。 */
    const startReloadPoll = (): void => {
      if (reloadScheduled || reloadBlocked) return
      reloadScheduled = true
      const tick = (): void => {
        const now = Date.now()
        if (!reloadAllowed(readReloadMark(), now, RELOAD_GUARD_MS)) {
          // 刚刷过又判定 stale：多半是刷新拿到了缓存的旧 HTML —— 别刷成死循环，转为手动。
          stopReloadPoll()
          reloadBlocked = true
          log.warn(`${LOG} 距上次自动刷新不足 ${String(RELOAD_GUARD_MS)}ms，改为提示手动刷新`)
          setPhase('stale')
          return
        }
        if (shouldReloadNow({ hidden: document.hidden, lastInputAt, now, quietMs: DEFAULT_QUIET_MS })) {
          stopReloadPoll()
          log.info(`${LOG} 服务端已换版本，刷新页面`)
          reload()
          return
        }
        setPhase('stale', { pending: true })
      }
      reloadPoll = window.setInterval(tick, RELOAD_POLL_MS)
      tick()
    }

    /**
     * 开机自检：页面加载后探测一次 RPC 层。覆盖的场景是"页面在服务未完全就绪的瞬间
     * 加载"——rev 与进程一致（SSE 不会触发刷新），但框架的一次性读取已失败且永不重试，
     * 表现为插件/设置页空白、模型不加载、输入发不出去（2026-09-22 用户事故）。
     * 更糟的是该场景下请求会**永不返回**（僵尸连接，探针实测）：浏览器 6 条连接被占死后
     * 整个浏览器对本站饿死。所以探测必须带超时，超时一律按失败处理；触发的重载会在
     * 页面导航时拆掉本标签页的僵尸连接，连接池随之解放。
     * 只在 phase === 'ok'（同进程确认）时探测：offline/stale 自有流程接管，避免
     * "服务重启中把页面刷到浏览器错误页"。探测失败 ⟹ 页面半初始化 ⟹ 重载（受防抖闸门）。
     */
    const runBootCheck = async (): Promise<void> => {
      let probeOk = false
      const controller = new AbortController()
      const timeout = window.setTimeout(() => {
        controller.abort()
      }, BOOT_PROBE_TIMEOUT_MS)
      try {
        const res = await window.fetch(BOOT_PROBE_PATH, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: '{}',
          signal: controller.signal,
        })
        probeOk = res.ok
      } catch {
        probeOk = false
      } finally {
        window.clearTimeout(timeout)
      }
      switch (bootCheckDecision(phase, probeOk)) {
        case 'healthy':
          log.info(`${LOG} 开机自检通过：RPC 层就绪`)
          // ctx.logger 走 buffered exporter 不进 console；自检是用户可见的自愈动作，
          // 同步一份到 console 方便排障（2026-09-22 探针验证时 console 验收扑空的教训）。
          console.info(`${LOG} 开机自检通过：RPC 层就绪`)
          return
        case 'reload': {
          const now = Date.now()
          if (!reloadAllowed(readReloadMark(), now, RELOAD_GUARD_MS)) {
            // 刚刷过还是坏的（服务仍未就绪）—— 别刷成死循环，转为手动提示。
            log.warn(`${LOG} 开机自检仍失败且距上次刷新不足 ${String(RELOAD_GUARD_MS)}ms，改为提示手动刷新`)
            console.warn(`${LOG} 开机自检仍失败且距上次刷新不足 ${String(RELOAD_GUARD_MS)}ms，改为提示手动刷新`)
            setPhase('stale')
            return
          }
          log.warn(`${LOG} 开机自检失败：页面在服务未就绪时加载（插件/设置/模型读取已损坏），自动刷新`)
          console.warn(`${LOG} 开机自检失败：页面在服务未就绪时加载（插件/设置/模型读取已损坏），自动刷新`)
          reload()
          return
        }
        default:
          return // skip：offline/stale 交给既有流程
      }
    }
    bootCheck = window.setTimeout(() => {
      void runBootCheck()
    }, BOOT_CHECK_DELAY_MS)

    const es = new EventSource(EVENTS_PATH)

    es.onmessage = (event: MessageEvent<string>): void => {
      const frame = parseFrame(event.data)
      if (frame === undefined || frame.type !== 'graph') return // rebuilt 等帧型由 HMR 自己处理
      everFramed = true
      if (offlineGrace !== undefined) {
        window.clearTimeout(offlineGrace)
        offlineGrace = undefined
      }
      switch (decideGraph(bootRev, frame.rev)) {
        case 'recover':
          stopReloadPoll()
          reloadScheduled = false
          setPhase('ok')
          break
        case 'reload':
          setPhase('stale', { pending: true })
          startReloadPoll()
          break
        default:
          break // ignore：信息不足，不动
      }
    }

    es.onerror = (): void => {
      // EventSource 自带重连（服务端可用时按 retry: 节流），这里只负责提示。
      if (phase === 'stale' || offlineGrace !== undefined) return
      offlineGrace = window.setTimeout(() => {
        offlineGrace = undefined
        // 从来没收到过任何帧、且已远超启动期 → 这条流本身不可用，退化为"本插件不存在"。
        if (!everFramed && Date.now() - startedAt > STREAM_UNAVAILABLE_MS) {
          log.warn(`${LOG} ${EVENTS_PATH} 始终没有可用帧，关闭监听（自动刷新不可用）`)
          dispose()
          return
        }
        setPhase('offline')
      }, OFFLINE_GRACE_MS)
    }

    function dispose(): void {
      stopReloadPoll()
      if (offlineGrace !== undefined) {
        window.clearTimeout(offlineGrace)
        offlineGrace = undefined
      }
      if (bootCheck !== undefined) {
        window.clearTimeout(bootCheck)
        bootCheck = undefined
      }
      es.close()
      banner.dispose()
      for (const type of INPUT_EVENTS) document.removeEventListener(type, markInput, true)
      delete window.__dshWlvClient
    }

    window.__dshWlvClient = { dispose }
    log.info(`${LOG} 已接管：boot rev=${bootRev ?? '(未知)'}，监听 ${EVENTS_PATH}`)
  } catch (error) {
    console.error('[web-liveness] client half failed to start:', error)
  }
}
