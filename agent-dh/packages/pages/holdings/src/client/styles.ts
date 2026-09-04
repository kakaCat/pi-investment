/**
 * Board styles, injected as one global stylesheet with dsh-hld- prefixed
 * classes. Surfaces/text ride the shell's --dsw-* tokens where available so
 * the board follows the active theme; status accents are the fixed palette.
 *
 * @module dashboard-holdings/client/styles
 */
export const STYLES = `
.dsh-hld-entry {
  display: flex; align-items: center; gap: 8px; position: relative;
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border: none; border-radius: 8px; background: transparent;
  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
  cursor: pointer; text-align: left;
}
.dsh-hld-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-hld-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
.dsh-hld-entry svg { flex: none; }
[data-sidebar-collapsed] [data-dsh-hld-entry],
[class*="_collapsed"] [data-dsh-hld-entry] {
  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
  justify-content: center; gap: 0; text-align: center;
}
[data-sidebar-collapsed] [data-dsh-hld-entry] .dsh-hld-entry-label,
[class*="_collapsed"] [data-dsh-hld-entry] .dsh-hld-entry-label { display: none; }
[data-sidebar-collapsed] [data-dsh-hld-entry] svg,
[class*="_collapsed"] [data-dsh-hld-entry] svg { width: 16px; height: 16px; }

html[data-dsh-hld-active] [data-pane="conversation"] > *:not([data-dsh-hld-view]),
html[data-dsh-hld-active] [class*="centerCol"] > *:not([data-dsh-hld-view]),
html[data-dsh-hld-active] .dshDesktopConversationSurface > *:not([data-dsh-hld-view]) { display: none !important; }
.dsh-hld-view { display: none; }
html[data-dsh-hld-active] .dsh-hld-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.dsh-hld-board { flex: 1; min-height: 0; overflow-y: auto; box-sizing: border-box; }

/* ---- board inner ---- */
.dsh-hld-board {
  --bg:#0b0f1c; --panel:#121a2c; --panel2:#0f1626; --line:#1e2a44;
  --text:#dbe4f0; --dim:#8ea0bd; --faint:#5b6b8c;
  --profit:#22c55e; --loss:#ef4444; --warn:#eab308; --neutral:#94a3b8;
  --accent:#3b82f6; --accent2:#8b5cf6;
  padding: 14px 18px 40px; color: var(--text); font: 13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
}
body[data-ds-dark-theme] .dsh-hld-board { --text:#e6e8eb; --dim:#9aa3b2; --faint:#6a7385; --line:#333947; --panel:#20242e; --panel2:#1a1e27; --bg:#14161d; }
.dsh-hld-board * { box-sizing: border-box; }
.dsh-hld-wrap { max-width: 1560px; }
.dsh-hld-head { display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
.dsh-hld-title { font-size: 18px; letter-spacing: .5px; margin: 0; color: var(--text); }
.dsh-hld-title small { color: var(--faint); font-weight: normal; margin-left: 10px; font-size: 11px; }
.dsh-hld-meta { margin-left: auto; color: var(--faint); font-size: 12px; display: flex; gap: 14px; align-items: baseline; }
.dsh-hld-refresh { background: var(--accent); color: #fff; border: 0; border-radius: 6px; padding: 5px 14px; font-size: 12px; cursor: pointer; }
.dsh-hld-refresh:active { opacity: .8; }
.dsh-hld-banner { display: none; background:#3b1c1c; border:1px solid var(--loss); color:#fca5a5; padding:8px 14px; border-radius:8px; margin-bottom:14px; font-size:12px; }
.dsh-hld-banner.show { display:block; }

/* 账户切换器 */
.dsh-hld-account-switch { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.dsh-hld-account-btn { background: var(--panel); border: 1px solid var(--line); color: var(--text); padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; }
.dsh-hld-account-btn:hover { background: var(--panel2); }
.dsh-hld-account-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 500; }

/* 区块 */
.dsh-hld-sec { margin-bottom: 20px; }
.dsh-hld-sec > h2 { font-size: 13px; color: var(--accent); border-left: 3px solid var(--accent); padding-left: 8px; margin: 0 0 8px; }
.dsh-hld-sec > h2 .sub { color: var(--faint); font-weight: normal; font-size: 10.5px; margin-left: 8px; }

/* 摘要卡片网格 */
.dsh-hld-summary-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap: 10px; margin-bottom: 20px; }
.dsh-hld-summary-card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }
.dsh-hld-summary-card .label { font-size: 11px; color: var(--faint); margin-bottom: 4px; }
.dsh-hld-summary-card .value { font-size: 20px; font-weight: 600; color: var(--text); }
.dsh-hld-summary-card .value.profit { color: var(--profit); }
.dsh-hld-summary-card .value.loss { color: var(--loss); }
.dsh-hld-summary-card .sub { font-size: 11px; color: var(--dim); margin-top: 4px; }

/* 持仓表格 */
.dsh-hld-table { width:100%; border-collapse:collapse; font-size:12px; background:var(--panel); border-radius:10px; overflow: hidden; }
.dsh-hld-table th { text-align:left; color:var(--faint); font-weight:500; padding:8px 10px; border-bottom:1px solid var(--line); background:var(--panel2); font-size:11px; white-space:nowrap; }
.dsh-hld-table th.num { text-align: right; }
.dsh-hld-table td { padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; color:var(--text); }
.dsh-hld-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
.dsh-hld-table td.code { font-family: ui-monospace,Consolas,monospace; color: var(--accent2); }
.dsh-hld-table .profit { color: var(--profit); }
.dsh-hld-table .loss { color: var(--loss); }
.dsh-hld-table .neutral { color: var(--neutral); }

/* 合规指标 */
.dsh-hld-compliance { display: flex; gap: 16px; flex-wrap: wrap; padding: 12px; background: var(--panel2); border-radius: 8px; font-size: 12px; }
.dsh-hld-compliance-item { display: flex; gap: 6px; align-items: baseline; }
.dsh-hld-compliance-item .label { color: var(--faint); }
.dsh-hld-compliance-item .value { color: var(--text); font-weight: 500; }
.dsh-hld-compliance-item .value.ok { color: var(--profit); }
.dsh-hld-compliance-item .value.warn { color: var(--warn); }
.dsh-hld-compliance-item .value.danger { color: var(--loss); }

/* 交易记录 */
.dsh-hld-trade-item { display: flex; gap: 12px; padding: 8px 12px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; margin-bottom: 8px; font-size: 12px; }
.dsh-hld-trade-item .time { color: var(--faint); font-size: 11px; min-width: 80px; }
.dsh-hld-trade-item .action { font-weight: 600; min-width: 40px; }
.dsh-hld-trade-item .action.BUY { color: var(--profit); }
.dsh-hld-trade-item .action.SELL { color: var(--loss); }
.dsh-hld-trade-item .symbol { color: var(--accent2); font-family: ui-monospace,Consolas,monospace; }
.dsh-hld-trade-item .reason { color: var(--dim); font-size: 11px; flex: 1; }

/* 盯盘规则 */
.dsh-hld-watch-item { display: flex; gap: 12px; padding: 10px 12px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; margin-bottom: 8px; font-size: 12px; align-items: center; }
.dsh-hld-watch-item .symbol { color: var(--accent2); font-family: ui-monospace,Consolas,monospace; min-width: 80px; font-weight: 500; }
.dsh-hld-watch-item .conditions { color: var(--text); flex: 1; }
.dsh-hld-watch-item .status { padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.dsh-hld-watch-item .status.enabled { background: #10293f; color: #60a5fa; }
.dsh-hld-watch-item .status.disabled { background: var(--panel2); color: var(--faint); }

.dsh-hld-empty { color: var(--faint); font-size: 12px; padding: 16px 0; text-align: center; }
`

/** Inject the stylesheet once (tagged for the HMR driver's cleanup). */
export function injectStyles(): void {
  const id = 'dsh-hld-styles'
  if (document.getElementById(id) !== null) return
  const style = document.createElement('style')
  style.id = id
  style.textContent = STYLES
  ;(document.head ?? document.documentElement).appendChild(style)
}
