/**
 * web-liveness 验收测试：**真浏览器 + 真重启**。
 *
 * 单测（tests/watch.test.ts）只能证明"判定函数写得对"，证明不了"重启时浏览器真的会刷新" ——
 * 而这恰恰是本次事故的全部内容。所以这个脚本做端到端：
 *
 *   1. 从 launchd 日志里取当前 :13080 的带 token URL，拉起一个**独立**的 headless Chrome
 *      （临时 user-data-dir，不碰用户正在用的浏览器）；
 *   2. 等页面加载完，读 `window.__DSH_BOOT__.rev`（= 重启前那个进程），并确认 client 半已接管；
 *   3. `launchctl kickstart -k` 真重启服务 —— 此刻页面是"开着"的，就是事故现场；
 *   4. 观察三件事：横幅是否提示"服务重启中" / 页面是否自动刷新 / 刷新后 rev 是否变成新进程的；
 *   5. 用 Page.addScriptToEvaluateOnNewDocument 埋的导航计数器确认**只刷新一次**（没刷成死循环）。
 *
 * 用法（会重启 :13080！）：
 *   node agent-dh/packages/pages/web-liveness/scripts/e2e-restart-reload.mjs
 *
 * 退出码：0 通过 / 1 断言未过 / 2 环境异常。
 */
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, readFileSync, rmSync } from 'node:fs'
import { once } from 'node:events'
import { setTimeout as sleep } from 'node:timers/promises'

const AGENT_DH = new URL('../../../../', import.meta.url).pathname.replace(/\/$/, '')
const PORT = Number(process.env.WLV_PORT || 13080)
const CDP_PORT = Number(process.env.WLV_CDP_PORT || 9333)
const CHROME = process.env.WLV_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const PROFILE = `/tmp/wl-e2e-chrome-${String(CDP_PORT)}`
/** launchd 日志位置（在 worktree 里跑时用 WLV_LOG 指向真实实例的日志）。 */
const LOG = process.env.WLV_LOG || `${AGENT_DH}/.dsh-data/state/launchd.out.log`
const POLL_MS = 400
const NAV_COUNTER = `try { sessionStorage.setItem('e2e-loads', String(Number(sessionStorage.getItem('e2e-loads') || '0') + 1)) } catch (e) {}`

/** 当前实例的带 token URL：launchd 日志里最后一条 "dsh web: http://…" 属于正在跑的进程。 */
function currentUrl() {
  if (!existsSync(LOG)) throw new Error(`找不到 launchd 日志：${LOG}`)
  const hits = [...readFileSync(LOG, 'utf8').matchAll(/dsh web: (http:\/\/\S+)/g)]
  if (hits.length === 0) throw new Error(`日志里没有 "dsh web:" 行：${LOG}`)
  return hits[hits.length - 1][1].replace('localhost', '127.0.0.1')
}

let ws
let msgId = 0
const pending = new Map()

function send(method, params = {}) {
  const id = ++msgId
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (r.exceptionDetails) return { error: r.exceptionDetails.text }
  return { value: r.result?.value }
}

const SNAPSHOT = `(() => {
  const bar = document.querySelector('.dsh-wlv-bar');
  return {
    rev: window.__DSH_BOOT__ && window.__DSH_BOOT__.rev,
    phase: bar ? bar.dataset.phase : null,
    text: bar ? (bar.textContent || '').slice(0, 70) : null,
    loads: Number(sessionStorage.getItem('e2e-loads') || '0'),
    guard: sessionStorage.getItem('dsh-wlv-reload-at'),
    hasClient: !!window.__dshWlvClient,
  };
})()`

async function connect() {
  for (let i = 0; i < 80; i++) {
    const list = await fetch(`http://127.0.0.1:${String(CDP_PORT)}/json/list`).then((r) => r.json()).catch(() => [])
    const page = list.find((t) => t.type === 'page' && t.url.includes(`:${String(PORT)}`))
    if (page?.webSocketDebuggerUrl) {
      ws = new WebSocket(page.webSocketDebuggerUrl)
      await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
      ws.onmessage = (ev) => {
        const m = JSON.parse(ev.data)
        const p = pending.get(m.id)
        if (!p) return
        pending.delete(m.id)
        if (m.error) p.reject(new Error(JSON.stringify(m.error)))
        else p.resolve(m.result)
      }
      return
    }
    await sleep(250)
  }
  throw new Error(`找不到 :${String(PORT)} 的页面 target`)
}

/** SSE 是永不结束的流：r.text() 会一直等下去，必须边读边匹配再中断。 */
async function sseGraphRev() {
  const ctrl = new AbortController()
  try {
    const res = await fetch(`http://127.0.0.1:${String(PORT)}/plugins/events`, { signal: ctrl.signal })
    const reader = res.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    while (buf.length < 8192) {
      const { value, done } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const m = buf.match(/"type":"graph","graph":\{"rev":"([^"]+)"/)
      if (m) return m[1]
    }
    return null
  } catch {
    return null
  } finally {
    ctrl.abort()
  }
}

async function main() {
  const url = currentUrl()
  console.log(`[e2e] 目标 ${url.replace(/token=\S+/, 'token=***')}`)
  rmSync(PROFILE, { recursive: true, force: true })
  const chrome = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--user-data-dir=${PROFILE}`, `--remote-debugging-port=${String(CDP_PORT)}`, url,
  ], { stdio: 'ignore' })

  try {
    await connect()
    await send('Runtime.enable')
    await send('Page.enable')
    await send('Page.addScriptToEvaluateOnNewDocument', { source: NAV_COUNTER })

    const t0 = Date.now()
    const at = () => `${((Date.now() - t0) / 1000).toFixed(1)}s`

    for (let i = 0; i < 60; i++) {
      if ((await evaluate('document.readyState')).value === 'complete') break
      await sleep(200)
    }
    await sleep(1500) // 给 client 半 apply 的时间
    const s0 = (await evaluate(SNAPSHOT)).value
    console.log(`[e2e] ${at()} 加载完成 bootRev=${s0.rev} 插件已接管=${String(s0.hasClient)} 已导航 ${s0.loads} 次`)
    if (!s0.rev || !s0.hasClient) throw new Error('client 半未接管或读不到 bootRev，观测无意义')

    await sleep(800)
    console.log(`[e2e] ${at()} 重启服务（kickstart -k）…`)
    spawnSync('launchctl', ['kickstart', '-k', `gui/${String(process.getuid())}/com.pi-investment.dsh`])

    let sawOffline = false
    let revAfter = null
    let reloadedAt = null
    const phases = new Set()
    const deadline = Date.now() + 75_000
    while (Date.now() < deadline) {
      const s = (await evaluate(SNAPSHOT)).value
      if (s) {
        if (s.phase && !phases.has(s.phase)) {
          phases.add(s.phase)
          console.log(`[e2e] ${at()} 横幅 phase=${s.phase}「${s.text}」`)
        }
        if (s.phase === 'offline') sawOffline = true
        if (revAfter === null && s.rev && s.rev !== s0.rev) {
          revAfter = s.rev
          reloadedAt = Date.now()
          console.log(`[e2e] ${at()} ✅ 页面已刷新：rev ${s0.rev} → ${revAfter}（导航 ${String(s.loads)} 次，防抖标记 ${String(s.guard)}）`)
        }
        if (reloadedAt !== null && Date.now() - reloadedAt > 8000) break // 刷新后再观察 8s，确认不再刷
      }
      await sleep(POLL_MS)
    }

    const fin = (await evaluate(SNAPSHOT)).value
    const ssRev = await sseGraphRev()
    const reloadCount = fin.loads - s0.loads

    console.log('')
    console.log('──── 结果 ────')
    console.log(`重启前 bootRev      : ${s0.rev}`)
    console.log(`刷新后 bootRev      : ${fin.rev}`)
    console.log(`当前 SSE graph.rev  : ${String(ssRev)}`)
    console.log(`横幅序列            : ${[...phases].join(' → ') || '(无)'}`)
    console.log(`自动刷新导航次数    : ${String(reloadCount)}（期望 1）`)
    const ok = sawOffline && revAfter !== null && fin.rev === ssRev && reloadCount === 1
    console.log(ok
      ? '✅ 通过：重启时提示 + 自动刷新一次 + 刷新后与新进程一致（无死循环）'
      : '❌ 未通过（见上）')
    return ok ? 0 : 1
  } finally {
    // 清理失败不能掩盖测试结论：Chrome 退出前还在写 profile，rm 会 ENOTEMPTY。
    chrome.kill()
    await Promise.race([once(chrome, 'exit'), sleep(3000)]).catch(() => {})
    try {
      rmSync(PROFILE, { recursive: true, force: true })
    } catch {
      console.warn(`[e2e] 临时 profile 未清干净（可忽略）：${PROFILE}`)
    }
  }
}

main()
  .then((code) => process.exit(code))
  .catch((e) => { console.error('[e2e] 异常:', e); process.exit(2) })
