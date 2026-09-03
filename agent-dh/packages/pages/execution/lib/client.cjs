Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});function e(){let e=`dsh-exec-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
.dsh-exec-entry {
  display: flex; align-items: center; gap: 8px; position: relative;
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border: none; border-radius: 8px; background: transparent;
  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
  cursor: pointer; text-align: left;
}
.dsh-exec-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-exec-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
.dsh-exec-entry svg { flex: none; }
[data-sidebar-collapsed] [data-dsh-exec-entry],
[class*="_collapsed"] [data-dsh-exec-entry] {
  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
  justify-content: center; gap: 0; text-align: center;
}
[data-sidebar-collapsed] [data-dsh-exec-entry] .dsh-exec-entry-label,
[class*="_collapsed"] [data-dsh-exec-entry] .dsh-exec-entry-label { display: none; }
[data-sidebar-collapsed] [data-dsh-exec-entry] svg,
[class*="_collapsed"] [data-dsh-exec-entry] svg { width: 16px; height: 16px; }

html[data-dsh-exec-active] [data-pane="conversation"] > *:not([data-dsh-exec-view]),
html[data-dsh-exec-active] [class*="centerCol"] > *:not([data-dsh-exec-view]),
html[data-dsh-exec-active] .dshDesktopConversationSurface > *:not([data-dsh-exec-view]) { display: none !important; }
.dsh-exec-view { display: none; }
html[data-dsh-exec-active] .dsh-exec-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.dsh-exec-board { flex: 1; min-height: 0; overflow-y: auto; box-sizing: border-box; }

/* ---- board inner ---- */
.dsh-exec-board {
  --bg:#0b0f1c; --panel:#121a2c; --panel2:#0f1626; --line:#1e2a44;
  --text:#dbe4f0; --dim:#8ea0bd; --faint:#5b6b8c;
  --ok:#22c55e; --fail:#ef4444; --late:#eab308; --pend:#94a3b8;
  --unk:#a855f7; --off:#4b5563; --deg:#f97316; --accent:#3b82f6;
  padding: 14px 18px 40px; color: var(--text); font: 13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
}
body[data-ds-dark-theme] .dsh-exec-board { --text:#e6e8eb; --dim:#9aa3b2; --faint:#6a7385; --line:#333947; --panel:#20242e; --panel2:#1a1e27; --bg:#14161d; }
.dsh-exec-board * { box-sizing: border-box; }
.dsh-exec-wrap { max-width: 1560px; }
.dsh-exec-head { display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
.dsh-exec-title { font-size: 18px; letter-spacing: .5px; margin: 0; color: var(--text); }
.dsh-exec-title small { color: var(--faint); font-weight: normal; margin-left: 10px; font-size: 11px; }
.dsh-exec-meta { margin-left: auto; color: var(--faint); font-size: 12px; display: flex; gap: 14px; align-items: baseline; }
.dsh-exec-btn { background: var(--accent); color: #fff; border: 0; border-radius: 6px; padding: 5px 14px; font-size: 12px; cursor: pointer; }
.dsh-exec-btn:active { opacity: .8; }
.dsh-exec-legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; color: var(--dim); align-items: center; }
.dsh-exec-lg { display: inline-flex; align-items: center; gap: 4px; }
.dsh-exec-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }
.dsh-exec-banner { display: none; background:#3b1c1c; border:1px solid var(--fail); color:#fca5a5; padding:8px 14px; border-radius:8px; margin-bottom:14px; font-size:12px; }
.dsh-exec-banner.show { display:block; }
.dsh-exec-sec { margin-bottom: 20px; }
.dsh-exec-sec > h2 { font-size: 13px; color: var(--accent); border-left: 3px solid var(--accent); padding-left: 8px; margin: 0 0 8px; }
.dsh-exec-sec > h2 .sub { color: var(--faint); font-weight: normal; font-size: 10.5px; margin-left: 8px; }
.dsh-exec-grid4 { display: grid; grid-template-columns: repeat(auto-fit,minmax(230px,1fr)); gap: 10px; }
.dsh-exec-card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }
.dsh-exec-card h3 { font-size: 13px; display: flex; align-items: center; gap: 8px; margin: 0 0 8px; }
.dsh-exec-card h3 .port { color: var(--faint); font-weight: normal; font-size: 11px; }
.dsh-exec-kv { color: var(--dim); font-size: 11.5px; }
.dsh-exec-kv div { display: flex; justify-content: space-between; gap: 8px; }
.dsh-exec-kv b { color: var(--text); font-weight: 500; text-align: right; word-break: break-all; }
.dsh-exec-errline { color: #fca5a5; font-size: 11px; margin-top: 6px; word-break: break-all; }
.dsh-exec-time { color: var(--faint); font-size: 10.5px; margin-top: 6px; }
.dsh-exec-ok, .dsh-exec-confirmed { color: var(--ok); }
.dsh-exec-fail, .dsh-exec-failed { color: var(--fail); }
.dsh-exec-late { color: var(--late); }
.dsh-exec-pending { color: var(--pend); }
.dsh-exec-unknown { color: var(--unk); }
.dsh-exec-degraded { color: var(--deg); }
.dsh-exec-off_day { color: var(--off); }
.dsh-exec-dot.ok, .dsh-exec-dot.confirmed { background: var(--ok); }
.dsh-exec-dot.failed { background: var(--fail); }
.dsh-exec-dot.late { background: var(--late); }
.dsh-exec-dot.pending { background: var(--pend); }
.dsh-exec-dot.unknown { background: var(--unk); }
.dsh-exec-dot.off_day { background: var(--off); }
.dsh-exec-dot.degraded { background: var(--deg); }
.dsh-exec-alert-card { background: #261818; border: 1px solid #7f1d1d; border-radius: 10px; padding: 12px 14px; }
.dsh-exec-alert-item { display:flex; gap:10px; align-items:baseline; margin-bottom:6px; font-size:12px; }
.dsh-exec-alert-item .flow { color: var(--faint); }
.dsh-exec-cp-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(196px,1fr)); gap:8px; }
.dsh-exec-cp { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--line); border-radius:8px; padding:9px 11px; }
.dsh-exec-cp .top { display:flex; justify-content:space-between; align-items:center; gap:6px; }
.dsh-exec-cp .mod { font-size:10px; color:var(--faint); }
.dsh-exec-cp .nm { font-size:12.5px; margin:3px 0; }
.dsh-exec-cp .msg { font-size:11px; color:var(--dim); word-break:break-all; }
.dsh-exec-group-title { font-size:11px; color:var(--faint); margin:12px 0 6px; letter-spacing:1px; }
.dsh-exec-errs { list-style:none; margin:0; padding:0; }
.dsh-exec-errs li { font-family: ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11px; padding:6px 10px; border-bottom:1px solid var(--line); display:flex; gap:10px; align-items:baseline; color:var(--dim); }
.dsh-exec-errs li .src { flex:none; border-radius:4px; padding:0 6px; font-size:10px; }
.dsh-exec-errs .src.v2 { background:#3b2a14; color:#fbbf24; }
.dsh-exec-errs .src.os { background:#10293f; color:#60a5fa; }
.dsh-exec-errs .src.dsh { background:#3b1140; color:#d8b4fe; }
.dsh-exec-errs .line { color:#e2e8f0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:70%; }
.dsh-exec-errs .file { color:var(--faint); flex:none; }
.dsh-exec-timeline { display:flex; flex-wrap:wrap; gap:6px; }
.dsh-exec-tl { border:1px solid var(--line); background:var(--panel2); border-radius:8px; padding:5px 10px; font-size:11.5px; display:flex; gap:8px; align-items:center; }
.dsh-exec-tl .t { color:var(--accent); font-weight:600; }
.dsh-exec-tl .e { color:var(--dim); }
.dsh-exec-table { width:100%; border-collapse:collapse; font-size:12px; background:var(--panel); border-radius:10px; }
.dsh-exec-table th { text-align:left; color:var(--faint); font-weight:500; padding:8px 10px; border-bottom:1px solid var(--line); background:var(--panel2); font-size:11px; white-space:nowrap; }
.dsh-exec-table td { padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; color:var(--text); }
.dsh-exec-table td.num, .dsh-exec-table td.id { color:var(--faint); white-space:nowrap; }
.dsh-exec-table td.err { font-family:ui-monospace,Consolas,monospace; font-size:10.5px; color:#fca5a5; word-break:break-all; }
.dsh-exec-dim { color:var(--dim); } .dsh-exec-faint { color:var(--faint); }
.dsh-exec-on { color:var(--ok); } .dsh-exec-off { color:var(--fail); }
.dsh-exec-empty { color: var(--faint); font-size: 12px; padding: 8px 0; }
`,(document.head??document.documentElement).appendChild(t)}const t=`data-dsh-exec-active`,n=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`],r=`dsh-panel-activate`;function i(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function a(e){return e==null?``:String(e).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`)}function o(e){if(!e)return`—`;let t=String(e).includes(` `)?String(e).replace(` `,`T`):String(e),n=new Date(t);if(Number.isNaN(n.getTime()))return a(e);let r=e=>(e<10?`0`:``)+e;return r(n.getMonth()+1)+`-`+r(n.getDate())+` `+r(n.getHours())+`:`+r(n.getMinutes())}function s(e){let t=Number(e);if(!Number.isFinite(t)||t<0)return e==null?`—`:String(e);let n=Math.floor(t/86400),r=Math.floor(t%86400/3600),i=Math.floor(t%3600/60);return n>0?n+`d `+r+`h`:r>0?r+`h `+i+`m`:i+`m`}function c(e,t){return t==null?`—`:typeof t==`boolean`?t?`是`:`否`:typeof t==`number`?e===`uptime_s`?s(t):Math.abs(t)>=1e5?t.toLocaleString(`zh-CN`,{maximumFractionDigits:0}):String(Math.round(t*100)/100):a(t)}const l={confirmed:`已确认`,failed:`失败`,late:`晚点`,pending:`等待`,off_day:`非执行日`,unknown:`未知`},u={ok:`正常`,degraded:`降级`,failed:`故障`},d={success:`成功`,failed:`失败`,pending:`待运行`,unknown:`未知`},f={"quantsys-v2":`量化后端 quantsys-v2`,"agent-os":`Agent OS (v1 遗留)`,postgres:`PostgreSQL (经 v2 代理)`,"agent-dh":`Agent-DH 进程(本看板宿主)`},p={api:`API`,db:`DB`,db_connected:`db_connected`,holdings_count:`持仓数`,model_loaded:`模型加载`,balance_date:`结算日`,total_assets:`总资产`,status:`status`,via:`via`,uptime_s:`运行时长`,rss_mb:`RSS(MB)`,heap_mb:`Heap(MB)`,restarts:`重启次数`,probe_ms:`探测耗时`},m={engine_m0:`ENGINE · M0 数据地基 / M1 市场感知 / M2 股票池 / M3 信号执行`,engine_m46:`ENGINE · M4 风控 / M5 交易对账 / M6 经验沉淀`,autonomy:`AUTONOMY · L1 策略验证 / L2 蒸馏 / L3 裁决 / L4 周报`},h={ok:`ok`,confirmed:`confirmed`,failed:`failed`,late:`late`,pending:`pending`,unknown:`unknown`,off_day:`off_day`,degraded:`degraded`,success:`ok`};function g(){let e=document.createElement(`div`);e.className=`dsh-exec-board`,e.dataset.dshExecView=``,e.innerHTML=`
<div class="dsh-exec-wrap">
  <div class="dsh-exec-head">
    <h1 class="dsh-exec-title">双线执行确认看板<small>engine(M0–M6) × autonomy(L1–L4)</small></h1>
    <div class="dsh-exec-meta">
      <span class="dsh-exec-legend">
        <span class="dsh-exec-lg"><i class="dsh-exec-dot confirmed"></i>已确认</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot pending"></i>等待</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot late"></i>晚点</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot failed"></i>失败</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot unknown"></i>未知</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot off_day"></i>非执行日</span>
        <span class="dsh-exec-lg"><i class="dsh-exec-dot degraded"></i>降级</span>
      </span>
      <span class="dsh-exec-last" data-role="lastFetch">—</span>
      <button class="dsh-exec-btn" data-role="refresh">立即刷新</button>
    </div>
  </div>
  <div class="dsh-exec-banner" data-role="banner"></div>
  <div class="dsh-exec-sec"><h2>系统健康</h2><div class="dsh-exec-grid4" data-role="health"></div></div>
  <div class="dsh-exec-sec" data-role="alertsSec" style="display:none"><h2>阻断告警<span class="sub">failed/late 且声明阻断下游</span></h2><div data-role="alerts"></div></div>
  <div class="dsh-exec-sec"><h2>执行检查点<span class="sub">状态语义：expectTime + 宽限(默认30min) 窗口内展示等待，绝不误报失败</span></h2>
    <div class="dsh-exec-group-title">${m.engine_m0}</div><div class="dsh-exec-cp-grid" data-role="cpM0M3"></div>
    <div class="dsh-exec-group-title">${m.engine_m46}</div><div class="dsh-exec-cp-grid" data-role="cpM4M6"></div>
    <div class="dsh-exec-group-title">${m.autonomy}</div><div class="dsh-exec-cp-grid" data-role="cpL"></div>
  </div>
  <div class="dsh-exec-sec"><h2>错误事件流<span class="sub">v2/os/dsh 日志尾部近 10 条（ERROR/CRITICAL/Traceback）</span></h2>
    <ol class="dsh-exec-errs" data-role="errors"></ol></div>
  <div class="dsh-exec-sec"><h2>今日时间轴<span class="sub">真实 cron 计划 × 当日运行结果</span></h2>
    <div class="dsh-exec-timeline" data-role="timeline"></div></div>
  <div class="dsh-exec-sec"><h2>调度任务明细<span class="sub">全部任务</span></h2>
    <table class="dsh-exec-table"><thead><tr>
      <th>ID</th><th>任务</th><th>启用</th><th>计划(cron)</th><th>下次运行</th><th>今日</th><th>最近一次运行</th><th>错误详情</th>
    </tr></thead><tbody data-role="tasks"></tbody></table>
  </div>
</div>`;let t=t=>e.querySelector(t);return{board:e,meta:t(`[data-role="lastFetch"]`),banner:t(`[data-role="banner"]`),healthGrid:t(`[data-role="health"]`),alertsSec:t(`[data-role="alertsSec"]`),alertsBox:t(`[data-role="alerts"]`),gridM0M3:t(`[data-role="cpM0M3"]`),gridM4M6:t(`[data-role="cpM4M6"]`),gridL:t(`[data-role="cpL"]`),errList:t(`[data-role="errors"]`),timelineBox:t(`[data-role="timeline"]`),taskTable:t(`table`)}}function _(e,t){let n=t.health??[];e.healthGrid.innerHTML=n.map(e=>{let t=f[e.name??``]??e.name??`?`,n=u[e.status??``]??e.status??`?`,r=e.port?`<span class="port">:`+e.port+`</span>`:``,i=(e.metrics?Object.keys(e.metrics):[]).filter(e=>e!==`probe_ms`).map(t=>`<div><span>`+a(p[t]??t)+`</span><b>`+c(t,e.metrics[t])+`</b></div>`).join(``),o=e.error?`<div class="dsh-exec-errline">`+a(e.error)+`</div>`:``,s=e.responseTimeMs===void 0?``:`<div class="dsh-exec-time">探测 `+e.responseTimeMs+`ms</div>`;return`<div class="dsh-exec-card"><h3><i class="dsh-exec-dot `+a(e.status)+`"></i>`+a(t)+r+`<span class="`+a(e.status)+`" style="margin-left:auto">`+a(n)+`</span></h3><div class="dsh-exec-kv">`+i+`</div>`+o+s+`</div>`}).join(``),n.length===0&&(e.healthGrid.innerHTML=`<div class="dsh-exec-card dsh-exec-dim">无健康数据</div>`)}function v(e,t){let n=t.blockedFlows??[];if(n.length===0){e.alertsSec.style.display=`none`;return}e.alertsSec.style.display=``;let r={failed:`失败`,late:`晚点`};e.alertsBox.innerHTML=`<div class="dsh-exec-alert-card">`+n.map(e=>`<div class="dsh-exec-alert-item"><span class="`+a(e.status)+`">`+a(e.checkpointName)+`（`+a(r[e.status??``]??e.status)+`）</span><span class="dsh-exec-dim">阻断下游：</span><span class="flow">`+(e.blocks??[]).map(a).join(` · `)+`</span></div>`).join(``)+`</div>`}function y(e,t){let n=t.checkpoints??[],r={m0m3:[],m46:[],l:[]};for(let e of n){let t=e.line===`engine`,n=e.module??``;t&&/^M[0-3]/.test(n)?r.m0m3.push(e):t&&/^M[4-6]/.test(n)?r.m46.push(e):r.l.push(e)}let i=e=>{let t=l[e.status??``]??e.status??`?`,n=h[e.status??``]??e.status,r=e.message?`<div class="msg">`+a(e.message)+`</div>`:``;return`<div class="dsh-exec-cp" title="`+a(e.id)+`"><div class="top"><i class="dsh-exec-dot `+a(n)+`"></i><span class="mod">`+a(e.module??``)+`</span><span class="`+a(n)+`">`+a(t)+`</span></div><div class="nm">`+a(e.name??``)+`</div>`+r+`</div>`};e.gridM0M3.innerHTML=r.m0m3.map(i).join(``)||`<div class="dsh-exec-empty">无</div>`,e.gridM4M6.innerHTML=r.m46.map(i).join(``)||`<div class="dsh-exec-empty">无</div>`,e.gridL.innerHTML=r.l.map(i).join(``)||`<div class="dsh-exec-empty">无</div>`}function b(e,t){let n=t.errors??[];e.errList.innerHTML=n.map(e=>`<li><span class="src `+a(e.source??``)+`">`+a(e.source??`?`)+`</span><span class="file">`+a(e.file??``)+`</span><span class="line" title="`+a(e.line)+`">`+a(e.line??``)+`</span></li>`).join(``)||`<li class="dsh-exec-empty">近 300 行日志内无错误事件</li>`}function x(e,t){let n=t.timeline??[],r=e=>e===`success`?`ok`:e===`failed`?`failed`:e===`unknown`?`unknown`:`pending`;e.timelineBox.innerHTML=n.map(e=>{let t=d[e.status??``]??e.status??`?`;return`<div class="dsh-exec-tl"><i class="dsh-exec-dot `+r(e.status??``)+`"></i><span class="t">`+a(e.expectedTime??``)+`</span><span class="e">`+a(e.taskName??``)+`</span><span class="`+r(e.status??``)+`">`+a(t)+`</span></div>`}).join(``)||`<div class="dsh-exec-empty">无</div>`}function S(e,t){let n=t.tasks??[];e.taskTable.tBodies[0].innerHTML=n.map(e=>{let t=e.enabled===!0||e.enabled===`true`?`<span class="dsh-exec-on">是</span>`:`<span class="dsh-exec-off">否</span>`,n=e.todaySuccess!==void 0&&e.todayTriggered!==void 0?String(e.todaySuccess??0)+`/`+String(e.todayTriggered??0):`—`,r=typeof e.lastRun==`string`?e.lastRun:e.lastRun?JSON.stringify(e.lastRun):`—`,i=e.nextRunAt&&e.nextRunAt!==`None`?o(e.nextRunAt):`—`,s=e.error?`<td class="err">`+a(e.error)+`</td>`:`<td class="dim">—</td>`;return`<tr><td class="id">`+a(e.id)+`</td><td>`+a(e.name??``)+`</td><td>`+t+`</td><td class="mono">`+a(e.scheduleExpr??``)+`</td><td class="num">`+i+`</td><td class="num">`+n+`</td><td class="num">`+o(r)+`</td>`+s+`</tr>`}).join(``)||`<tr><td colspan="8" class="dsh-exec-empty">无</td></tr>`}function C(e,t){_(e,t),v(e,t),y(e,t),b(e,t),x(e,t),S(e,t)}let w=!1;function T(){let e={boardOpen:!1},i=()=>{e.boardOpen=!0,o()},a=()=>{e.boardOpen=!1,o()},o=()=>{if(e.boardOpen){for(let e of n)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(t,``),document.dispatchEvent(new CustomEvent(r,{detail:`dashboard-execution`}))}else document.documentElement.removeAttribute(t)};return{isActive:()=>e.boardOpen,toggle:()=>{e.boardOpen?a():i()},getSnapshot:()=>e,openBoard:i,closeBoard:a,toggleBoard:()=>{e.boardOpen?a():i()}}}function E(e){let n,i,a=0,o,s=()=>{if(i!==void 0)return;let e=document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`);e!==null&&(i=document.createElement(`div`),i.dataset.dshExecView=``,i.className=`dsh-exec-view`,e.appendChild(i),n=g(),i.appendChild(n.board),o=i.querySelector(`[data-role="refresh"]`)??void 0,o?.addEventListener(`click`,()=>{l()}),l(!0))},c=new MutationObserver(()=>{s()});c.observe(document.body,{childList:!0,subtree:!0});async function l(e=!1){if(!w){w=!0;try{let e=await fetch(`/dashboard/api/board`,{headers:{Accept:`application/json`}});if(!e.ok)throw Error(`HTTP `+e.status);let t=await e.json();if(!t.success||t.data===void 0)throw Error(t.error??`API 返回失败`);if(n===void 0)return;C(n,t.data),n.meta.textContent=`刷新于 `+new Date().toLocaleTimeString()+` · 数据 `+(t.data.fetchedAt??``),n.banner.classList.remove(`show`)}catch(e){if(n===void 0)return;n.banner.innerHTML=`⚠ 无法连接看板 API：`+String(e&&e.message?e.message:e)+` — 请检查 :13080 与插件状态`,n.banner.classList.add(`show`)}finally{w=!1}}}let u=t=>{t.detail!==`dashboard-execution`&&e.getSnapshot().boardOpen&&e.closeBoard()},d=t=>{if(!e.getSnapshot().boardOpen)return;let n=t.target;n!==null&&n.closest(`[data-dsh-exec-entry]`)===null&&n.closest(`[class*="sessionRow"], [class*="projectRow"], [class*="searchResultRow"], [class*="searchResultWorkspace"], [class*="newSession"]`)!==null&&e.closeBoard()};document.addEventListener(`click`,d,!0),document.addEventListener(r,u);let f=()=>{a!==0&&window.clearInterval(a),a=window.setInterval(()=>{l()},3e4)},p=()=>{a!==0&&(window.clearInterval(a),a=0)},m=()=>{document.hidden?p():(f(),l())};return document.addEventListener(`visibilitychange`,m),s(),f(),()=>{document.removeEventListener(`click`,d,!0),document.removeEventListener(r,u),document.removeEventListener(`visibilitychange`,m),c.disconnect(),p(),document.documentElement.removeAttribute(t),i?.remove(),i=void 0,n=void 0}}function D(e){let t,n=()=>{let t=document.createElement(`button`);return t.type=`button`,t.className=`dsh-exec-entry`,t.dataset.dshExecEntry=``,t.setAttribute(`aria-label`,`执行看板`),t.title=`双线执行确认看板 (dashboard-execution)`,t.innerHTML=`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/></svg><span class="dsh-exec-entry-label">执行看板</span>`,t.addEventListener(`click`,t=>{t.preventDefault(),t.stopPropagation(),e.toggle()}),t},r=()=>{let e=i();if(e===void 0)return!1;if(e.querySelector(`[data-dsh-exec-entry]`)!==null){let n=e.querySelector(`[data-dsh-exec-entry]`);return n!==void 0&&t===void 0&&(t=n),!0}let r=n(),a=e.querySelector(`[class*="logoRow"]`);return a!==null&&a.nextSibling!==null?e.insertBefore(r,a.nextSibling):e.prepend(r),t=r,!0};r();let a=new MutationObserver(()=>{(t===void 0||!document.contains(t)||t.parentElement===null)&&r()});a.observe(document.body,{childList:!0,subtree:!0});let o=window.setInterval(()=>{(t===void 0||!document.contains(t))&&r()},5e3),s=()=>{t?.setAttribute(`data-active`,e.isActive()?`true`:`false`)},c=window.setInterval(s,1e3);return s(),()=>{a.disconnect(),window.clearInterval(o),window.clearInterval(c),t?.remove(),t=void 0}}const O=[];function k(t){try{e();let n=T(),r=[];try{r.push(D(n)),r.push(E(n))}catch(e){console.error(`[dashboard-execution] mount failed:`,e)}t.effect?.(()=>()=>{for(let e of r.splice(0))try{e()}catch{}},`dashboard-execution: client mount`)}catch(e){console.error(`[dashboard-execution] client half failed to start:`,e)}}exports.apply=k,exports.inject=O,exports.name=`@pi-investment/dashboard-execution/client`;