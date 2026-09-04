Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");const t=`[data-dsh-hld-view]`,n=`data-dsh-hld-active`,r=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-exec-active`],i=`dsh-panel-activate`;function a(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}function o(e){let t=new Date().toLocaleString(`zh-CN`,{hour12:!1});return`
    <div class="dsh-hld-board">
      <div class="dsh-hld-wrap">
        <div class="dsh-hld-head">
          <h1 class="dsh-hld-title">持仓看板 <small>账户: ${p(e.currentAccount)}</small></h1>
          <div class="dsh-hld-meta">
            <span>更新时间: ${t}</span>
            <button class="dsh-hld-refresh" onclick="window.__dshHldRefresh?.()">刷新</button>
          </div>
        </div>

        ${s(e)}
        ${c(e)}
        ${l(e)}
        ${u(e)}
        ${d(e)}
        ${f(e)}
      </div>
    </div>
  `}function s(e){return e.accounts.length<=1?``:`
    <div class="dsh-hld-account-switch">
      ${e.accounts.map(t=>`
      <button class="dsh-hld-account-btn ${t.account_name===e.currentAccount?`active`:``}"
              onclick="window.__dshHldSwitchAccount?.('${t.account_name}')">
        ${p(t.display_name||t.account_name)}
        <small>(${t.positions_count}持仓)</small>
      </button>
    `).join(``)}
    </div>
  `}function c(e){let t=e.summary,n=t.totalPnl>=0?`profit`:`loss`,r=t.totalPnl>=0?`+`:``;return`
    <div class="dsh-hld-sec">
      <h2>账户摘要</h2>
      <div class="dsh-hld-summary-grid">
        <div class="dsh-hld-summary-card">
          <div class="label">总资产</div>
          <div class="value">¥${m(t.totalValue)}</div>
          <div class="sub">持仓 ${t.positions} 只</div>
        </div>
        <div class="dsh-hld-summary-card">
          <div class="label">持仓市值</div>
          <div class="value">¥${m(t.totalMarketValue)}</div>
          <div class="sub">成本 ¥${m(t.totalCost)}</div>
        </div>
        <div class="dsh-hld-summary-card">
          <div class="label">浮动盈亏</div>
          <div class="value ${n}">${r}¥${m(Math.abs(t.totalPnl))}</div>
          <div class="sub ${n}">${r}${t.totalPnlPct.toFixed(2)}%</div>
        </div>
        <div class="dsh-hld-summary-card">
          <div class="label">可用现金</div>
          <div class="value">¥${m(t.cash)}</div>
          <div class="sub">盈利 ${t.profitCount} / 亏损 ${t.lossCount}</div>
        </div>
      </div>
    </div>
  `}function l(e){let t=e.compliance,n=t.cashRatio>=10?`ok`:t.cashRatio>=5?`warn`:`danger`,r=t.maxSingleStock<=20?`ok`:t.maxSingleStock<=25?`warn`:`danger`,i=t.maxIndustry<=40?`ok`:t.maxIndustry<=50?`warn`:`danger`,a=Math.abs(t.maxDrawdown60d)<=8?`ok`:Math.abs(t.maxDrawdown60d)<=12?`warn`:`danger`;return`
    <div class="dsh-hld-sec">
      <h2>合规指标 <span class="sub">现金≥10% / 单股≤20% / 单行业≤40% / 60日回撤≤8%</span></h2>
      <div class="dsh-hld-compliance">
        <div class="dsh-hld-compliance-item">
          <span class="label">现金占比:</span>
          <span class="value ${n}">${t.cashRatio.toFixed(2)}%</span>
        </div>
        <div class="dsh-hld-compliance-item">
          <span class="label">最大单股:</span>
          <span class="value ${r}">${t.maxSingleStock.toFixed(2)}%</span>
        </div>
        <div class="dsh-hld-compliance-item">
          <span class="label">最大行业:</span>
          <span class="value ${i}">${t.maxIndustry>0?t.maxIndustry.toFixed(2)+`%`:`N/A`}</span>
        </div>
        <div class="dsh-hld-compliance-item">
          <span class="label">60日最大回撤:</span>
          <span class="value ${a}">${t.maxDrawdown60d>0?t.maxDrawdown60d.toFixed(2)+`%`:`N/A`}</span>
        </div>
      </div>
    </div>
  `}function u(e){if(e.positions.length===0)return`
      <div class="dsh-hld-sec">
        <h2>持仓明细</h2>
        <div class="dsh-hld-empty">暂无持仓</div>
      </div>
    `;let t=e.positions.map(e=>{let t=e.profitLoss>=0?`profit`:`loss`,n=e.profitLoss>=0?`+`:``,r=e.profitToday>=0?`profit`:`loss`,i=e.profitToday>=0?`+`:``;return`
      <tr>
        <td class="code">${p(e.symbol)}</td>
        <td>${p(e.name)}</td>
        <td class="num">${e.quantity}</td>
        <td class="num">${e.sharesAvailable}</td>
        <td class="num">¥${e.avgCost.toFixed(2)}</td>
        <td class="num">¥${e.currentPrice.toFixed(2)}</td>
        <td class="num">¥${m(e.currentValue)}</td>
        <td class="num ${t}">${n}¥${m(Math.abs(e.profitLoss))}</td>
        <td class="num ${t}">${n}${e.profitLossPct.toFixed(2)}%</td>
        <td class="num ${r}">${i}¥${m(Math.abs(e.profitToday))}</td>
      </tr>
    `}).join(``);return`
    <div class="dsh-hld-sec">
      <h2>持仓明细 <span class="sub">${e.positions.length} 只股票</span></h2>
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
          ${t}
        </tbody>
      </table>
    </div>
  `}function d(e){if(e.todayTrades.length===0)return`
      <div class="dsh-hld-sec">
        <h2>今日自动交易</h2>
        <div class="dsh-hld-empty">今日暂无交易</div>
      </div>
    `;let t=e.todayTrades.map(e=>{let t=e.action.toUpperCase()===`BUY`?`BUY`:`SELL`,n=new Date(e.created_at).toLocaleTimeString(`zh-CN`,{hour12:!1}),r=e.realized_pnl?` (实现 ¥${m(e.realized_pnl)})`:``;return`
      <div class="dsh-hld-trade-item">
        <div class="time">${n}</div>
        <div class="action ${t}">${e.action.toUpperCase()}</div>
        <div class="symbol">${p(e.symbol)}</div>
        <div class="shares">${e.shares}股 @ ¥${e.filled_price.toFixed(2)}${r}</div>
        <div class="reason">${p(e.reason||`-`)}</div>
      </div>
    `}).join(``);return`
    <div class="dsh-hld-sec">
      <h2>今日自动交易 <span class="sub">${e.todayTrades.length} 笔</span></h2>
      ${t}
    </div>
  `}function f(e){if(e.watchRules.length===0)return`
      <div class="dsh-hld-sec">
        <h2>盯盘中心</h2>
        <div class="dsh-hld-empty">暂无盯盘规则</div>
      </div>
    `;let t=e.watchRules.map(e=>{let t=e.enabled?`enabled`:`disabled`,n=e.enabled?`启用`:`禁用`,r=e.conditions.map(e=>`${e.field||e.type} ${e.operator} ${e.threshold}`).join(`, `);return`
      <div class="dsh-hld-watch-item">
        <div class="symbol">${p(e.symbol)}</div>
        <div class="conditions">${p(r)}</div>
        <div class="status ${t}">${n} (触发${e.triggered_count}次)</div>
      </div>
    `}).join(``);return`
    <div class="dsh-hld-sec">
      <h2>盯盘中心 <span class="sub">${e.watchRules.length} 条规则</span></h2>
      ${t}
    </div>
  `}function p(e){let t=document.createElement(`div`);return t.textContent=e,t.innerHTML}function m(e){return e>=1e4?(e/1e4).toFixed(2)+`万`:e.toFixed(2)}function h(){let e=!1,a=`agent_virtual`,s,c=()=>{if(!e){e=!0,console.log(`[dashboard-holdings] opening board`),document.documentElement.setAttribute(n,``);for(let e of r)document.documentElement.removeAttribute(e);window.dispatchEvent(new CustomEvent(i,{detail:`dashboard-holdings`})),p(),h(a)}},l=()=>{e&&(e=!1,console.log(`[dashboard-holdings] closing board`),document.documentElement.removeAttribute(n),m())},u=()=>{e?l():c()},d=()=>{console.log(`[dashboard-holdings] manual refresh`),h(a)},f=e=>{console.log(`[dashboard-holdings] switching account to`,e),a=e,h(e)},p=()=>{m(),s=window.setInterval(()=>{e&&h(a)},15e3)},m=()=>{s!==void 0&&(clearInterval(s),s=void 0)},h=async e=>{try{let t=`/dashboard/api/holdings?account=${encodeURIComponent(e)}`,n=await(await fetch(t)).json();if(!n.success)throw Error(n.error||`Unknown error`);let r=n.data;g(r)}catch(e){console.error(`[dashboard-holdings] fetch failed:`,e),_(String(e))}},g=e=>{let n=document.querySelector(t);n&&(n.innerHTML=o(e))},_=e=>{let n=document.querySelector(t);n&&(n.innerHTML=`
      <div class="dsh-hld-board">
        <div class="dsh-hld-wrap">
          <div class="dsh-hld-head">
            <h1 class="dsh-hld-title">持仓看板</h1>
          </div>
          <div class="dsh-hld-banner show">
            数据加载失败: ${e}
          </div>
        </div>
      </div>
    `)};return{openBoard:c,closeBoard:l,toggleBoard:u,getSnapshot:()=>({boardOpen:e}),refresh:d,switchAccount:f}}function g(e){let t,n=()=>{if(t!==void 0)return;let e=a();e!==void 0&&(t=document.createElement(`div`),t.setAttribute(`data-dsh-hld-view`,``),t.className=`dsh-hld-view`,e.appendChild(t),console.log(`[dashboard-holdings] board container mounted`))},r=new MutationObserver(()=>{n()});r.observe(document.body,{childList:!0,subtree:!0}),n(),window.__dshHldRefresh=()=>e.refresh(),window.__dshHldSwitchAccount=t=>e.switchAccount(t);let o=t=>{t.detail!==`dashboard-holdings`&&e.getSnapshot().boardOpen&&e.closeBoard()};window.addEventListener(i,o);let s=t=>{if(!e.getSnapshot().boardOpen)return;let n=t.target;n!==null&&n.closest(`[data-dsh-hld-view]`)===null&&n.closest(`[class*="dsh-hld-foot"]`)===null&&n.closest(`[data-dsh-hld-entry]`)===null&&e.closeBoard()};return document.addEventListener(`click`,s,!0),()=>{window.removeEventListener(i,o),document.removeEventListener(`click`,s,!0),r.disconnect(),t!==void 0&&t.remove(),delete window.__dshHldRefresh,delete window.__dshHldSwitchAccount,console.log(`[dashboard-holdings] board unmounted`)}}const _=`持仓看板`,v=`@pi-investment/dashboard-holdings/footer-action.css`,y=`dashboard-holdings:open-board`;function b(t){let{wide:n}=t,r=_;return(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-hld-foot wide`:`dsh-hld-foot rail`,title:r,"aria-label":r,onClick:()=>{console.log(`[dashboard-holdings] footer action clicked — dispatching`,y),window.dispatchEvent(new CustomEvent(y,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-hld-foot-icon`,key:`i`},x),(0,e.createElement)(`span`,{className:`dsh-hld-foot-label`,key:`l`},r)]:(0,e.createElement)(`span`,{className:`dsh-hld-foot-icon`,key:`i`},x))}const x=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`circle`,{cx:`8`,cy:`8`,r:`6`}),(0,e.createElement)(`path`,{d:`M8 2 V8 L12 11`}),(0,e.createElement)(`path`,{d:`M8 8 L4 5`}));function S(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${v}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=v,e.textContent=`
.dsh-hld-foot {
  display: flex; align-items: center; gap: 8px;
  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
  font: inherit; font-size: 13px; cursor: pointer;
  -webkit-appearance: none; appearance: none;
}
.dsh-hld-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-hld-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
.dsh-hld-foot.wide {
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border-radius: 8px; justify-content: flex-start; text-align: left;
}
.dsh-hld-foot.rail {
  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
  justify-content: center; padding: 0;
}
.dsh-hld-foot-icon { display: inline-flex; flex: none; }
.dsh-hld-foot.rail .dsh-hld-foot-label { display: none; }
.dsh-hld-foot-icon svg { width: 16px; height: 16px; }
`,document.head.appendChild(e)}function C(){let e=`dsh-hld-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
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
/* sidebar.footer.action 列表默认按行排布——把整个 seat 容器改为纵向列，
   两个看板按钮即上下堆叠（wide 整宽 / rail 纵向图标） */
div[data-slot="sidebar.footer.action"] {
  display: flex !important; flex-direction: column; align-items: stretch; width: 100%; min-width: 0;
}
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
`,(document.head??document.documentElement).appendChild(t)}const w=[`slots`];function T(e){try{S(),C(),window.__dshHldClient?.dispose();let t=h(),n=g(t),r=e=>{let n=e.detail?.open;console.log(`[dashboard-holdings] open-board event`,{open:n},`boardOpen:`,t.getSnapshot().boardOpen),n===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(y,r),window.__dshHldClient={dispose:()=>{window.removeEventListener(y,r),n(),t.closeBoard()}};let i=e.slots;i?i.inject(`sidebar.footer.action`,()=>i.register({name:`sidebar.footer.action`,id:`dashboard-holdings`,order:200,label:_},b)):console.warn(`[dashboard-holdings] ctx.slots unavailable (inject missing "slots")`)}catch(e){console.error(`[dashboard-holdings] client half failed to start:`,e)}}exports.apply=T,exports.inject=w,exports.name=`@pi-investment/dashboard-holdings/client`;