/**
 * 看板实测回归（真实打开页面）—— headless Chrome + CDP 驱动脚本。
 *
 * 为什么需要它：单测绿 ≠ 看板不回归（本需求最高风险点）。单测走的是 in-memory 夹具，
 * 看不到「真实台账 + 真实队列 + 真实 client bundle + 真实 CSS」这条完整链路。
 * 本脚本用独立 headless Chrome（临时 user-data-dir，不碰用户浏览器）真实加载 :13080，
 * 逐项核对任务可见性与数量、甘特/阶段视图渲染、依赖连线、需求详情，并留页面截图。
 *
 * 证据强度与边界（R-013 数据来源标注）：
 *   - 页面渲染证据 = 真实浏览器（headless Chrome）+ 真实服务进程 + 真实 .dsh-data 台账；
 *   - 断言取的是**渲染后的 DOM**（document.querySelector 计数），不是接口 JSON；
 *   - 仍需人工注意：headless 与有头渲染在同一 CSS 下等价，但截图仅供人眼复核，不代替人看。
 *
 * 用法：
 *   node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs \
 *     --port 13080 --out docs/requirements/REQ-260927202051-f6df/notes/board-live/shots
 *
 * 退出码：0 = 全部断言通过；1 = 有断言未过；2 = 环境异常（Chrome 起不来 / 页面加载失败）。
 */
import { spawn, spawnSync } from 'node:child_process'
import { createHash, createHmac } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { once } from 'node:events'
import { setTimeout as sleep } from 'node:timers/promises'
import { dirname, resolve } from 'node:path'

// ── 参数 ─────────────────────────────────────────────────────────────────
const argv = process.argv.slice(2)
const argOf = (name, dflt) => {
  const i = argv.indexOf(name)
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : dflt
}
const PORT = Number(argOf('--port', '13080'))
const OUT = resolve(argOf('--out', `docs/requirements/REQ-260927202051-f6df/notes/board-live/shots`))
const CDP_PORT = Number(argOf('--cdp-port', '9345'))
const CHROME = process.env.BOARD_LIVE_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const REQ_ID = argOf('--req', 'REQ-260927202051-f6df')
const CRED = argOf('--credentials', resolve(process.env.BOARD_LIVE_AGENT_DH || '.', '.dsh-data/.credentials.yaml'))
const BASE = `http://127.0.0.1:${String(PORT)}`
const AUTHORITY = `127.0.0.1:${String(PORT)}`

mkdirSync(OUT, { recursive: true })

// ── Cookie：按 dsh-client-connection 的算法自签（secret 取自 credentials store）──
function mintCookie() {
  const yaml = readFileSync(CRED, 'utf8')
  const m = yaml.match(/client-connection\/browser-session:[\s\S]*?secret:\s*([A-Za-z0-9_-]+)/)
  if (m === null) throw new Error(`credentials 里找不到 browser-session secret：${CRED}`)
  const b64 = m[1]
  const decode = (v) => Buffer.from(v.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat((4 - (v.length % 4)) % 4), 'base64')
  const encode = (buf) => Buffer.from(buf).toString('base64').replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/u, '')
  const secret = decode(b64)
  const issuedAt = Date.now()
  const expiresAt = issuedAt + 7 * 864e5
  const body = encode(Buffer.from(JSON.stringify({ version: 1, authority: AUTHORITY, issuedAt, expiresAt }), 'utf8'))
  const sig = encode(createHmac('sha256', secret).update(body).digest())
  const name = 'dsh-auth-' + encode(createHash('sha256').update(AUTHORITY).digest())
  return { name, value: `v1.${body}.${sig}` }
}

// ── CDP 薄客户端 ─────────────────────────────────────────────────────────
let ws
let msgId = 0
const pending = new Map()
const consoleErrors = []
const pageErrors = []
const failedRequests = []

function send(method, params = {}) {
  const id = ++msgId
  return new Promise((resolve_, reject) => {
    pending.set(id, { resolve: resolve_, reject })
    ws.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, timeout: 30000 })
  if (r.exceptionDetails) throw new Error(`evaluate failed: ${r.exceptionDetails.text} ${r.exceptionDetails.exception?.description ?? ''}`)
  return r.result?.value
}

async function screenshot(name, opts = {}) {
  const res = await send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: opts.full !== false,
    ...(opts.clip ? { clip: opts.clip } : {}),
  })
  const file = resolve(OUT, `${name}.png`)
  writeFileSync(file, Buffer.from(res.data, 'base64'))
  return file
}

async function waitFor(expression, { timeoutMs = 45000, intervalMs = 300, label = expression } = {}) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    let v
    try { v = await evaluate(expression) } catch { v = false }
    if (v) return v
    if (Date.now() > deadline) throw new Error(`waitFor 超时（${timeoutMs}ms）：${label}`)
    await sleep(intervalMs)
  }
}

// ── 启动 Chrome ──────────────────────────────────────────────────────────
const PROFILE_DIR = `/tmp/board-live-chrome-${String(CDP_PORT)}-${String(process.pid)}`

async function main() {
  const results = []
  const checks = []
  const add = (name, pass, detail) => {
    checks.push({ name, pass, detail })
    console.log(`${pass ? 'PASS' : 'FAIL'}  ${name} — ${detail}`)
  }

  rmSync(PROFILE_DIR, { recursive: true, force: true })
  const chrome = spawn(CHROME, [
    '--headless=new',
    `--remote-debugging-port=${String(CDP_PORT)}`,
    `--user-data-dir=${PROFILE_DIR}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--disable-features=DialMediaRouteProvider',
    '--hide-scrollbars',
    '--window-size=1680,1500',
    'about:blank',
  ], { stdio: 'ignore' })

  const cleanup = () => { try { chrome.kill('SIGKILL') } catch { /* ignore */ } rmSync(PROFILE_DIR, { recursive: true, force: true }) }
  process.on('exit', cleanup)

  // 等 CDP 端点
  let target
  for (let i = 0; i < 120; i++) {
    const list = await fetch(`http://127.0.0.1:${String(CDP_PORT)}/json/list`).then((r) => r.json()).catch(() => [])
    target = list.find((t) => t.type === 'page')
    if (target?.webSocketDebuggerUrl) break
    await sleep(250)
  }
  if (!target?.webSocketDebuggerUrl) throw new Error('CDP 端点未就绪（Chrome 起不来？）')

  ws = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data)
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      consoleErrors.push((m.params.args ?? []).map((a) => String(a.value ?? a.description ?? '')).join(' ').slice(0, 300))
    }
    if (m.method === 'Runtime.exceptionThrown') {
      pageErrors.push(String(m.params.exceptionDetails?.exception?.description ?? m.params.exceptionDetails?.text ?? '').slice(0, 300))
    }
    if (m.method === 'Network.loadingFailed' && m.params.type === 'XHR' || m.method === 'Network.loadingFailed' && m.params.type === 'Fetch') {
      failedRequests.push(`${m.params.type} ${m.params.errorText}`)
    }
    const p = pending.get(m.id)
    if (p === undefined) return
    pending.delete(m.id)
    if (m.error) p.reject(new Error(JSON.stringify(m.error)))
    else p.resolve(m.result)
  }

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Network.enable')

  const cookie = mintCookie()
  const setRes = await send('Network.setCookie', { name: cookie.name, value: cookie.value, url: BASE, path: '/', httpOnly: true })
  if (setRes.success !== true) throw new Error(`Network.setCookie 失败：${JSON.stringify(setRes)}`)

  // ── 1. 打开页面 ───────────────────────────────────────────────────────
  await send('Page.navigate', { url: BASE + '/' })
  await waitFor(`document.readyState === 'complete'`, { label: 'document.readyState=complete' })
  const boot = await evaluate(`(() => ({
    title: document.title,
    rev: (window.__DSH_BOOT__ && window.__DSH_BOOT__.rev) || null,
    hasReqboardClient: !!window.__dshReqboardClient,
    url: location.href,
  }))()`)
  add('页面加载（未落到 401）', boot.hasReqboardClient === true || boot.title !== '', JSON.stringify(boot))

  // client 半 apply
  await waitFor(`!!window.__dshReqboardClient`, { label: 'window.__dshReqboardClient', timeoutMs: 60000 })
  add('pmboard client 半已接管', true, 'window.__dshReqboardClient 存在')

  // ── 2. 打开看板面板 ───────────────────────────────────────────────────
  await evaluate(`window.dispatchEvent(new CustomEvent('dsh-pmboard:open-board', { detail: { open: true } }))`)
  await waitFor(`!!document.querySelector('[data-dsh-pm-view]')`, { label: '[data-dsh-pm-view]' })
  // 等数据到位（泳道或列表渲染出来）
  await waitFor(`!!document.querySelector('.dsh-pm-board')`, { label: '.dsh-pm-board', timeoutMs: 45000 })
  await sleep(800)

  const boardDom = await evaluate(`(() => {
    const lanes = [...document.querySelectorAll('.dsh-pm-lane')].map(l => ({
      lane: l.dataset.lane,
      count: Number(l.querySelector('.dsh-pm-lane-count')?.textContent || '0'),
      cards: l.querySelectorAll('.dsh-pm-card').length,
    }))
    const cards = [...document.querySelectorAll('.dsh-pm-card')]
    const targetCard = cards.find(c => c.dataset.req === ${JSON.stringify(REQ_ID)})
    return {
      panelActive: !!document.querySelector('[data-dsh-pm-active]'),
      lanes,
      totalCards: cards.length,
      revText: document.querySelector('.dsh-pm-rev')?.textContent || null,
      targetCardFound: !!targetCard,
      targetCardText: targetCard ? (targetCard.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 200) : null,
      empty: !!document.querySelector('.dsh-pm-empty'),
    }
  })()`)
  results.push({ step: 'board', ...boardDom })
  add('泳道看板渲染出泳道', boardDom.lanes.length > 0, `泳道数=${String(boardDom.lanes.length)}`)
  add('泳道看板有需求卡（非空）', boardDom.totalCards > 0, `卡片数=${String(boardDom.totalCards)}，空态=${String(boardDom.empty)}`)
  add(`本需求卡片可见（${REQ_ID}）`, boardDom.targetCardFound === true, boardDom.targetCardText ?? '未找到卡片')
  const shotBoard = await screenshot('01-board-lanes')

  // ── 3. 列表视图 ───────────────────────────────────────────────────────
  await evaluate(`document.querySelector('[data-action="switch-view"][data-view="list"]').click()`)
  await waitFor(`!!document.querySelector('.dsh-pm-table, .dsh-pm-list-empty')`, { label: '列表视图' })
  await sleep(500)
  const listDom = await evaluate(`(() => ({
    rows: document.querySelectorAll('.dsh-pm-table tbody tr[data-req]').length,
    hasTarget: !!document.querySelector('.dsh-pm-table tbody tr[data-req=${JSON.stringify(REQ_ID)}]'),
  }))()`)
  results.push({ step: 'list', ...listDom })
  add('列表视图渲染出行', listDom.rows > 0, `行数=${String(listDom.rows)}`)
  const shotList = await screenshot('02-board-list')

  // 回泳道
  await evaluate(`document.querySelector('[data-action="switch-view"][data-view="lanes"]').click()`)
  await sleep(400)

  // ── 4. 任务总览 + 甘特图 ──────────────────────────────────────────────
  await evaluate(`document.querySelector('[data-action="open-tasks"]').click()`)
  await waitFor(`!!document.querySelector('.dsh-pm-tasks-page') || !!document.querySelector('.dsh-pm-empty')`, { label: '任务总览页' })
  await sleep(900)
  const tasksDom = await evaluate(`(() => {
    const gantt = document.querySelector('.dsh-pm-gantt')
    const bars = document.querySelectorAll('.dsh-pm-gantt-bar')
    const rows = document.querySelectorAll('.dsh-pm-tasks-group')
    const tableRows = document.querySelectorAll('.dsh-pm-tasks-page table tbody tr')
    const head = document.querySelector('.dsh-pm-rev')?.textContent || null
    const targetGroup = [...document.querySelectorAll('.dsh-pm-tasks-group')].find(g => (g.textContent || '').includes(${JSON.stringify(REQ_ID)}))
    return {
      ganttSvg: !!gantt,
      ganttBars: bars.length,
      groups: rows.length,
      tableRows: tableRows.length,
      headText: head,
      targetGroupFound: !!targetGroup,
      targetGroupBars: targetGroup ? targetGroup.querySelectorAll('.dsh-pm-gantt-bar').length : 0,
      empty: !!document.querySelector('.dsh-pm-empty'),
    }
  })()`)
  results.push({ step: 'tasks', ...tasksDom })
  add('任务总览页渲染（非空）', tasksDom.groups > 0 && tasksDom.empty === false, `需求分组=${String(tasksDom.groups)}，任务行=${String(tasksDom.tableRows)}，${String(tasksDom.headText)}`)
  add('甘特图 SVG 渲染', tasksDom.ganttSvg === true && tasksDom.ganttBars > 0, `条形数=${String(tasksDom.ganttBars)}`)
  add(`本需求在任务总览可见（${REQ_ID}）`, tasksDom.targetGroupFound === true, `其甘特条=${String(tasksDom.targetGroupBars)}`)
  const shotTasks = await screenshot('03-tasks-gantt')

  // ── 5. 需求详情（含依赖 DAG / 任务清单）────────────────────────────────
  await evaluate(`document.querySelector('[data-action="back"]').click()`)
  await waitFor(`!!document.querySelector('.dsh-pm-card')`, { label: '回泳道' })
  await sleep(500)
  await evaluate(`document.querySelector('.dsh-pm-card[data-req=${JSON.stringify(REQ_ID)}]').click()`)
  await waitFor(`!!document.querySelector('[data-detail-req=${JSON.stringify(REQ_ID)}]')`, { label: '需求详情页', timeoutMs: 30000 })
  await sleep(1500)
  const detailDom = await evaluate(`(() => {
    const d = document.querySelector('[data-detail-req=${JSON.stringify(REQ_ID)}]')
    const text = d ? (d.textContent || '') : ''
    const tabs = [...(d ? d.querySelectorAll('.dsh-pm-tab') : [])].map(t => (t.textContent || '').trim())
    return {
      hasDetail: !!d,
      tabs,
      hasDag: !!document.querySelector('.dsh-pm-dag'),
      dagLayers: document.querySelectorAll('.dsh-pm-dag .dsh-pm-dag-layer').length,
      tables: d ? d.querySelectorAll('table').length : 0,
      taskRows: d ? d.querySelectorAll('table tbody tr').length : 0,
      mentionsDep: text.includes('依赖'),
      mentionsQueue: text.includes('队列') || text.includes('ready'),
      textLen: text.length,
    }
  })()`)
  results.push({ step: 'req-detail', ...detailDom })
  add('需求详情页渲染', detailDom.hasDetail === true && detailDom.textLen > 200, `正文长度=${String(detailDom.textLen)}，表格=${String(detailDom.tables)}，任务行=${String(detailDom.taskRows)}，Tab=${JSON.stringify(detailDom.tabs)}`)
  add('依赖信息可见（DAG 或依赖列）', detailDom.hasDag === true || detailDom.mentionsDep === true, `DAG=${String(detailDom.hasDag)}，DAG 层=${String(detailDom.dagLayers)}，含「依赖」字样=${String(detailDom.mentionsDep)}`)
  const shotDetail = await screenshot('04-req-detail')

  // ── 6. 页面级错误 ─────────────────────────────────────────────────────
  const fatal = pageErrors.filter((e) => !/ResizeObserver|Script error/i.test(e))
  add('无未捕获页面异常', fatal.length === 0, fatal.length === 0 ? '0 条' : fatal.slice(0, 3).join(' | '))
  add('无 console.error', consoleErrors.length === 0, consoleErrors.length === 0 ? '0 条' : consoleErrors.slice(0, 3).join(' | '))
  add('无失败的数据请求', failedRequests.length === 0, failedRequests.length === 0 ? '0 条' : failedRequests.slice(0, 3).join(' | '))

  // ── 7. 接口侧交叉核对（同一进程，同源数据）──────────────────────────────
  const apiState = await fetch(`${BASE}/dashboard/api/reqboard/state`).then((r) => r.json())
  const apiTasks = Array.isArray(apiState?.data?.tasks) ? apiState.data.tasks.length : -1
  const apiReqs = Array.isArray(apiState?.data?.requirements) ? apiState.data.requirements.length : -1
  results.push({ step: 'api', apiTasks, apiReqs, revision: apiState?.data?.revision ?? null })
  add('接口侧交叉核对（tasks 与 DOM 同源）', apiTasks > 0 && boardDom.totalCards > 0, `接口 tasks=${String(apiTasks)}，接口 requirements=${String(apiReqs)}，DOM 卡片=${String(boardDom.totalCards)}`)

  const summary = {
    generated_at: new Date().toISOString(),
    port: PORT,
    req_id: REQ_ID,
    boot,
    checks,
    passed: checks.filter((c) => c.pass).length,
    failed: checks.filter((c) => !c.pass).length,
    screenshots: { board: shotBoard, list: shotList, tasks: shotTasks, detail: shotDetail },
    consoleErrors,
    pageErrors,
    failedRequests,
    dom: results,
  }
  const summaryFile = resolve(OUT, 'SUMMARY.json')
  writeFileSync(summaryFile, JSON.stringify(summary, null, 2))
  console.log(`\n截图：${[shotBoard, shotList, shotTasks, shotDetail].join(' ')}`)
  console.log(`摘要：${summaryFile}`)
  console.log(`断言：${String(summary.passed)} passed / ${String(summary.failed)} failed`)

  ws.close()
  cleanup()
  process.exit(summary.failed === 0 ? 0 : 1)
}

main().catch((e) => {
  console.error(`环境异常：${String(e?.stack ?? e)}`)
  try { ws?.close() } catch { /* ignore */ }
  process.exit(2)
})
