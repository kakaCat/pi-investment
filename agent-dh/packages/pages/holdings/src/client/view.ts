/**
 * Holdings board view — light broker-style monitor (design v2 page1).
 *
 * Rendering is data-only: buildView(data) -> innerHTML string; the board is a
 * read-only monitoring surface — every trading action stays with the agent.
 *
 * Class conventions: all classes prefixed dsh-hld- to stay clear of shell
 * styles. Stock display names prefer Chinese company names: resolved from the
 * rule contexts the watch centre already carries (e.g. "沪电股份(002463)"),
 * falling back to a small static dictionary, then the raw code.
 *
 * @module dashboard-holdings/client/view
 */
import type { Account, HoldingsData, Position, WatchRule } from './types.js'

/* ------------------------------------------------------------------ utils */
const esc = (s: unknown): string =>
  String(s ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m] ?? m))

const money = (v: number | undefined | null, frac = 2): string =>
  (Number.isFinite(Number(v)) ? Number(v) : 0).toLocaleString('zh-CN', { minimumFractionDigits: frac, maximumFractionDigits: frac })

const signNum = (v: number | undefined | null): string => {
  const n = Number(v) || 0
  return (n > 0 ? '+' : '') + n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

const pct = (v: number | undefined | null): string => {
  const n = Number(v) || 0
  return (n > 0 ? '+' : '') + n.toFixed(2) + '%'
}

/** 涨跌红/绿/灰 class（A股：红涨绿跌） */
const trend = (v: number | undefined | null): 'up' | 'down' | 'flat' => {
  const n = Number(v) || 0
  return n > 0.0001 ? 'up' : n < -0.0001 ? 'down' : 'flat'
}

const fmtClock = (ts?: string): string => {
  if (!ts) return '—'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return String(ts).slice(11, 19)
  const p = (n: number): string => String(n).padStart(2, '0')
  return p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
}

const ctxText = (rule: WatchRule): string => {
  const c = rule.context
  if (typeof c === 'string') return c
  try { return JSON.stringify(c ?? '') } catch { return '' }
}

/* ---------------- Chinese stock-name resolution ---------------- */
/** 常用标的静态字典（context 未携带中文名时兜底） */
const STOCK_NAMES: Record<string, string> = {
  '600519': '贵州茅台', '000858': '五粮液', '000568': '泸州老窖', '600809': '山西汾酒', '600600': '青岛啤酒',
  '601288': '农业银行', '601398': '工商银行', '601939': '建设银行', '601988': '中国银行', '600036': '招商银行',
  '000001': '平安银行', '600000': '浦发银行', '601166': '兴业银行', '600016': '民生银行', '601328': '交通银行',
  '601318': '中国平安', '601601': '中国太保', '601628': '中国人寿', '600030': '中信证券', '601688': '华泰证券',
  '600900': '长江电力', '601857': '中国石油', '600028': '中国石化', '601088': '中国神华', '600019': '宝钢股份',
  '600585': '海螺水泥', '601668': '中国建筑', '601390': '中国中铁', '601766': '中国中车', '600104': '上汽集团',
  '601633': '长城汽车', '601238': '广汽集团', '000333': '美的集团', '000651': '格力电器', '600690': '海尔智家',
  '300750': '宁德时代', '002594': '比亚迪', '601012': '隆基绿能', '600438': '通威股份', '002460': '赣锋锂业',
  '600276': '恒瑞医药', '603259': '药明康德', '000538': '云南白药', '300760': '迈瑞医疗',
  '002415': '海康威视', '000063': '中兴通讯', '002230': '科大讯飞', '002475': '立讯精密', '002241': '歌尔股份',
  '688981': '中芯国际', '688111': '金山办公', '603986': '兆易创新', '002049': '紫光国微', '300782': '卓胜微',
  '002371': '北方华创', '688012': '中微公司', '002463': '沪电股份', '002815': '崇达技术', '002050': '三花智控',
  '000807': '云铝股份', '601138': '工业富联', '002352': '顺丰控股', '601888': '中国中免', '000725': '京东方A',
  '002714': '牧原股份', '300498': '温氏股份', '601111': '中国国航', '600029': '南方航空', '600150': '中国船舶',
  '601989': '中国重工', '600893': '航发动力', '002179': '中航光电', '300059': '东方财富', '600031': '三一重工',
}

/** 从盯盘规则 context 提取「中文名 + 6位代码」对 */
function namesFromContexts(rules: WatchRule[]): Record<string, string> {
  const map: Record<string, string> = {}
  for (const rule of rules) {
    const ctx = ctxText(rule)
    // 形如：沪电股份(002463) / 云铝股份000807
    const re1 = /([\u4e00-\u9fa5]{2,10})\s*\(?0*(\d{6})\)?/g
    let m: RegExpExecArray | null
    while ((m = re1.exec(ctx)) !== null) map[m[2]] = m[1]
  }
  return map
}

/** 取证券中文展示名 */
function stockName(symbol: string | undefined, ctxNames: Record<string, string>): string {
  if (!symbol) return '—'
  const code = String(symbol).replace(/\D/g, '').slice(-6)
  return STOCK_NAMES[code] ?? ctxNames[code] ?? code
}

const pureCode = (symbol?: string): string => String(symbol ?? '').replace(/\D/g, '')

/** 生成 A 股风险档位对应的止损比例（宪法铁律） */
function stopRatioFor(code: string): number {
  return /^(30|68)/.test(code) ? -0.10 : -0.08 // 成长 -10% / 大盘蓝筹 -8%
}

/* ------------------------------------------------------------------ board */
export function buildView(data: HoldingsData, watchKey: string = 'current', historyPage = 0): string {
  const summary = (data.summary ?? {}) as HoldingsData['summary']
  const accounts: Account[] = Array.isArray(data.accounts) ? data.accounts : []
  const current = data.currentAccount ?? ''
  const positions: Position[] = Array.isArray(data.positions) ? data.positions : []
  const watchRules: WatchRule[] = Array.isArray(data.watchRules) ? data.watchRules : []
  const ctxNames = namesFromContexts(watchRules)

  // 账户维度（2026-09-04）：仅「本账户归属 + 通用观察(无归属)」参与展示与持仓盯盘标记；
  // 其余账户的规则不在当前账户视图出现（account 由后端 watch_rules.account 返回）
  const scopedRules = watchRules.filter((r) => {
    const a = r.account
    return a == null || a === '' || a === current
  })

  const accountSelect = accounts.length > 1
    ? `<div class="dsh-hld-acct">
         <label for="dsh-hld-account-switch">账户</label>
         <select id="dsh-hld-account-switch"
           onchange="window.__dshHldSwitchAccount && window.__dshHldSwitchAccount(this.value)">
           ${accounts.map((a) => `<option value="${esc(a.account_name)}" ${a.account_name === current ? 'selected' : ''}>${esc(a.display_name || a.account_name)}（${a.positions_count ?? 0} 仓）</option>`).join('')}
         </select>
       </div>`
    : ''

  const updated = summary.lastUpdated ? fmtClock(summary.lastUpdated) : '—'
  const todayPct = summary.totalValue ? (summary.dailyChange / (summary.totalValue - summary.dailyChange)) * 100 : 0

  return `<div class="dsh-hld-board">
  <div class="dsh-hld-topbar">
    <div class="dsh-hld-title">
      <h1>账户持仓看板</h1>
      <div class="sub">只读监控 · 交易操作由 agent 执行</div>
    </div>
    <div class="dsh-hld-tools">
      ${accountSelect}
      <div class="dsh-hld-updated">更新于 <b>${esc(updated)}</b></div>
      <button type="button" class="dsh-hld-refresh" onclick="window.__dshHldRefresh && window.__dshHldRefresh()">↻ 刷新</button>
    </div>
  </div>

  ${renderSummary(summary, todayPct, data)}

  ${renderPositions(positions, ctxNames, scopedRules)}

  ${renderTrades(data)}

  ${renderHistoryTrades(data, historyPage)}

  ${renderWatchRules(watchRules, ctxNames, current, accounts, watchKey)}
</div>`
}

/* ---------------------------------------------------------------- summary */
function renderSummary(summary: HoldingsData['summary'], todayPct: number, data: HoldingsData): string {
  const tToday = trend(summary.dailyChange)
  const tHeld = trend(summary.totalPnl)
  const cashRatio = Number(data.compliance?.cashRatio ?? (summary.totalValue ? (summary.cash / summary.totalValue) * 100 : 0))
  const maxStock = Number(data.compliance?.maxSingleStock ?? 0)
  const maxInd = Number(data.compliance?.maxIndustry ?? 0)
  const dd60 = Number(data.compliance?.maxDrawdown60d ?? 0)
  const nearStop = (data.positions ?? []).filter((p) => Number(p.profitLossPct) <= stopRatioFor(p.symbol) + 1).length

  const chip = (ok: boolean, text: string, warn = false): string =>
    `<span class="dsh-hld-chip ${ok ? 'ok' : warn ? 'warn' : 'bad'}">${text} ${ok ? '✅' : '⚠️'}</span>`

  return `<div class="dsh-hld-summary">
  <div class="dsh-hld-sum-top">
    <div class="dsh-hld-sum-pnl">
      <div class="n">今日盈亏</div>
      <div class="v ${tToday}">${signNum(summary.dailyChange)} <small>${pct(todayPct)}</small></div>
    </div>
    <div class="dsh-hld-sum-pnl right">
      <div class="n">持仓盈亏</div>
      <div class="v ${tHeld}">${signNum(summary.totalPnl)} <small>${pct(summary.totalPnlPct)}</small></div>
    </div>
  </div>
  <div class="dsh-hld-sum-assets">
    <div class="asset-item"><div class="n">总资产</div><div class="v">${money(summary.totalValue)}</div></div>
    <div class="asset-item"><div class="n"><span class="legend-dot" style="background:#f56c6c"></span>持仓市值（${summary.positions ?? 0} 只）</div><div class="v">${money(summary.totalMarketValue)}</div></div>
    <div class="asset-item"><div class="n"><span class="legend-dot" style="background:#e6a23c"></span>可用资金</div><div class="v">${money(summary.cash)}</div></div>
  </div>
  <div class="dsh-hld-risk">
    ${chip(cashRatio >= 10, '现金占比 ' + cashRatio.toFixed(1) + '% · 铁律 ≥10%')}
    ${chip(maxStock <= 20, '单股最大 ' + maxStock.toFixed(2) + '% · 上限 20%')}
    ${chip(maxInd <= 40, '单行业最大 ' + maxInd.toFixed(1) + '% · 上限 40%')}
    ${dd60 > 8 ? chip(false, '60日回撤 -' + dd60.toFixed(1) + '%（熔断线 -8%）', true) : chip(true, '60日回撤 ' + dd60.toFixed(1) + '%（熔断线 -8%）')}
    ${nearStop > 0 ? chip(false, nearStop + ' 只临近止损', true) : chip(true, '无临近止损')}
  </div>
</div>`
}

/* -------------------------------------------------------------- positions */
function renderPositions(positions: Position[], ctxNames: Record<string, string>, watchRules: WatchRule[]): string {
  const ruleCodes = new Set(watchRules.map((r) => pureCode(r.symbol)))
  const rows = positions.map((p) => renderPositionRow(p, ctxNames, ruleCodes)).join('')
  const empty = positions.length === 0
    ? `<tr><td colspan="7" class="dsh-hld-empty">当前账户暂无持仓 — 空仓等待信号是正确决策</td></tr>`
    : ''
  return `<div class="dsh-hld-card">
  <div class="hd"><span class="t">持仓明细（${positions.length}）</span><span class="more">买卖点参考 = 止损铁律 + 止盈参考(+10%) · 具体交易由 agent 执行</span></div>
  <div class="tblwrap"><table>
    <tr>
      <th>名称/代码</th><th class="r">市值/股数</th><th class="r">现价/成本</th>
      <th class="r">今日盈亏</th><th class="r">持仓盈亏</th><th>买卖点参考</th><th>盯盘</th>
    </tr>
    ${rows}${empty}
  </table></div>
</div>`
}

function renderPositionRow(p: Position, ctxNames: Record<string, string>, ruleCodes: Set<string>): string {
  const name = stockName(p.symbol, ctxNames)
  const code = pureCode(p.symbol)
  const stopRatio = stopRatioFor(code)
  const stop = (Number(p.avgCost) || 0) * (1 + stopRatio)
  const tp = (Number(p.avgCost) || 0) * 1.10
  const lossPct = Number(p.profitLossPct) || 0
  const nearStop = lossPct <= stopRatio + 1
  const gapPct = p.currentPrice ? (((Number(p.currentPrice) - stop) / Number(p.currentPrice)) * 100) : 0
  const hasRule = ruleCodes.has(code)

  const watchTag = nearStop
    ? `<span class="dsh-hld-tag trig">⚠️ 临近止损</span>`
    : hasRule
      ? `<span class="dsh-hld-tag on">已挂盯盘</span>`
      : `<span class="dsh-hld-tag off">—</span>`

  const bp = nearStop
    ? `<span class="dsh-hld-sl">⚠️ 临近止损 ${money(stop)}（${Math.abs(stopRatio * 100)}%）</span><br><span class="dsh-hld-s">反弹减 / 止盈参考 ${money(tp)}（+10%）</span>`
    : `<span class="dsh-hld-sl">止损 ${money(stop)}（-${Math.abs(stopRatio * 100)}% 档）</span><br><span class="dsh-hld-s">止盈参考 ${money(tp)}（+10%）</span>`

  return `<tr>
  <td><span class="sec-name">${esc(name)}</span> <span class="sec-code">${esc(code)}</span></td>
  <td class="r">${money(p.currentValue, 0)}<span class="sub">${p.quantity ?? 0} 股 · 可卖 ${p.sharesAvailable ?? 0}</span></td>
  <td class="r">${money(p.currentPrice)}<span class="sub">成本 ${money(p.avgCost)}</span></td>
  <td class="r ${trend(p.profitToday)}">${signNum(p.profitToday)}<span class="sub">今日</span></td>
  <td class="r ${trend(p.profitLoss)}">${signNum(p.profitLoss)}<span class="sub">${pct(p.profitLossPct)}</span></td>
  <td class="bp">
    ${bp}
    <span class="src">依据：成本 ${money(p.avgCost)} · 距止损线 +${Math.max(gapPct, 0).toFixed(1)}% · 铁律优先不补仓</span>
  </td>
  <td>${watchTag}</td>
</tr>`
}

/* ----------------------------------------------------------- today trades */
function renderTrades(data: HoldingsData): string {
  const trades = Array.isArray(data.todayTrades) ? data.todayTrades : []
  if (trades.length === 0) {
    return `<div class="dsh-hld-card">
      <div class="hd"><span class="t">今日自动交易（0）</span><span class="more">agent 的买卖动作都会显示在这里</span></div>
      <div class="dsh-hld-emptybox">今日尚无自动交易 — 没有信号时空仓等待是正确决策</div>
    </div>`
  }
  const zhAction: Record<string, { tag: string; text: string }> = {
    BUY: { tag: 'buy', text: '买入' },
    SELL: { tag: 'sell', text: '卖出' },
  }
  const zhStatus: Record<string, string> = { filled: '✅ 已成交', partial: '⏳ 部分成交', pending: '⏳ 待执行', rejected: '❌ 已拒绝', cancelled: '— 已撤单' }
  const ctxNames = namesFromContexts(data.watchRules ?? [])
  const rows = trades
    .map((t) => {
      const a = zhAction[String(t.action ?? '').toUpperCase()] ?? { tag: 'off', text: String(t.action ?? '') }
      const price = Number(t.filled_price) || Number(t.price)
      const amount = price * (t.shares ?? 0)
      const st = zhStatus[String(t.status ?? '')] ?? String(t.status ?? '')
      return `<tr>
        <td><span class="dsh-hld-tag ${a.tag}">${a.text}</span></td>
        <td><span class="sec-name">${esc(stockName(t.symbol, ctxNames))}</span> <span class="sec-code">${esc(pureCode(t.symbol))}</span></td>
        <td class="r">${money(price)}<span class="sub">× ${t.shares ?? 0} 股</span></td>
        <td class="r">${money(amount)}</td>
        <td>${esc(String(t.reason ?? '—').slice(0, 64))}</td>
        <td>${st}</td>
        <td class="dim">${esc(fmtClock(t.created_at))}</td>
      </tr>`
    })
    .join('')
  return `<div class="dsh-hld-card">
  <div class="hd"><span class="t">今日自动交易（${trades.length}）</span><span class="more">agent 已完成 / 进行中的自动交易</span></div>
  <div class="tblwrap"><table>
    <tr><th>方向</th><th>股票</th><th class="r">成交价</th><th class="r">金额</th><th>理由</th><th>状态</th><th>时间</th></tr>
    ${rows}
  </table></div>
</div>`
}

/* ---------------------------------------------------------- history trades */
/** 「历史交易」分页卡：全量成交（tradeHistory，倒序）按页切片展示，默认每页 8 条 */
export const HISTORY_PAGE_SIZE = 8

/** 生成分页数字（页数多时折叠为 1 … cur±1 … last） */
function pageNums(cur: number, pages: number, btn: (p: number, label: string, act: boolean) => string): string {
  if (pages <= 9) {
    let out = ''
    for (let i = 0; i < pages; i++) out += btn(i, String(i + 1), i === cur)
    return out
  }
  const set = new Set<number>([0, pages - 1, cur - 1, cur, cur + 1].filter((p) => p >= 0 && p < pages))
  const sorted = [...set].sort((a, b) => a - b)
  let out = ''
  let prev = -2
  for (const p of sorted) {
    if (p - prev > 1) out += '<span class="gap">…</span>'
    out += btn(p, String(p + 1), p === cur)
    prev = p
  }
  return out
}

function renderHistoryTrades(data: HoldingsData, page: number): string {
  // 时间口径说明：本卡数据按账户 = 当前账户（board API ?account= 已限定），与摘要/持仓同一 scope
  const all = Array.isArray(data.tradeHistory) ? data.tradeHistory : []
  const pageSize = HISTORY_PAGE_SIZE
  const pages = Math.max(1, Math.ceil(all.length / pageSize))
  const cur = Math.min(Math.max(0, Math.trunc(Number(page) || 0)), pages - 1)

  if (all.length === 0) {
    return `<div class="dsh-hld-card">
      <div class="hd"><span class="t">历史交易（0）</span><span class="more">${esc(String(data.currentAccount ?? ''))} · agent 成交后自动归档到此</span></div>
      <div class="dsh-hld-emptybox">该账户暂无历史交易记录</div>
    </div>`
  }

  const slice = all.slice(cur * pageSize, (cur + 1) * pageSize)
  const ctxNames = namesFromContexts(data.watchRules ?? [])
  const zhAction: Record<string, { tag: string; text: string }> = {
    BUY: { tag: 'buy', text: '买入' },
    SELL: { tag: 'sell', text: '卖出' },
  }
  const rows = slice
    .map((t) => {
      const act = String(t.action ?? '').toUpperCase()
      const a = zhAction[act] ?? { tag: 'off', text: String(t.action ?? '') }
      const price = Number(t.filled_price) || Number(t.price)
      const amount = Number(t.amount) || price * (t.shares ?? 0)
      // v2 成交行无 status 字段（全部为已成交明细）；盈亏仅 SELL 行带 realized_pnl（买入为 null → '—'）
      const pnl = Number(t.realized_pnl)
      const hasPnl = act === 'SELL' && Number.isFinite(pnl)
      const pnlCls = hasPnl && pnl !== 0 ? trend(pnl) : 'flat'
      const rate = Number(t.realized_pnl_rate)
      const rateSub = hasPnl && Number.isFinite(rate) && rate !== 0 ? '<span class="sub">' + pct(rate) + '</span>' : ''
      const reason = String(t.reason ?? '—')
      return `<tr>
        <td><span class="dsh-hld-tag ${a.tag}">${a.text}</span></td>
        <td><span class="sec-name">${esc(stockName(t.symbol, ctxNames))}</span> <span class="sec-code">${esc(pureCode(t.symbol))}</span></td>
        <td class="r">${money(price)}<span class="sub">× ${t.shares ?? 0} 股</span></td>
        <td class="r">${money(amount)}</td>
        <td class="r ${pnlCls}">${hasPnl ? signNum(pnl) + rateSub : '<span class=\"dim\">—</span>'}</td>
        <td title="${esc(reason)}">${esc(reason.slice(0, 60))}</td>
        <td class="dim">${esc(fmtClock(t.created_at))}</td>
      </tr>`
    })
    .join('')

  const btn = (p: number, label: string, act: boolean): string =>
    `<button type="button" class="dsh-hld-pgb${act ? ' act' : ''}"${p === cur ? ' aria-current="page"' : ''} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${p})">${label}</button>`
  const nav = pages <= 1
    ? ''
    : `<div class="dsh-hld-pg">
        <button type="button" class="dsh-hld-pgb"${cur === 0 ? ' disabled' : ''} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${cur - 1})">‹ 上一页</button>
        <span class="dsh-hld-pg-nums">${pageNums(cur, pages, btn)}</span>
        <button type="button" class="dsh-hld-pgb"${cur >= pages - 1 ? ' disabled' : ''} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${cur + 1})">下一页 ›</button>
        <span class="dsh-hld-pg-cnt">第 ${cur + 1}/${pages} 页 · 共 ${all.length} 笔</span>
      </div>`

  return `<div class="dsh-hld-card">
  <div class="hd"><span class="t">历史交易（${all.length}）</span><span class="more">${esc(String(data.currentAccount ?? ''))} · agent 全部成交明细 · 倒序</span></div>
  <div class="tblwrap"><table>
    <tr><th>方向</th><th>股票</th><th class="r">成交价</th><th class="r">金额</th><th class="r">实现盈亏</th><th>理由</th><th>时间</th></tr>
    ${rows}
  </table></div>
  ${nav}
</div>`
}

/* ------------------------------------------------------------ watch rules */
function renderWatchRules(watchRules: WatchRule[], ctxNames: Record<string, string>, currentAccount: string, accounts: Account[], watchKey: string): string {
  // 盯盘中心 = 账户归属 tab（pill 带计数）+ 列表（2026-09-05 · 对齐执行看板「调度任务 tab + 列表」）
  // 默认 tab = 本账户：当前账户归属 + 通用观察（account 为空/缺失，跨账户看板通用展示）；
  // 其余账户规则按账户 tab 查看；「全部」为全量并在归属列带徽标。
  const acctOf = (r: WatchRule): string => r.account ?? ''
  const all = watchRules
  const general = all.filter((r) => acctOf(r) === '')
  const curOwned = all.filter((r) => acctOf(r) === currentAccount)
  const curView = curOwned.concat(general)
  const otherAccts: string[] = []
  for (const r of all) {
    const a = acctOf(r)
    if (a !== '' && a !== currentAccount && !otherAccts.includes(a)) otherAccts.push(a)
  }
  const acctLabel = new Map<string, string>()
  for (const a of accounts) acctLabel.set(a.account_name, a.display_name || a.account_name)
  const disp = (name: string): string => acctLabel.get(name) ?? name

  // tab key 合法性：所选账户规则已被清空等场景回退「本账户」
  const valid = new Set<string>(['current', 'all', ...otherAccts])
  const act = valid.has(watchKey) ? watchKey : 'current'

  const list: WatchRule[] =
    act === 'all' ? all
      : act === 'current' ? curView
        : all.filter((r) => acctOf(r) === act)

  const tab = (key: string, label: string, count: number, tip: string): string =>
    `<button type="button" class="dsh-hld-wtab${act === key ? ' act' : ''}" data-wkey="${key}" title="${esc(tip)}" onclick="window.__dshHldWatchTab && window.__dshHldWatchTab('${key.replace(/'/g, '')}')">${esc(label)}<i class="c">${count}</i></button>`

  const tabs: string[] = [tab('current', '本账户', curView.length, `当前账户归属 + 通用观察（${disp(currentAccount)}）`)]
  for (const acct of otherAccts) tabs.push(tab(acct, disp(acct), all.filter((r) => acctOf(r) === acct).length, `归属账户：${acct}`))
  tabs.push(tab('all', '全部', all.length, '全部账户规则汇总'))

  const row = (r: WatchRule): string => {
    const ctx = ctxText(r)
    const brief = ctx.replace(/\s+/g, ' ').trim()
    const condTexts = (r.conditions ?? []).map(condChip).filter(Boolean)
    const condShow = condTexts.slice(0, 3).join(' <span class="dim">·</span> ') + (condTexts.length > 3 ? ' <span class="dim">+' + (condTexts.length - 3) + '</span>' : '')
    const kind = kindOf(ctx)
    const a = acctOf(r)
    const ownCls = a === '' ? 'off' : a === currentAccount ? 'on' : 'oth'
    const ownText = a === '' ? '通用观察' : a === currentAccount ? '本账户' : disp(a)
    return `<tr>
      <td><span class="sec-name">${esc(stockName(r.symbol, ctxNames))}</span> <span class="sec-code">${esc(pureCode(r.symbol))}</span></td>
      <td><span class="dsh-hld-tag ${kind.cls}">${kind.text}</span></td>
      <td class="cond">${condShow || '<span class="dim">—</span>'}</td>
      <td>${r.enabled ? '<span class="dsh-hld-tag on">监控中</span>' : '<span class="dsh-hld-tag off">已停用</span>'}</td>
      <td><span class="dsh-hld-tag ${ownCls}" title="${esc(a || '通用观察')}">${esc(ownText)}</span></td>
      <td class="ctx" title="${esc(brief.slice(0, 400))}">${esc(brief.slice(0, 44))}${brief.length > 44 ? '…' : ''}</td>
    </tr>`
  }

  const rows = list.map(row).join('')
  const emptyMsg = act === 'current'
    ? '本账户暂无归属/通用观察规则 — 开仓后 agent 会自动挂上止损/止盈盯盘；可切换上方其他账户 / 全部 tab'
    : act === 'all'
      ? '暂无任何盯盘规则'
      : '该账户暂无归属盯盘规则'
  const empty = list.length === 0 ? '<tr class="dsh-hld-empty"><td colspan="6">' + emptyMsg + '</td></tr>' : ''

  return `<div class="dsh-hld-card">
  <div class="hd"><span class="t">盯盘中心（${all.length}）</span><span class="more">账户归属 tab · 默认本账户（含通用观察）· 触发后由 agent 决策，无需人工盯盘</span></div>
  <div class="dsh-hld-wtabs">${tabs.join('')}</div>
  <div class="tblwrap"><table>
    <tr><th>股票</th><th>监控性质</th><th>触发条件</th><th>状态</th><th>归属账户</th><th>监控摘要</th></tr>
    ${rows}${empty}
  </table></div>
</div>`
}

/** 触发条件 → 短文本（支持新旧两种条件形状） */
function condChip(c: { type?: string; operator?: string; threshold?: number; field?: string; params?: { price?: number; direction?: string } }): string {
  const params = c.params as { price?: number; direction?: string } | undefined
  if (c.type === 'price_break' || String(c.operator || '').toLowerCase().includes('price')) {
    if (params && params.price !== undefined && params.price !== null) {
      const d = params.direction === 'above' ? '突破' : params.direction === 'below' ? '跌破' : '触碰'
      return `<span class="cond-${params.direction === 'above' ? 'up' : 'down'}">${d}${money(params.price)}</span>`
    }
    if (c.threshold !== undefined && c.threshold !== null) {
      return '价格 ' + c.threshold
    }
  }
  if (c.threshold !== undefined && c.threshold !== null && c.operator) {
    return String(c.operator || c.type).toUpperCase() + ' ' + c.threshold
  }
  return String(c.type ?? c.operator ?? '条件')
}

/** 从监控理由提取方向标签（止损 > 买入 > 卖出，避免误判） */
function kindOf(ctx: string): { cls: string; text: string } {
  if (/止损|风控|破位|减仓保护/.test(ctx)) return { cls: 'warn', text: '止损监控' }
  if (/买入|低吸|介入|加仓|建仓|补仓/.test(ctx)) return { cls: 'buy', text: '买入提醒' }
  if (/卖出|止盈|减仓|高抛|目标价/.test(ctx)) return { cls: 'sell', text: '卖出提醒' }
  return { cls: 'on', text: '常规监控' }
}
