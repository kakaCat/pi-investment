/**
 * Holdings board view builder — renders all sections.
 * Pure functions: buildView takes data and returns HTML string.
 *
 * @module dashboard-holdings/client/view
 */
import type { HoldingsData, Position, Trade, WatchRule } from './types.js'

export function buildView(data: HoldingsData): string {
  const now = new Date().toLocaleString('zh-CN', { hour12: false })

  return `
    <div class="dsh-hld-board">
      <div class="dsh-hld-wrap">
        <div class="dsh-hld-head">
          <h1 class="dsh-hld-title">持仓看板 <small>账户: ${escapeHtml(data.currentAccount)}</small></h1>
          <div class="dsh-hld-meta">
            <span>更新时间: ${now}</span>
            <button class="dsh-hld-refresh" onclick="window.__dshHldRefresh?.()">刷新</button>
          </div>
        </div>

        ${renderAccountSwitch(data)}
        ${renderSummary(data)}
        ${renderCompliance(data)}
        ${renderPositions(data)}
        ${renderTodayTrades(data)}
        ${renderWatchRules(data)}
      </div>
    </div>
  `
}

function renderAccountSwitch(data: HoldingsData): string {
  if (data.accounts.length <= 1) return ''

  const buttons = data.accounts.map(acc => {
    const active = acc.account_name === data.currentAccount ? 'active' : ''
    return `
      <button class="dsh-hld-account-btn ${active}"
              onclick="window.__dshHldSwitchAccount?.('${acc.account_name}')">
        ${escapeHtml(acc.display_name || acc.account_name)}
        <small>(${acc.positions_count}持仓)</small>
      </button>
    `
  }).join('')

  return `
    <div class="dsh-hld-account-switch">
      ${buttons}
    </div>
  `
}

function renderSummary(data: HoldingsData): string {
  const s = data.summary
  const pnlClass = s.totalPnl >= 0 ? 'profit' : 'loss'
  const pnlSign = s.totalPnl >= 0 ? '+' : ''

  return `
    <div class="dsh-hld-sec">
      <h2>账户摘要</h2>
      <div class="dsh-hld-summary-grid">
        <div class="dsh-hld-summary-card">
          <div class="label">总资产</div>
          <div class="value">¥${formatNumber(s.totalValue)}</div>
          <div class="sub">持仓 ${s.positions} 只</div>
        </div>
        <div class="dsh-hld-summary-card">
          <div class="label">持仓市值</div>
          <div class="value">¥${formatNumber(s.totalMarketValue)}</div>
          <div class="sub">成本 ¥${formatNumber(s.totalCost)}</div>
        </div>
        <div class="dsh-hld-summary-card">
          <div class="label">浮动盈亏</div>
          <div class="value ${pnlClass}">${pnlSign}¥${formatNumber(Math.abs(s.totalPnl))}</div>
          <div class="sub ${pnlClass}">${pnlSign}${s.totalPnlPct.toFixed(2)}%</div>
        </div>
        <div class="dsh-hld-summary-card">
          <div class="label">可用现金</div>
          <div class="value">¥${formatNumber(s.cash)}</div>
          <div class="sub">盈利 ${s.profitCount} / 亏损 ${s.lossCount}</div>
        </div>
      </div>
    </div>
  `
}

function renderCompliance(data: HoldingsData): string {
  const c = data.compliance

  const cashClass = c.cashRatio >= 10 ? 'ok' : c.cashRatio >= 5 ? 'warn' : 'danger'
  const stockClass = c.maxSingleStock <= 20 ? 'ok' : c.maxSingleStock <= 25 ? 'warn' : 'danger'
  const industryClass = c.maxIndustry <= 40 ? 'ok' : c.maxIndustry <= 50 ? 'warn' : 'danger'
  const drawdownClass = Math.abs(c.maxDrawdown60d) <= 8 ? 'ok' : Math.abs(c.maxDrawdown60d) <= 12 ? 'warn' : 'danger'

  return `
    <div class="dsh-hld-sec">
      <h2>合规指标 <span class="sub">现金≥10% / 单股≤20% / 单行业≤40% / 60日回撤≤8%</span></h2>
      <div class="dsh-hld-compliance">
        <div class="dsh-hld-compliance-item">
          <span class="label">现金占比:</span>
          <span class="value ${cashClass}">${c.cashRatio.toFixed(2)}%</span>
        </div>
        <div class="dsh-hld-compliance-item">
          <span class="label">最大单股:</span>
          <span class="value ${stockClass}">${c.maxSingleStock.toFixed(2)}%</span>
        </div>
        <div class="dsh-hld-compliance-item">
          <span class="label">最大行业:</span>
          <span class="value ${industryClass}">${c.maxIndustry > 0 ? c.maxIndustry.toFixed(2) + '%' : 'N/A'}</span>
        </div>
        <div class="dsh-hld-compliance-item">
          <span class="label">60日最大回撤:</span>
          <span class="value ${drawdownClass}">${c.maxDrawdown60d > 0 ? c.maxDrawdown60d.toFixed(2) + '%' : 'N/A'}</span>
        </div>
      </div>
    </div>
  `
}

function renderPositions(data: HoldingsData): string {
  if (data.positions.length === 0) {
    return `
      <div class="dsh-hld-sec">
        <h2>持仓明细</h2>
        <div class="dsh-hld-empty">暂无持仓</div>
      </div>
    `
  }

  const rows = data.positions.map(pos => {
    const pnlClass = pos.profitLoss >= 0 ? 'profit' : 'loss'
    const pnlSign = pos.profitLoss >= 0 ? '+' : ''
    const pnlTodayClass = pos.profitToday >= 0 ? 'profit' : 'loss'
    const pnlTodaySign = pos.profitToday >= 0 ? '+' : ''

    return `
      <tr>
        <td class="code">${escapeHtml(pos.symbol)}</td>
        <td>${escapeHtml(pos.name)}</td>
        <td class="num">${pos.quantity}</td>
        <td class="num">${pos.sharesAvailable}</td>
        <td class="num">¥${pos.avgCost.toFixed(2)}</td>
        <td class="num">¥${pos.currentPrice.toFixed(2)}</td>
        <td class="num">¥${formatNumber(pos.currentValue)}</td>
        <td class="num ${pnlClass}">${pnlSign}¥${formatNumber(Math.abs(pos.profitLoss))}</td>
        <td class="num ${pnlClass}">${pnlSign}${pos.profitLossPct.toFixed(2)}%</td>
        <td class="num ${pnlTodayClass}">${pnlTodaySign}¥${formatNumber(Math.abs(pos.profitToday))}</td>
      </tr>
    `
  }).join('')

  return `
    <div class="dsh-hld-sec">
      <h2>持仓明细 <span class="sub">${data.positions.length} 只股票</span></h2>
      <table class="dsh-hld-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th class="num">持仓</th>
            <th class="num">可卖</th>
            <th class="num">成本价</th>
            <th class="num">现价</th>
            <th class="num">市值</th>
            <th class="num">浮动盈亏</th>
            <th class="num">盈亏比例</th>
            <th class="num">今日盈亏</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>
  `
}

function renderTodayTrades(data: HoldingsData): string {
  if (data.todayTrades.length === 0) {
    return `
      <div class="dsh-hld-sec">
        <h2>今日自动交易</h2>
        <div class="dsh-hld-empty">今日暂无交易</div>
      </div>
    `
  }

  const items = data.todayTrades.map(trade => {
    const actionClass = trade.action.toUpperCase() === 'BUY' ? 'BUY' : 'SELL'
    const time = new Date(trade.created_at).toLocaleTimeString('zh-CN', { hour12: false })
    const pnl = trade.realized_pnl ? ` (实现 ¥${formatNumber(trade.realized_pnl)})` : ''

    return `
      <div class="dsh-hld-trade-item">
        <div class="time">${time}</div>
        <div class="action ${actionClass}">${trade.action.toUpperCase()}</div>
        <div class="symbol">${escapeHtml(trade.symbol)}</div>
        <div class="shares">${trade.shares}股 @ ¥${trade.filled_price.toFixed(2)}${pnl}</div>
        <div class="reason">${escapeHtml(trade.reason || '-')}</div>
      </div>
    `
  }).join('')

  return `
    <div class="dsh-hld-sec">
      <h2>今日自动交易 <span class="sub">${data.todayTrades.length} 笔</span></h2>
      ${items}
    </div>
  `
}

function renderWatchRules(data: HoldingsData): string {
  if (data.watchRules.length === 0) {
    return `
      <div class="dsh-hld-sec">
        <h2>盯盘中心</h2>
        <div class="dsh-hld-empty">暂无盯盘规则</div>
      </div>
    `
  }

  const items = data.watchRules.map(rule => {
    const statusClass = rule.enabled ? 'enabled' : 'disabled'
    const statusText = rule.enabled ? '启用' : '禁用'
    const conditions = rule.conditions.map(c =>
      `${c.field || c.type} ${c.operator} ${c.threshold}`
    ).join(', ')

    return `
      <div class="dsh-hld-watch-item">
        <div class="symbol">${escapeHtml(rule.symbol)}</div>
        <div class="conditions">${escapeHtml(conditions)}</div>
        <div class="status ${statusClass}">${statusText} (触发${rule.triggered_count}次)</div>
      </div>
    `
  }).join('')

  return `
    <div class="dsh-hld-sec">
      <h2>盯盘中心 <span class="sub">${data.watchRules.length} 条规则</span></h2>
      ${items}
    </div>
  `
}

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function formatNumber(num: number): string {
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toFixed(2)
}
