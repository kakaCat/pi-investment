/**
 * 接口联调探针（REQ-260927202051-f6df · 卡 t-6df9a0「看板实测回归·联调」）。
 *
 * 联调对象 = **真实运行的 :13080 实例**上的 reqboard HTTP 面（I-12 看板/路由读方，已迁到队列），
 * 真值 = 磁盘上的**独立数据源**（`.dsh-data/dsh-reqboard.json` 台账 + 各需求 `docs/requirements/<REQ>/queue.json`），
 * 不是被测代码自己的内存快照 —— 这是「实际返回与预期一致」的可证伪口径（R-013：数据须标来源与时点）。
 *
 * 覆盖两类请求：
 *   A. 只读接口（看板首屏/甘特/阶段/详情/token 真正的数据源）：请求样例 → 期望（磁盘真值推导）→ 实测 → 逐字段比对；
 *   B. 写接口的**拒绝路径**（零副作用口径）：真实 POST 到 404/400 分支，比对状态码 + code + 文案，
 *      并以「台账 + 全部 queue.json 的 md5 前后不变」证明拒绝路径没有半写（不落盘、不建档）。
 *
 * 为什么写接口只打拒绝路径：本探针跑在生产实例上，成功路径会真改生产台账/队列。写成功路径的联调
 * 放在 in-process 用例 `packages/web/dsh-pmboard/tests/t16-http-queue-integration.test.ts`
 * （真实 handler + 真实台账/队列文件，临时工作区，活数据零接触）。
 *
 * 用法（cwd = agent-dh）：
 *   node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs \
 *     [--port 13080] [--workspace .] [--req REQ-260927202051-f6df]
 * 退出码：0 = 全部断言通过；1 = 有断言不通过；2 = 环境异常（凭据/连接/真值读不到）。
 */
import { createHash, createHmac } from 'node:crypto'
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const argv = process.argv.slice(2)
const argOf = (name, dflt) => {
  const i = argv.indexOf(name)
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : dflt
}
const PORT = Number(argOf('--port', '13080'))
const WORKSPACE = resolve(argOf('--workspace', '.'))
const TARGET_REQ = argOf('--req', 'REQ-260927202051-f6df')
const BASE = `http://127.0.0.1:${String(PORT)}`
const AUTHORITY = `127.0.0.1:${String(PORT)}`
const API = `${BASE}/dashboard/api/reqboard`
const CRED = join(WORKSPACE, '.dsh-data/.credentials.yaml')
const LEDGER_FILE = join(WORKSPACE, '.dsh-data/dsh-reqboard.json')
const REQUIREMENTS_DIR = join(WORKSPACE, 'docs/requirements')

// ── 断言收集 ──────────────────────────────────────────────────────────────
const checks = []
const add = (name, pass, detail) => {
  checks.push({ group, name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'}  [${group}] ${name} — ${detail}`)
}
let group = 'setup'
const setGroup = (g) => { group = g }

// ── 台账签发 cookie（与 route-probe.mjs 同源算法）───────────────────────────
function mintCookie() {
  const yaml = readFileSync(CRED, 'utf8')
  const m = yaml.match(/client-connection\/browser-session:[\s\S]*?secret:\s*([A-Za-z0-9_-]+)/)
  if (m === null) throw new Error(`credentials 里找不到 browser-session secret：${CRED}`)
  const decode = (v) => Buffer.from(v.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat((4 - (v.length % 4)) % 4), 'base64')
  const encode = (buf) => Buffer.from(buf).toString('base64').replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/u, '')
  const secret = decode(m[1])
  const issuedAt = Date.now()
  const expiresAt = issuedAt + 7 * 864e5
  const body = encode(Buffer.from(JSON.stringify({ version: 1, authority: AUTHORITY, issuedAt, expiresAt }), 'utf8'))
  const sig = encode(createHmac('sha256', secret).update(body).digest())
  const name = 'dsh-auth-' + encode(createHash('sha256').update(AUTHORITY).digest())
  return `${name}=v1.${body}.${sig}`
}

/** 结构化比较用的规范化 JSON（键序无关；与 QueueTaskStore.canonical 同口径）。 */
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value !== null && typeof value === 'object') {
    const o = value
    return `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`).join(',')}}`
  }
  return JSON.stringify(value) ?? 'undefined'
}

const stripLayer = (t) => {
  const c = structuredClone(t)
  delete c.layer
  return c
}

// ── 磁盘真值（独立数据源）────────────────────────────────────────────────
function loadTruth() {
  const ledger = JSON.parse(readFileSync(LEDGER_FILE, 'utf8'))
  const dirs = readdirSync(REQUIREMENTS_DIR, { withFileTypes: true })
    .filter((e) => e.isDirectory() && /^REQ-/.test(e.name))
    .map((e) => e.name)
    .sort()
  const queues = new Map()
  for (const id of dirs) {
    const p = join(REQUIREMENTS_DIR, id, 'queue.json')
    if (existsSync(p)) queues.set(id, JSON.parse(readFileSync(p, 'utf8')))
  }
  return { ledger, dirs, queues }
}

/** 与 listAll() 契约一致：需求 id 字典序分组 + 组内队列文件顺序，出口剥离 layer。 */
function expectedTaskSequence(queues, dirs) {
  const out = []
  const mismatch = []
  for (const id of dirs) {
    const q = queues.get(id)
    if (q === undefined) continue
    for (const t of q.tasks) {
      if (t.requirementId !== id) mismatch.push(`${t.id}: requirementId=${String(t.requirementId)} 而目录=${id}`)
      out.push(stripLayer(t))
    }
  }
  return { out, mismatch }
}

/** readyTasks(protocol.ts:1401) 契约的独立复算：status=todo 且依赖全为 done（悬空依赖不放行）。 */
function expectedReadyIds(tasks, requirementId) {
  const inReq = tasks.filter((t) => t.requirementId === requirementId)
  const doneIds = new Set(inReq.filter((t) => t.status === 'done').map((t) => t.id))
  return inReq.filter((t) => t.status === 'todo' && t.dependsOn.every((d) => doneIds.has(d))).map((t) => t.id)
}

/** 台账里某需求的计划任务键（requirement.md 常以计划键引用接收任务）。 */
const planKeysOf = (led, id) => led.requirements.find((r) => r.id === id)?.plan?.tasks ?? []

const md5 = (s) => createHash('md5').update(s).digest('hex')

/**
 * 阶段视图任务投影的契约校验（QueryStageDetail.toStageTaskRef :295 / toStageTaskExecution :309）。
 *
 * 投影是 `TaskRecord` 的**子集**（不是整条记录），故判据是：id 顺序一致 + 契约字段等值 +
 * 不出现契约外字段（`layer` 属于队列文件派生字段，出现在这里即出口未剥离）。
 * `cardDoc` 允许比源多（装配器会从 req.artifacts 的 task_detail 产物补），但源有值时须等值。
 */
const REF_REQUIRED = ['id', 'title', 'status', 'phase', 'side', 'dependsOn', 'acceptance']
const REF_OPTIONAL = ['dependsSummary', 'cardDoc', 'executorHint']
const REF_EXEC = ['claimedBy', 'executions']
function checkProjection(actualList, queueTasks, { withExecutions }) {
  const allowed = [...REF_REQUIRED, ...REF_OPTIONAL, ...(withExecutions ? REF_EXEC : [])]
  const byId = new Map(queueTasks.map((t) => [t.id, t]))
  const idDiff = firstDiff(queueTasks.map((t) => t.id), actualList.map((t) => t.id))
  if (idDiff !== null) return `id 序列不一致：${String(idDiff)}`
  for (const act of actualList) {
    const src = byId.get(act.id)
    if (src === undefined) return `${act.id} 不在队列任务集里`
    for (const k of Object.keys(act)) if (!allowed.includes(k)) return `${act.id} 出现契约外字段 ${k}（layer/多写字段即为出口污染）`
    for (const k of REF_REQUIRED) {
      const d = firstDiff(src[k], act[k])
      if (d !== null) return `${act.id}.${k} 不一致：${d}`
    }
    for (const k of REF_OPTIONAL) {
      const srcHas = Object.prototype.hasOwnProperty.call(src, k)
      if (k === 'cardDoc') { // 装配器可从 artifacts 补 cardDoc：允许实测多出，源有则须等值
        if (srcHas) { const d = firstDiff(src[k], act[k]); if (d !== null) return `${act.id}.cardDoc 不一致：${d}` }
        continue
      }
      const actHas = Object.prototype.hasOwnProperty.call(act, k)
      if (srcHas !== actHas) return `${act.id}.${k} 存在性不一致（队列 ${String(srcHas)} / 实测 ${String(actHas)}）`
      if (srcHas) { const d = firstDiff(src[k], act[k]); if (d !== null) return `${act.id}.${k} 不一致：${d}` }
    }
    if (withExecutions) {
      for (const k of REF_EXEC) {
        const srcHas = Object.prototype.hasOwnProperty.call(src, k)
        const actHas = Object.prototype.hasOwnProperty.call(act, k)
        if (k === 'executions' ? !actHas : srcHas !== actHas) return `${act.id}.${k} 存在性不一致`
        const d = firstDiff(src[k], act[k])
        if (d !== null) return `${act.id}.${k} 不一致：${d}`
      }
    }
  }
  return null
}

/** 单个 queue.json 的 md5（队列文件是任务读方的唯一数据源）。 */
function queueFileMd5(id) {
  const file = join(REQUIREMENTS_DIR, id, 'queue.json')
  return existsSync(file) ? md5(readFileSync(file)) : 'MISSING'
}

/** 逐文件队列指纹（附逐文件明细，便于定位并发写入是哪一个需求）。 */
function queueFingerprint(queues) {
  const per = {}
  for (const id of [...queues.keys()].sort()) per[id] = queueFileMd5(id)
  return { overall: md5(JSON.stringify(per)), per }
}

/** 台账文件 md5（仅信息性：台账会被并发窗口与产物自动发现写入）。 */
const ledgerMd5 = () => md5(readFileSync(LEDGER_FILE))

// ── HTTP ─────────────────────────────────────────────────────────────────
let COOKIE = ''
async function get(sub) {
  const res = await fetch(`${API}/${sub}`, { headers: { cookie: COOKIE } })
  const text = await res.text()
  let json = null
  try { json = JSON.parse(text) } catch { /* 非 JSON 原样留证 */ }
  return { status: res.status, json, text }
}
async function post(sub, body) {
  const res = await fetch(`${API}/${sub}`, {
    method: 'POST',
    headers: { cookie: COOKIE, 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  const text = await res.text()
  let json = null
  try { json = JSON.parse(text) } catch { /* 同上 */ }
  return { status: res.status, json, text }
}

const firstDiff = (a, b) => {
  const A = canonical(a)
  const B = canonical(b)
  if (A === B) return null
  const n = Math.min(A.length, B.length)
  let i = 0
  while (i < n && A[i] === B[i]) i += 1
  return `期望@${i}:…${A.slice(Math.max(0, i - 40), i + 60)}… / 实测@${i}:…${B.slice(Math.max(0, i - 40), i + 60)}…`
}

// ── 主流程 ────────────────────────────────────────────────────────────────
async function main() {
  COOKIE = mintCookie()
  const { ledger, dirs, queues } = loadTruth()
  const { out: expectedTasks, mismatch } = expectedTaskSequence(queues, dirs)
  const fpStart = queueFingerprint(queues)
  const revStart = ledger.revision

  setGroup('truth')
  add('磁盘真值可读（台账 + 队列文件）', ledger.schemaVersion === 9 && !('tasks' in ledger) && queues.size > 0,
    `台账 schemaVersion=${String(ledger.schemaVersion)} 有 tasks 键=${String('tasks' in ledger)} requirements=${String(ledger.requirements.length)} queue.json=${String(queues.size)} tasks=${String(expectedTasks.length)}`)
  add('队列 requirementId 与目录一一对应（无串档）', mismatch.length === 0,
    mismatch.length === 0 ? `全部 ${String(expectedTasks.length)} 条一致` : mismatch.slice(0, 3).join(' | '))

  // ── A1. GET /state（看板首屏 + 甘特主数据源）──────────────────────────
  setGroup('A1 /state')
  const state = await get('state')
  const data = state.json?.data ?? {}
  add('请求样例 GET /dashboard/api/reqboard/state → 200 且信封 {success:true}', state.status === 200 && state.json?.success === true,
    `HTTP=${String(state.status)} success=${String(state.json?.success)}`)

  const reqIdsApi = Array.isArray(data.requirements) ? data.requirements.map((r) => r.id) : []
  const reqIdsDisk = ledger.requirements.map((r) => r.id)
  add('requirements 与台账逐项一致（数量+顺序）', canonical(reqIdsApi) === canonical(reqIdsDisk),
    `HTTP=${String(reqIdsApi.length)} 台账=${String(reqIdsDisk.length)}${firstDiff(reqIdsDisk, reqIdsApi) !== null ? ' | ' + firstDiff(reqIdsDisk, reqIdsApi) : ''}`)

  const tasksApi = Array.isArray(data.tasks) ? data.tasks : []
  add('tasks 数量 = Σ 各 queue.json 任务数', tasksApi.length === expectedTasks.length,
    `HTTP=${String(tasksApi.length)} 磁盘=${String(expectedTasks.length)}`)
  add('tasks 顺序 = 需求字典序分组 + 组内队列顺序（listAll 契约）',
    canonical(tasksApi.map((t) => t.id)) === canonical(expectedTasks.map((t) => t.id)),
    firstDiff(expectedTasks.map((t) => t.id), tasksApi.map((t) => t.id)) ?? `id 序列逐项相同（${String(tasksApi.length)} 条）`)
  const layerLeak = tasksApi.filter((t) => Object.prototype.hasOwnProperty.call(t, 'layer'))
  add('出口剥离派生字段 layer（TaskStore D3 契约）', layerLeak.length === 0,
    layerLeak.length === 0 ? '0 条带 layer' : `${String(layerLeak.length)} 条带 layer，例：${layerLeak[0].id}`)

  const apiById = new Map(tasksApi.map((t) => [t.id, t]))
  let taskDiff = null
  let taskDiffCount = 0
  for (const exp of expectedTasks) {
    const act = apiById.get(exp.id)
    const d = act === undefined ? `期望任务 ${exp.id} 在实测响应中缺失` : firstDiff(exp, act)
    if (d !== null) { taskDiffCount += 1; taskDiff ??= `${exp.id}: ${d}` }
  }
  add('逐任务逐字段与队列文件一致（去 layer 后键集+值全等）', taskDiffCount === 0,
    taskDiffCount === 0 ? `${String(expectedTasks.length)} 条逐字段一致` : `${String(taskDiffCount)} 条不一致；首例 ${String(taskDiff)}`)

  const readyApi = data.ready ?? {}
  const readyKeysOk = canonical(Object.keys(readyApi)) === canonical(reqIdsDisk)
  add('ready 映射键 = 台账全部需求（顺序一致）', readyKeysOk,
    readyKeysOk ? `${String(Object.keys(readyApi).length)} 个键` : firstDiff(reqIdsDisk, Object.keys(readyApi)))
  let readyBad = null
  for (const id of dirs) {
    if (!queues.has(id)) continue
    const expReady = expectedReadyIds(expectedTasks, id)
    const actReady = readyApi[id] ?? []
    const d = firstDiff(expReady, actReady)
    if (d !== null) { readyBad ??= `${id}: ${d}` }
  }
  add('需求内 ready = status:todo 且依赖全 done（顺序=任务数组顺序）', readyBad === null,
    readyBad === null ? `抽查 ${String(queues.size)} 个有队列需求全部一致` : String(readyBad))

  // ── A2. GET /requirements/summary ────────────────────────────────────
  setGroup('A2 /requirements/summary')
  const summary = await get('requirements/summary')
  const rows = summary.json?.data?.requirements ?? summary.json?.data ?? []
  add('请求样例 GET /requirements/summary → 200', summary.status === 200 && summary.json?.success === true,
    `HTTP=${String(summary.status)} rows=${String(Array.isArray(rows) ? rows.length : -1)}`)
  const rowById = new Map((Array.isArray(rows) ? rows : []).map((r) => [r.id, r]))
  const targetRow = rowById.get(TARGET_REQ)
  const targetQueue = queues.get(TARGET_REQ)
  const targetDone = targetQueue === undefined ? -1 : targetQueue.tasks.filter((t) => t.status === 'done').length
  add('本需求摘要计数 = 队列真值（tasksTotal/tasksDone）',
    targetRow !== undefined && targetQueue !== undefined
    && targetRow.tasksTotal === targetQueue.tasks.length && targetRow.tasksDone === targetDone,
    targetRow === undefined ? '响应中无本需求行'
      : `${TARGET_REQ} tasksTotal=${String(targetRow.tasksTotal)}/${String(targetQueue?.tasks.length)} tasksDone=${String(targetRow.tasksDone)}/${String(targetDone)}`)

  // ── A3. GET /requirements/:id/stages（全流程一览）────────────────────
  setGroup('A3 /requirements/:id/stages')
  const stages = await get(`requirements/${TARGET_REQ}/stages`)
  const stagesData = stages.json?.data
  add('请求样例 GET /requirements/<REQ>/stages → 200', stages.status === 200 && stages.json?.success === true,
    `HTTP=${String(stages.status)} currentStage=${String(stagesData?.currentStage)} stages=${String(stagesData?.stages?.length)}`)
  const deco = stagesData?.stages?.find((s) => s.stage === 'decomposing')
  const impl = stagesData?.stages?.find((s) => s.stage === 'implementing')
  // StageDetail 是判别联合：节点任务是 `body.tasks`（不在节点顶层）。
  const decoTasks = deco?.body?.tasks ?? []
  const decoBad = checkProjection(decoTasks, targetQueue?.tasks ?? [], { withExecutions: false })
  add('拆分节点任务投影 = 队列任务（29 条：id 顺序 + 契约字段 + 无契约外键）', decoBad === null,
    decoBad ?? `${String(decoTasks.length)} 条投影逐字段一致（StageTaskRef 契约）`)
  const implTasks = impl?.body?.tasks ?? []
  const implBad = checkProjection(implTasks, targetQueue?.tasks ?? [], { withExecutions: true })
  add('实施节点任务投影 = 队列任务（含 executions）', implBad === null,
    implBad ?? `${String(implTasks.length)} 条投影逐字段一致（StageTaskExecution 契约）`)
  const stageLayerLeak = JSON.stringify(stagesData ?? {}).includes('"layer"')
  add('阶段视图响应无 layer 派生字段泄漏', !stageLayerLeak, stageLayerLeak ? '响应文本含 "layer"' : '响应文本不含 "layer"')

  // ── A4. GET /requirements/:id/stage/implementing（节点详情）───────────
  setGroup('A4 /requirements/:id/stage/:stage')
  const detail = await get(`requirements/${TARGET_REQ}/stage/implementing`)
  const detailTasks = detail.json?.data?.body?.tasks ?? []
  const detailBad = checkProjection(detailTasks, targetQueue?.tasks ?? [], { withExecutions: true })
  add('请求样例 GET /requirements/<REQ>/stage/implementing → 200 且任务投影 = 队列任务',
    detail.status === 200 && detail.json?.success === true && detailBad === null && detailTasks.length > 0,
    `HTTP=${String(detail.status)} tasks=${String(detailTasks.length)} ${detailBad ?? '逐字段一致'}`)
  const badStage = await get(`requirements/${TARGET_REQ}/stage/not-a-stage`)
  add('非法 stage → 400 invalid_input', badStage.status === 400 && badStage.json?.code === 'invalid_input',
    `HTTP=${String(badStage.status)} code=${String(badStage.json?.code)}`)

  // ── A5. GET /requirements/:id/token & /marks ─────────────────────────
  setGroup('A5 token / marks')
  const token = await get(`requirements/${TARGET_REQ}/token`)
  const tokenData = token.json?.data
  add('请求样例 GET /requirements/<REQ>/token → 200 且 byStage = 全节点',
    token.status === 200 && token.json?.success === true && Array.isArray(tokenData?.byStage) && tokenData.byStage.length > 0,
    `HTTP=${String(token.status)} byStage=${String(tokenData?.byStage?.length)} totals=${canonical(tokenData?.totals)}`)
  const marks = await get(`requirements/${TARGET_REQ}/marks`)
  const marksData = marks.json?.data
  const queueTaskIds = new Set((targetQueue?.tasks ?? []).map((t) => t.id))
  const planKeys = new Set(planKeysOf(ledger, TARGET_REQ).map((t) => t.key))
  const marksBy = [...new Set((marksData?.clauses ?? []).flatMap((c) => c.by ?? []))]
  // 本需求的 requirement.md 用**计划键**（t1..t16）引用接收任务，解析不到台账 id 时按契约保留原文
  // （content-trace.ts:272-289：宁可不标红）——故合法值域 = 队列任务 id ∪ 计划键。
  const marksForeign = marksBy.filter((id) => !queueTaskIds.has(id) && !planKeys.has(id))
  add('请求样例 GET /requirements/<REQ>/marks → 200 且接收标记值域可追溯（队列 id ∪ 计划键）',
    marks.status === 200 && marks.json?.success === true && marksData?.available === true
    && (marksData?.clauses?.length ?? 0) > 0 && marksForeign.length === 0,
    `HTTP=${String(marks.status)} clauses=${String(marksData?.clauses?.length ?? 'n/a')} unreceived=${String(marksData?.unreceived?.length ?? 'n/a')} 越界值=${String(marksForeign.length)}${marksForeign.length > 0 ? ' 例：' + marksForeign.slice(0, 3).join(',') : ''}`)

  // 全量抽扫：marks 的 by 若解析成**真实任务 id**，必须命中该需求 queue.json（证明读方确实从队列出数）
  let scanChecked = 0
  let scanRealIdReqs = 0
  let scanForeign = []
  for (const id of dirs) {
    if (!queues.has(id)) continue
    const m = await get(`requirements/${id}/marks`)
    if (m.status !== 200) continue
    scanChecked += 1
    const ids = new Set(queues.get(id).tasks.map((t) => t.id))
    const real = [...new Set((m.json?.data?.clauses ?? []).flatMap((c) => c.by ?? []))].filter((x) => /^t-[0-9a-z]{6}$/.test(x))
    if (real.length > 0) scanRealIdReqs += 1
    for (const x of real) if (!ids.has(x)) scanForeign.push(`${id}:${x}`)
  }
  add('marks 抽扫：解析出的真实任务 id 全部命中队列文件（读方确从队列出数）',
    scanChecked > 0 && scanRealIdReqs > 0 && scanForeign.length === 0,
    `扫描 ${String(scanChecked)} 个有队列需求；含真实 id 解析的 ${String(scanRealIdReqs)} 个；未命中 ${String(scanForeign.length)}${scanForeign.length > 0 ? ' 例：' + scanForeign.slice(0, 3).join(',') : ''}`)
  const marks404 = await get('requirements/REQ-does-not-exist-000000/marks')
  add('不存在需求 → 404 not_found', marks404.status === 404 && marks404.json?.code === 'not_found',
    `HTTP=${String(marks404.status)} code=${String(marks404.json?.code)}`)

  // ── A6. GET /session/:sid/progress ───────────────────────────────────
  setGroup('A6 /session/:sid/progress')
  const targetReqRec = ledger.requirements.find((r) => r.id === TARGET_REQ)
  const sidCandidates = [
    targetReqRec?.sourceSessionId,
    ...(targetQueue?.tasks ?? []).flatMap((t) => (t.executions ?? []).map((e) => e.sessionId)),
  ].filter((s) => typeof s === 'string' && s.length > 0)
  const sid = sidCandidates[0]
  if (sid === undefined) {
    add('会话进度接口（需真实 sessionId）', false, '台账与队列里找不到可用 sessionId（无样本，不算通过）')
  } else {
    const OPEN = ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting']
    const anchored = ledger.requirements.filter((r) => r.sourceSessionId === sid
      || (queues.get(r.id)?.tasks ?? []).some((t) => (t.executions ?? []).some((e) => e.sessionId === sid)))
    const byRecent = (a, b) => b.updatedAt - a.updatedAt
    const picked = anchored.filter((r) => OPEN.includes(r.status)).sort(byRecent)[0] ?? anchored.slice().sort(byRecent)[0]
    const prog = await get(`session/${encodeURIComponent(sid)}/progress`)
    const p = prog.json?.data
    const expTasks = queues.get(picked?.id ?? '')?.tasks ?? []
    const expDone = expTasks.filter((t) => t.status === 'done').length
    add('请求样例 GET /session/<sid>/progress → 200 且 progress 计数 = 队列真值',
      prog.status === 200 && p?.hasRequirement === true && picked !== undefined
      && p.requirement?.id === picked.id && p.progress?.total === expTasks.length && p.progress?.done === expDone,
      `HTTP=${String(prog.status)} sid=${sid} target=${String(p?.requirement?.id)} total=${String(p?.progress?.total)}/${String(expTasks.length)} done=${String(p?.progress?.done)}/${String(expDone)}`)
  }

  // ── A7. 未知路由 / health ────────────────────────────────────────────
  setGroup('A7 路由契约')
  const health = await get('health')
  add('GET /health → 200 {status:ok}', health.status === 200 && health.json?.data?.status === 'ok',
    `HTTP=${String(health.status)} body=${health.text.slice(0, 80)}`)
  const unknown = await get('definitely-not-a-route')
  add('未知路由 → 404 {success:false, code:not_found}', unknown.status === 404 && unknown.json?.success === false && unknown.json?.code === 'not_found',
    `HTTP=${String(unknown.status)} body=${unknown.text.slice(0, 120)}`)

  // ── B. 写接口拒绝路径 + 零副作用 ──────────────────────────────────────
  setGroup('B 写接口契约（零副作用）')
  // 只读阶段收尾口径：读方**不写队列**（queue.json 指纹不变）。台账 revision 可能因
  // `/state` 的产物自动发现（syncAllReqArtifacts）而变，那是既有行为，单独记录不入断言。
  const fpAfterReads = queueFingerprint(queues)
  add('只读阶段零写队列：全部 queue.json 指纹前后一致', fpStart.overall === fpAfterReads.overall,
    fpStart.overall === fpAfterReads.overall
      ? `before=after=${fpStart.overall}（${String(Object.keys(fpStart.per).length)} 个队列文件）`
      : `before=${fpStart.overall} after=${fpAfterReads.overall}；变化文件=${Object.keys(fpStart.per).filter((id) => fpStart.per[id] !== fpAfterReads.per[id]).join(',')}`)
  const ledgerMd5AfterReads = ledgerMd5()
  const revAfterReads = JSON.parse(readFileSync(LEDGER_FILE, 'utf8')).revision
  const fpBefore = fpAfterReads.overall
  const dirsBefore = dirs.length
  const doneTask = expectedTasks.find((t) => t.status === 'done')

  const w1 = await post('task/move', { id: 't-deadbeef0001', to: 'done' })
  add('POST /task/move 不存在 id → 404 not_found', w1.status === 404 && w1.json?.code === 'not_found',
    `HTTP=${String(w1.status)} body=${w1.text.slice(0, 100)}`)

  const w2 = await post('task/move', { to: 'done' })
  add('POST /task/move 缺 id → 404 not_found（不误判为成功）', w2.status === 404 && w2.json?.code === 'not_found',
    `HTTP=${String(w2.status)} body=${w2.text.slice(0, 100)}`)

  const w3 = doneTask === undefined
    ? { status: -1, json: null, text: '无 done 任务，样本缺失' }
    : await post('task/move', { id: doneTask.id, to: 'todo', actor: 'human' })
  add('POST /task/move 非法流转（done→todo）→ 400 invalid_transition', w3.status === 400 && w3.json?.code === 'invalid_transition',
    `HTTP=${String(w3.status)} id=${String(doneTask?.id)} body=${String(w3.text).slice(0, 140)}`)

  const w4 = await post('task/move', { id: 't-deadbeef0001', to: '不存在的状态' })
  add('POST /task/move 非法 to → 400 invalid_input', w4.status === 400 && w4.json?.code === 'invalid_input',
    `HTTP=${String(w4.status)} body=${w4.text.slice(0, 100)}`)

  const w5 = await post('task/update', { id: 't-deadbeef0001', acceptance: '联调探针（不应落盘）' })
  add('POST /task/update 不存在 id → 404 not_found', w5.status === 404 && w5.json?.code === 'not_found',
    `HTTP=${String(w5.status)} body=${w5.text.slice(0, 100)}`)

  const w6 = await post('task/create', { requirementId: 'REQ-does-not-exist-000000', title: '联调探针（不应建档）', phase: 'implement', side: 'backend' })
  add('POST /task/create 需求不存在 → 404 not_found（不隐式建档）', w6.status === 404 && w6.json?.code === 'not_found',
    `HTTP=${String(w6.status)} body=${w6.text.slice(0, 120)}`)

  const w7 = await post('comment', { requirementId: 'REQ-does-not-exist-000000', body: '联调探针（不应落盘）' })
  add('POST /comment 目标不存在 → 4xx（不静默成功）', w7.status >= 400 && w7.json?.success === false,
    `HTTP=${String(w7.status)} code=${String(w7.json?.code)} body=${w7.text.slice(0, 100)}`)

  // 人工闸门（HUMAN_ONLY_TASK_TRANSITIONS）：done 卡的重开/取消、canceled 卡的复活 = 仅人可操作，
  // agent/system 一律 403 human_gate 且**不改任何字段**（拒绝路径零副作用）。
  const w8 = doneTask === undefined
    ? { status: -1, json: null, text: '无 done 任务，样本缺失' }
    : await post('task/move', { id: doneTask.id, to: 'in_progress', actor: 'agent' })
  add('POST /task/move done→in_progress（actor=agent）→ 403 human_gate（人工闸门）',
    w8.status === 403 && w8.json?.code === 'human_gate',
    `HTTP=${String(w8.status)} id=${String(doneTask?.id)} body=${String(w8.text).slice(0, 140)}`)

  const canceledTask = expectedTasks.find((t) => t.status === 'canceled')
  if (canceledTask === undefined) {
    // 无样本不冒充通过：显式 INFO（同一 human_gate 断言族已由 done→in_progress 覆盖）
    console.log('INFO  无 canceled 任务样本：canceled→todo 的人工闸门分支本次未验证（本次全部 616 条队列任务里 status=canceled 为 0 条）')
  } else {
    const w9 = await post('task/move', { id: canceledTask.id, to: 'todo', actor: 'system' })
    add('POST /task/move canceled→todo（actor=system）→ 403 human_gate（复活仅人）',
      w9.status === 403 && w9.json?.code === 'human_gate',
      `HTTP=${String(w9.status)} id=${canceledTask.id} body=${w9.text.slice(0, 140)}`)
  }

  const { queues: queuesAfter } = loadTruth()
  const fpAfter = queueFingerprint(queuesAfter)
  const dirsAfter = readdirSync(REQUIREMENTS_DIR, { withFileTypes: true }).filter((e) => e.isDirectory() && /^REQ-/.test(e.name)).length
  add('拒绝路径零副作用：全部 queue.json 指纹不变',
    fpBefore === fpAfter.overall,
    fpBefore === fpAfter.overall
      ? `before=after=${fpBefore}`
      : `before=${fpBefore} after=${fpAfter.overall}；变化文件=${Object.keys(fpAfterReads.per).filter((id) => fpAfterReads.per[id] !== fpAfter.per[id]).join(',')}`)
  add('拒绝路径零副作用：需求目录数不变（未隐式建档）', dirsBefore === dirsAfter,
    `before=${String(dirsBefore)} after=${String(dirsAfter)}`)
  const ledgerMd5After = ledgerMd5()
  const revAfter = JSON.parse(readFileSync(LEDGER_FILE, 'utf8')).revision
  console.log(`INFO  台账 md5 只读阶段 ${ledgerMd5AfterReads} → 拒绝路径后 ${ledgerMd5After}（rev ${String(revAfterReads)} → ${String(revAfter)}）；台账会被并发窗口与 /state 的产物自动发现写入，故零写判据只取 queue.json 与目录数`)

  // ── 汇总 ─────────────────────────────────────────────────────────────
  const failed = checks.filter((c) => !c.pass)
  console.log(`\n断言：${String(checks.length - failed.length)} passed / ${String(failed.length)} failed`)
  const report = {
    generated_at: new Date().toISOString(),
    card: 't-6df9a0（看板实测回归·联调）',
    requirement: TARGET_REQ,
    target: { base: BASE, workspace: WORKSPACE, port: PORT },
    truth: {
      ledger_schemaVersion: ledger.schemaVersion,
      ledger_has_tasks: 'tasks' in ledger,
      requirements: ledger.requirements.length,
      queue_files: queues.size,
      queue_tasks: expectedTasks.length,
      queue_total: queues.get(TARGET_REQ)?.tasks.length ?? 0,
      ledger_revision_before_reads: revStart,
      ledger_revision_after_reads: revAfterReads,
      ledger_revision_after_rejects: revAfter,
      queue_fingerprint_before_reads: fpStart.overall,
      queue_fingerprint_after_reads: fpAfterReads.overall,
      queue_fingerprint_after_rejects: fpAfter.overall,
      queue_file_md5: fpAfter.per,
    },
    passed: checks.length - failed.length,
    failed: failed.length,
    checks,
  }
  const out = join(WORKSPACE, 'docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-summary.json')
  writeFileSync(out, JSON.stringify(report, null, 2))
  console.log(`结构化证据：${out}`)
  process.exit(failed.length === 0 ? 0 : 1)
}

main().catch((e) => {
  console.error(`环境异常：${String(e?.stack ?? e)}`)
  process.exit(2)
})
