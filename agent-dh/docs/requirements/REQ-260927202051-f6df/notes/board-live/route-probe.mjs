/**
 * 页面可达性探针（验收①的可复现口径）。
 *
 * 为什么单独写它：验收① 原口径是 `curl -s localhost:13080/dashboard | grep -c pmboard`，
 * 但 dsh web 的 shell 只挂在 **`/`**（`/dashboard` 是**客户端 hash 路由**，服务端返回 404），
 * 且整站受 dsh-auth cookie 保护（无 cookie 一律 401）。照原样敲命令必然得 0，那不是看板回归。
 *
 * 本探针把「可达」钉成可复核的三条：
 *   1. `GET /`（带 dsh-auth cookie）→ 200，且 HTML 里 `pmboard` 出现次数 ≥1（client 半被注入）；
 *   2. `GET /dashboard/api/reqboard/state` → 200，requirements/tasks 计数非 0（读方真的在出数）；
 *   3. 无 cookie 时 `/` → 401（证明 404/401 是鉴权与路由形态，不是页面坏了）。
 *
 * cookie 算法与 `scripts/cdp-board-check.mjs` / dsh-client-connection 同源（secret 取自凭据库）。
 *
 * 用法（cwd = agent-dh）：
 *   node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs [--port 13080]
 * 退出码：0 = 三条都成立；1 = 有断言不成立；2 = 环境异常（凭据读不到 / 连接失败）。
 */
import { createHash, createHmac } from 'node:crypto'
import { readFileSync } from 'node:fs'

const argv = process.argv.slice(2)
const argOf = (name, dflt) => {
  const i = argv.indexOf(name)
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : dflt
}
const PORT = Number(argOf('--port', '13080'))
const BASE = `http://127.0.0.1:${String(PORT)}`
const AUTHORITY = `127.0.0.1:${String(PORT)}`
const CRED = argOf('--credentials', '.dsh-data/.credentials.yaml')

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
  return `${name}=v1.${body}.${sig}`
}

const checks = []
const add = (name, pass, detail) => {
  checks.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name} — ${detail}`)
}

async function main() {
  const cookie = mintCookie()

  const authed = await fetch(`${BASE}/`, { headers: { cookie } })
  const html = await authed.text()
  const hits = (html.match(/pmboard/g) ?? []).length
  add('GET / （带 dsh-auth cookie）→ 200 且 shell 含 pmboard', authed.status === 200 && hits >= 1, `HTTP=${String(authed.status)} bytes=${String(html.length)} pmboard=${String(hits)}`)

  const anon = await fetch(`${BASE}/`)
  add('GET / （无 cookie）→ 401（鉴权在位）', anon.status === 401, `HTTP=${String(anon.status)}`)

  const legacy = await fetch(`${BASE}/dashboard`, { headers: { cookie } })
  add('GET /dashboard 记录为客户端 hash 路由（服务端 404，非回归）', legacy.status === 404, `HTTP=${String(legacy.status)} bytes=${String((await legacy.text()).length)}`)

  const state = await fetch(`${BASE}/dashboard/api/reqboard/state`, { headers: { cookie } })
  const body = await state.json().catch(() => null)
  const reqs = Array.isArray(body?.data?.requirements) ? body.data.requirements.length : -1
  const tasks = Array.isArray(body?.data?.tasks) ? body.data.tasks.length : -1
  add('GET /dashboard/api/reqboard/state → 200 且出数', state.status === 200 && reqs > 0 && tasks > 0, `HTTP=${String(state.status)} requirements=${String(reqs)} tasks=${String(tasks)} rev=${String(body?.data?.revision ?? null)}`)

  const failed = checks.filter((c) => !c.pass).length
  console.log(`\n断言：${String(checks.length - failed)} passed / ${String(failed)} failed`)
  process.exit(failed === 0 ? 0 : 1)
}

main().catch((e) => {
  console.error(`环境异常：${String(e?.stack ?? e)}`)
  process.exit(2)
})
