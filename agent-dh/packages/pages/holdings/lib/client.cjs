Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});const e=`[data-dsh-hld-view]`,t=`data-dsh-hld-active`,n=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-exec-active`],r=`dsh-panel-activate`;function i(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function a(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}const o=e=>String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e),s=(e,t=2)=>(Number.isFinite(Number(e))?Number(e):0).toLocaleString(`zh-CN`,{minimumFractionDigits:t,maximumFractionDigits:t}),c=e=>{let t=Number(e)||0;return(t>0?`+`:``)+t.toLocaleString(`zh-CN`,{maximumFractionDigits:2})},l=e=>{let t=Number(e)||0;return(t>0?`+`:``)+t.toFixed(2)+`%`},u=e=>{let t=Number(e)||0;return t>1e-4?`up`:t<-1e-4?`down`:`flat`},d=e=>{if(!e)return`—`;let t=new Date(e);if(Number.isNaN(t.getTime()))return String(e).slice(11,19);let n=e=>String(e).padStart(2,`0`);return n(t.getMonth()+1)+`-`+n(t.getDate())+` `+n(t.getHours())+`:`+n(t.getMinutes())},f=e=>{let t=e.context;if(typeof t==`string`)return t;try{return JSON.stringify(t??``)}catch{return``}},p={600519:`贵州茅台`,"000858":`五粮液`,"000568":`泸州老窖`,600809:`山西汾酒`,600600:`青岛啤酒`,601288:`农业银行`,601398:`工商银行`,601939:`建设银行`,601988:`中国银行`,600036:`招商银行`,"000001":`平安银行`,6e5:`浦发银行`,601166:`兴业银行`,600016:`民生银行`,601328:`交通银行`,601318:`中国平安`,601601:`中国太保`,601628:`中国人寿`,600030:`中信证券`,601688:`华泰证券`,600900:`长江电力`,601857:`中国石油`,600028:`中国石化`,601088:`中国神华`,600019:`宝钢股份`,600585:`海螺水泥`,601668:`中国建筑`,601390:`中国中铁`,601766:`中国中车`,600104:`上汽集团`,601633:`长城汽车`,601238:`广汽集团`,"000333":`美的集团`,"000651":`格力电器`,600690:`海尔智家`,300750:`宁德时代`,"002594":`比亚迪`,601012:`隆基绿能`,600438:`通威股份`,"002460":`赣锋锂业`,600276:`恒瑞医药`,603259:`药明康德`,"000538":`云南白药`,300760:`迈瑞医疗`,"002415":`海康威视`,"000063":`中兴通讯`,"002230":`科大讯飞`,"002475":`立讯精密`,"002241":`歌尔股份`,688981:`中芯国际`,688111:`金山办公`,603986:`兆易创新`,"002049":`紫光国微`,300782:`卓胜微`,"002371":`北方华创`,688012:`中微公司`,"002463":`沪电股份`,"002815":`崇达技术`,"002050":`三花智控`,"000807":`云铝股份`,601138:`工业富联`,"002352":`顺丰控股`,601888:`中国中免`,"000725":`京东方A`,"002714":`牧原股份`,300498:`温氏股份`,601111:`中国国航`,600029:`南方航空`,600150:`中国船舶`,601989:`中国重工`,600893:`航发动力`,"002179":`中航光电`,300059:`东方财富`,600031:`三一重工`};function m(e){if(e.enabled===!1)return!1;if(e.expires_at){let t=new Date(e.expires_at).getTime();if(Number.isFinite(t)&&t<=Date.now())return!1}return!0}function h(e){let t={};for(let n of e){let e=f(n),r=/([\u4e00-\u9fa5]{2,10})\s*\(?0*(\d{6})\)?/g,i;for(;(i=r.exec(e))!==null;)t[i[2]]=i[1]}return t}function g(e,t){if(!e)return`—`;let n=String(e).replace(/\D/g,``).slice(-6);return p[n]??t[n]??n}const _=e=>String(e??``).replace(/\D/g,``);function v(e){return/^(30|68)/.test(e)?-.1:-.08}function y(e,t=`current`,n=0){let r=e.summary??{},i=Array.isArray(e.accounts)?e.accounts:[],a=e.currentAccount??``,s=Array.isArray(e.positions)?e.positions:[],c=Array.isArray(e.watchRules)?e.watchRules:[],l=h(c),u=c.filter(e=>{let t=e.account;return t!=null&&t!==``&&t!==a?!1:m(e)}),f=i.length>1?`<div class="dsh-hld-acct">
         <label for="dsh-hld-account-switch">账户</label>
         <select id="dsh-hld-account-switch"
           onchange="window.__dshHldSwitchAccount && window.__dshHldSwitchAccount(this.value)">
           ${i.map(e=>`<option value="${o(e.account_name)}" ${e.account_name===a?`selected`:``}>${o(e.display_name||e.account_name)}（${e.positions_count??0} 仓）</option>`).join(``)}
         </select>
       </div>`:``,p=r.lastUpdated?d(r.lastUpdated):`—`,g=r.totalValue?r.dailyChange/(r.totalValue-r.dailyChange)*100:0;return`<div class="dsh-hld-board">
  <div class="dsh-hld-topbar">
    <div class="dsh-hld-title">
      <h1>账户持仓看板</h1>
      <div class="sub">只读监控 · 交易操作由 agent 执行</div>
    </div>
    <div class="dsh-hld-tools">
      ${f}
      <div class="dsh-hld-updated">更新于 <b>${o(p)}</b></div>
      <button type="button" class="dsh-hld-refresh" onclick="window.__dshHldRefresh && window.__dshHldRefresh()">↻ 刷新</button>
    </div>
  </div>

  ${b(r,g,e)}

  ${x(s,l,u)}

  ${C(e)}

  ${T(e,n)}

  ${N(e)}

  ${P(e,t)}
</div>`}function b(e,t,n){let r=u(e.dailyChange),i=u(e.totalPnl),a=Number(n.compliance?.cashRatio??(e.totalValue?e.cash/e.totalValue*100:0)),o=Number(n.compliance?.maxSingleStock??0),d=Number(n.compliance?.maxIndustry??0),f=Number(n.compliance?.maxDrawdown60d??0),p=(n.positions??[]).filter(e=>Number(e.profitLossPct)<=v(e.symbol)+1).length,m=(e,t,n=!1)=>`<span class="dsh-hld-chip ${e?`ok`:n?`warn`:`bad`}">${t} ${e?`✅`:`⚠️`}</span>`;return`<div class="dsh-hld-summary">
  <div class="dsh-hld-sum-top">
    <div class="dsh-hld-sum-pnl">
      <div class="n">今日盈亏</div>
      <div class="v ${r}">${c(e.dailyChange)} <small>${l(t)}</small></div>
    </div>
    <div class="dsh-hld-sum-pnl right">
      <div class="n">持仓盈亏</div>
      <div class="v ${i}">${c(e.totalPnl)} <small>${l(e.totalPnlPct)}</small></div>
    </div>
  </div>
  <div class="dsh-hld-sum-assets">
    <div class="asset-item"><div class="n">总资产</div><div class="v">${s(e.totalValue)}</div></div>
    <div class="asset-item"><div class="n"><span class="legend-dot" style="background:#f56c6c"></span>持仓市值（${e.positions??0} 只）</div><div class="v">${s(e.totalMarketValue)}</div></div>
    <div class="asset-item"><div class="n"><span class="legend-dot" style="background:#e6a23c"></span>可用资金</div><div class="v">${s(e.cash)}</div></div>
  </div>
  <div class="dsh-hld-risk">
    ${m(a>=10,`现金占比 `+a.toFixed(1)+`% · 铁律 ≥10%`)}
    ${m(o<=20,`单股最大 `+o.toFixed(2)+`% · 上限 20%`)}
    ${m(d<=40,`单行业最大 `+d.toFixed(1)+`% · 上限 40%`)}
    ${f>8?m(!1,`60日回撤 -`+f.toFixed(1)+`%（熔断线 -8%）`,!0):m(!0,`60日回撤 `+f.toFixed(1)+`%（熔断线 -8%）`)}
    ${p>0?m(!1,p+` 只临近止损`,!0):m(!0,`无临近止损`)}
  </div>
</div>`}function x(e,t,n){let r=new Set(n.map(e=>_(e.symbol))),i=e.map(e=>S(e,t,r)).join(``),a=e.length===0?`<tr><td colspan="7" class="dsh-hld-empty">当前账户暂无持仓 — 空仓等待信号是正确决策</td></tr>`:``;return`<div class="dsh-hld-card">
  <div class="hd"><span class="t">持仓明细（${e.length}）</span><span class="more">买卖点参考 = 止损铁律 + 止盈参考(+10%) · 具体交易由 agent 执行</span></div>
  <div class="tblwrap"><table>
    <tr>
      <th>名称/代码</th><th class="r">市值/股数</th><th class="r">现价/成本</th>
      <th class="r">今日盈亏</th><th class="r">持仓盈亏</th><th>买卖点参考</th><th>盯盘</th>
    </tr>
    ${i}${a}
  </table></div>
</div>`}function S(e,t,n){let r=g(e.symbol,t),i=_(e.symbol),a=v(i),d=(Number(e.avgCost)||0)*(1+a),f=(Number(e.avgCost)||0)*1.1,p=(Number(e.profitLossPct)||0)<=a+1,m=e.currentPrice?(Number(e.currentPrice)-d)/Number(e.currentPrice)*100:0,h=n.has(i),y=p?`<span class="dsh-hld-tag trig">⚠️ 临近止损</span>`:h?`<span class="dsh-hld-tag on">已挂盯盘</span>`:`<span class="dsh-hld-tag off">—</span>`,b=p?`<span class="dsh-hld-sl">⚠️ 临近止损 ${s(d)}（${Math.abs(a*100)}%）</span><br><span class="dsh-hld-s">反弹减 / 止盈参考 ${s(f)}（+10%）</span>`:`<span class="dsh-hld-sl">止损 ${s(d)}（-${Math.abs(a*100)}% 档）</span><br><span class="dsh-hld-s">止盈参考 ${s(f)}（+10%）</span>`;return`<tr>
  <td><span class="sec-name">${o(r)}</span> <span class="sec-code">${o(i)}</span></td>
  <td class="r">${s(e.currentValue,0)}<span class="sub">${e.quantity??0} 股 · 可卖 ${e.sharesAvailable??0}</span></td>
  <td class="r">${s(e.currentPrice)}<span class="sub">成本 ${s(e.avgCost)}</span></td>
  <td class="r ${u(e.profitToday)}">${c(e.profitToday)}<span class="sub">今日</span></td>
  <td class="r ${u(e.profitLoss)}">${c(e.profitLoss)}<span class="sub">${l(e.profitLossPct)}</span></td>
  <td class="bp">
    ${b}
    <span class="src">依据：成本 ${s(e.avgCost)} · 距止损线 +${Math.max(m,0).toFixed(1)}% · 铁律优先不补仓</span>
  </td>
  <td>${y}</td>
</tr>`}function C(e){let t=Array.isArray(e.todayTrades)?e.todayTrades:[];if(t.length===0)return`<div class="dsh-hld-card">
      <div class="hd"><span class="t">今日自动交易（0）</span><span class="more">agent 的买卖动作都会显示在这里</span></div>
      <div class="dsh-hld-emptybox">今日尚无自动交易 — 没有信号时空仓等待是正确决策</div>
    </div>`;let n={BUY:{tag:`buy`,text:`买入`},SELL:{tag:`sell`,text:`卖出`}},r={filled:`✅ 已成交`,partial:`⏳ 部分成交`,pending:`⏳ 待执行`,rejected:`❌ 已拒绝`,cancelled:`— 已撤单`},i=h(e.watchRules??[]),a=t.map(e=>{let t=n[String(e.action??``).toUpperCase()]??{tag:`off`,text:String(e.action??``)},a=Number(e.filled_price)||Number(e.price),c=a*(e.shares??0),l=r[String(e.status??``)]??String(e.status??``);return`<tr>
        <td><span class="dsh-hld-tag ${t.tag}">${t.text}</span></td>
        <td><span class="sec-name">${o(g(e.symbol,i))}</span> <span class="sec-code">${o(_(e.symbol))}</span></td>
        <td class="r">${s(a)}<span class="sub">× ${e.shares??0} 股</span></td>
        <td class="r">${s(c)}</td>
        <td>${o(String(e.reason??`—`).slice(0,64))}</td>
        <td>${l}</td>
        <td class="dim">${o(d(e.created_at))}</td>
      </tr>`}).join(``);return`<div class="dsh-hld-card">
  <div class="hd"><span class="t">今日自动交易（${t.length}）</span><span class="more">agent 已完成 / 进行中的自动交易</span></div>
  <div class="tblwrap"><table>
    <tr><th>方向</th><th>股票</th><th class="r">成交价</th><th class="r">金额</th><th>理由</th><th>状态</th><th>时间</th></tr>
    ${a}
  </table></div>
</div>`}function w(e,t,n){if(t<=9){let r=``;for(let i=0;i<t;i++)r+=n(i,String(i+1),i===e);return r}let r=[...new Set([0,t-1,e-1,e,e+1].filter(e=>e>=0&&e<t))].sort((e,t)=>e-t),i=``,a=-2;for(let t of r)t-a>1&&(i+=`<span class="gap">…</span>`),i+=n(t,String(t+1),t===e),a=t;return i}function T(e,t){let n=Array.isArray(e.tradeHistory)?e.tradeHistory:[],r=Math.max(1,Math.ceil(n.length/8)),i=Math.min(Math.max(0,Math.trunc(Number(t)||0)),r-1);if(n.length===0)return`<div class="dsh-hld-card" id="dsh-hld-hx">
      <div class="hd"><span class="t">历史交易（0）</span><span class="more">${o(String(e.currentAccount??``))} · agent 成交后自动归档到此</span></div>
      <div class="dsh-hld-emptybox">该账户暂无历史交易记录</div>
    </div>`;let a=n.slice(i*8,(i+1)*8),f=h(e.watchRules??[]),p={BUY:{tag:`buy`,text:`买入`},SELL:{tag:`sell`,text:`卖出`}},m=a.map(e=>{let t=String(e.action??``).toUpperCase(),n=p[t]??{tag:`off`,text:String(e.action??``)},r=Number(e.filled_price)||Number(e.price),i=Number(e.amount)||r*(e.shares??0),a=Number(e.realized_pnl),m=t===`SELL`&&Number.isFinite(a),h=m&&a!==0?u(a):`flat`,v=Number(e.realized_pnl_rate),y=m&&Number.isFinite(v)&&v!==0?`<span class="sub">`+l(v)+`</span>`:``,b=String(e.reason??`—`);return`<tr>
        <td><span class="dsh-hld-tag ${n.tag}">${n.text}</span></td>
        <td><span class="sec-name">${o(g(e.symbol,f))}</span> <span class="sec-code">${o(_(e.symbol))}</span></td>
        <td class="r">${s(r)}<span class="sub">× ${e.shares??0} 股</span></td>
        <td class="r">${s(i)}</td>
        <td class="r ${h}">${m?c(a)+y:`<span class="dim">—</span>`}</td>
        <td title="${o(b)}">${o(b.slice(0,60))}</td>
        <td class="dim">${o(d(e.created_at))}</td>
      </tr>`}).join(``),v=r<=1?``:`<div class="dsh-hld-pg">
        <button type="button" class="dsh-hld-pgb"${i===0?` disabled`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${i-1})">‹ 上一页</button>
        <span class="dsh-hld-pg-nums">${w(i,r,(e,t,n)=>`<button type="button" class="dsh-hld-pgb${n?` act`:``}"${e===i?` aria-current="page"`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${e})">${t}</button>`)}</span>
        <button type="button" class="dsh-hld-pgb"${i>=r-1?` disabled`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${i+1})">下一页 ›</button>
        <span class="dsh-hld-pg-cnt">第 ${i+1}/${r} 页 · 共 ${n.length} 笔</span>
      </div>`;return`<div class="dsh-hld-card" id="dsh-hld-hx">
  <div class="hd"><span class="t">历史交易（${n.length}）</span><span class="more">${o(String(e.currentAccount??``))} · agent 全部成交明细 · 倒序</span></div>
  <div class="tblwrap"><table>
    <tr><th>方向</th><th>股票</th><th class="r">成交价</th><th class="r">金额</th><th class="r">实现盈亏</th><th>理由</th><th>时间</th></tr>
    ${m}
  </table></div>
  ${v}
</div>`}function E(e,t,n,r,i){let a=e=>e.account??``,s=e.filter(e=>m(e)),c=s.filter(e=>a(e)===``),l=s.filter(e=>a(e)===n).concat(c),u=[];for(let e of s){let t=a(e);t!==``&&t!==n&&!u.includes(t)&&u.push(t)}let d=new Map;for(let e of r)d.set(e.account_name,e.display_name||e.account_name);let p=e=>d.get(e)??e,h=new Set([`current`,`all`,...u]).has(i)?i:`current`,v=h===`all`?s:h===`current`?l:s.filter(e=>a(e)===h),y=(e,t,n,r)=>`<button type="button" class="dsh-hld-wtab${h===e?` act`:``}" data-wkey="${e}" title="${o(r)}" onclick="window.__dshHldWatchTab && window.__dshHldWatchTab('${e.replace(/'/g,``)}')">${o(t)}<i class="c">${n}</i></button>`,b=[y(`current`,`本账户`,l.length,`当前账户归属 + 通用观察（${p(n)}）`)];for(let e of u)b.push(y(e,p(e),s.filter(t=>a(t)===e).length,`归属账户：${e}`));b.push(y(`all`,`全部`,s.length,`全部账户规则汇总`));let x=v.map(e=>{let r=f(e),i=r.replace(/\s+/g,` `).trim(),s=(e.conditions??[]).map(F).filter(Boolean),c=s.slice(0,3).join(` <span class="dim">·</span> `)+(s.length>3?` <span class="dim">+`+(s.length-3)+`</span>`:``),l=I(r),u=a(e),d=u===``?`off`:u===n?`on`:`oth`,m=u===``?`通用观察`:u===n?`本账户`:p(u);return`<tr>
      <td><span class="sec-name">${o(g(e.symbol,t))}</span> <span class="sec-code">${o(_(e.symbol))}</span></td>
      <td><span class="dsh-hld-tag ${l.cls}">${l.text}</span></td>
      <td class="cond">${c||`<span class="dim">—</span>`}</td>
      <td>${e.enabled?`<span class="dsh-hld-tag on">监控中</span>`:`<span class="dsh-hld-tag off">已停用</span>`}</td>
      <td><span class="dsh-hld-tag ${d}" title="${o(u||`通用观察`)}">${o(m)}</span></td>
      <td class="ctx" title="${o(i.slice(0,400))}">${o(i.slice(0,44))}${i.length>44?`…`:``}</td>
    </tr>`}).join(``),S=h===`current`?`本账户暂无归属/通用观察规则 — 开仓后 agent 会自动挂上止损/止盈盯盘；可切换上方其他账户 / 全部 tab`:h===`all`?`暂无任何盯盘规则`:`该账户暂无归属盯盘规则`,C=v.length===0?`<tr class="dsh-hld-empty"><td colspan="6">`+S+`</td></tr>`:``;return`<div class="dsh-hld-card" id="dsh-hld-watch">
  <div class="hd"><span class="t">盯盘中心（${s.length}）</span><span class="more">账户归属 tab · 默认本账户（含通用观察）· 触发后由 agent 决策，无需人工盯盘</span></div>
  <div class="dsh-hld-wtabs">${b.join(``)}</div>
  <div class="tblwrap"><table>
    <tr><th>股票</th><th>监控性质</th><th>触发条件</th><th>状态</th><th>归属账户</th><th>监控摘要</th></tr>
    ${x}${C}
  </table></div>
</div>`}const D={"v13-simulation-trading":`模拟交易执行`,v13_daily_check:`模拟交易执行`,"v13-risk-check":`风控检查`,v13_risk_check:`风控检查`,"v13-verification":`验证裁决`,v13_verification:`验证裁决`,"v13-weekly-report":`每周报告`,v13_weekly_report:`每周报告`,"v14-simulation-trading":`模拟交易执行`,v14_daily_check:`模拟交易执行`,morning_ai_analysis:`晨间 AI 分析`,realtime_quick_check:`盘中快速检查`,daily_ai_review:`每日 AI 复盘`,daily_recall_audit:`每日回查审计`,weekly_evolution:`周度策略进化`,weekly_memory_distill:`周度记忆蒸馏`,weekly_tool_roi_review:`周度工具 ROI 复盘`,"pre-market-routine":`盘前例行检查`,"afternoon-open-check-live":`午后开盘检查`,"post-market-routine-live":`盘后例行复盘`,"m4-circuit-breaker-live":`M4 回撤熔断巡检`,"weekly-report-m6":`M6 学习飞轮周报`,"agent-brain-morning-analysis":`晨间 AI 分析`,"agent-brain-realtime-check":`盘中快速检查`,"agent-brain-daily-review":`每日 AI 复盘`,"agent-brain-daily-audit":`每日回查审计`,"agent-brain-weekly-evolution":`周度策略进化`,"agent-brain-weekly-distill":`周度记忆蒸馏`,"agent-brain-weekly-roi":`周度工具 ROI 复盘`},O={success:{cls:`ok`,text:`成功`},failed:{cls:`bad`,text:`失败`},skipped:{cls:`wait`,text:`跳过`},pending:{cls:`on`,text:`待执行`},unknown:{cls:`off`,text:`未知`},"":{cls:`off`,text:`从未运行`}};function k(e){let t=String(e??``).trim().split(/\s+/);if(t.length!==5)return String(e||`—`);let[,n,,,r]=t,i=(String(n).padStart(2,`0`)||`--`)+`:`+(t[0].padStart(2,`0`)||`--`),a=String(r);return!a||a===`*`?`每天 `+i:/^\d+$/.test(a)?`周`+`日一二三四五六`[Number(a)%7]+` `+i:/^1-5$/.test(a)?`工作日 `+i:/^(0|6)(,(0|6))?$/.test(a)?`周末 `+i:/^1-5$/.test(a.replace(/,/g,`-`))?`工作日 `+i:a+` `+i}const A={v2:`quantsys-v2 引擎 cron 自动执行（不走 agent）`,ts:`fin-agent（agent-ts）智能体执行`,dh:`agent-dh · investor 例行执行`};function j(e){return e!==`v2`&&e!==`ts`&&e!==`dh`?`<span class="dim">—</span>`:`<span class="dsh-hld-echip `+e+`" title="`+o(A[e]??``)+`">`+e+`</span>`}function M(e,t=!0,n=!1,r=``){let i=D[String(e.name)]??D[String(e.command)]??String(e.name||e.command||`?`),a=k(e.scheduleExpr),s=O[String(e.lastStatus??``)]??O.unknown,c=e.lastAt?d(e.lastAt):`—`,l=e.nextRunAt?d(e.nextRunAt):`—`,u=e.todayTriggered>0?e.todaySuccess+`/`+e.todayTriggered:`—`,f=e.enabled,p=f?s.cls:`off`,m=f?s.text:`未启用`,h=[String(e.name||``),String(e.command||``),e.lastError?`最近错误: `+String(e.lastError).slice(0,120):``].filter(Boolean).join(` · `),g=f&&String(e.lastStatus??``)===`failed`,_=t?`<td class="r">${u}</td><td class="dim">${l}</td>`:n?`<td class="op">${g?`<button type="button" class="dsh-hld-solve" data-solve-task="${o(String(e.name||``))}"
              title="投递给 investor 窗口排查处置此任务" onclick="window.__dshHldSolveTask && window.__dshHldSolveTask(this)">我来解决</button>`:`<span class="dim">—</span>`}</td>`:``;return`<tr title="${o(h)}">
    <td><span class="dsh-hld-tag ${p}">${m}</span></td>
    <td>${o(i)}<span class="sub dim"> ${o(e.command)}</span></td>
    <td class="exe">${j(r)}</td>
    <td>${o(a)}</td>
    <td class="dim">${c}</td>
    ${_}
  </tr>`}function N(e){let t=e.automation;if(!t||t.tasks.length===0)return``;let n=t.tasks,r=t.engine===!0,i=r?`引擎定时任务`:`执行例行任务`,a=t.executor?` · `+t.executor:``,s=t.note?`<div class="dsh-hld-auto-note">⚠️ ${o(t.note)}</div>`:``,c=(e.watchRules??[]).filter(e=>e.account===t.accountName&&m(e)).length,l=n.map(e=>r?M(e,!0,!1,t.executorCode):M(e,!1,!0,t.executorCode)).join(``),u=r?`<th class="r">今日 成/触</th><th>下次运行</th>`:`<th>处理</th>`;return`<div class="dsh-hld-card dsh-hld-auto">
  <div class="hd"><span class="t">账户自动化流程</span>
    <span class="more">${o(t.displayName)}${a} · ${n.length} 个${i} · 盯盘规则 ${c} 条（见下方盯盘中心）</span></div>
  ${s}
  <div class="tblwrap"><table class="dsh-hld-autotbl">
    <tr><th>状态</th><th>任务</th><th class="exe">执行</th><th>计划时刻</th><th>上次运行</th>${u}</tr>
    ${l}
  </table></div>
</div>`}function P(e,t){let n=h(e.watchRules??[]);return E(e.watchRules??[],n,e.currentAccount??``,Array.isArray(e.accounts)?e.accounts:[],t)}function F(e){let t=e.params;if(e.type===`price_break`||String(e.operator||``).toLowerCase().includes(`price`)){if(t&&t.price!==void 0&&t.price!==null){let e=t.direction===`above`?`突破`:t.direction===`below`?`跌破`:`触碰`;return`<span class="cond-${t.direction===`above`?`up`:`down`}">${e}${s(t.price)}</span>`}if(e.threshold!==void 0&&e.threshold!==null)return`价格 `+e.threshold}return e.threshold!==void 0&&e.threshold!==null&&e.operator?String(e.operator||e.type).toUpperCase()+` `+e.threshold:String(e.type??e.operator??`条件`)}function I(e){return/止损|风控|破位|减仓保护/.test(e)?{cls:`warn`,text:`止损监控`}:/买入|低吸|介入|加仓|建仓|补仓/.test(e)?{cls:`buy`,text:`买入提醒`}:/卖出|止盈|减仓|高抛|目标价/.test(e)?{cls:`sell`,text:`卖出提醒`}:{cls:`on`,text:`常规监控`}}function L(e){return[`.`+e+`-solve { flex:none; border:1px solid #c6e2ff; background:#ecf5ff; color:#409eff; border-radius:5px; padding:2px 9px; font-size:11.5px; line-height:1.7; cursor:pointer; white-space:nowrap; vertical-align:middle; }`,`.`+e+`-solve:hover { background:#d9ecff; border-color:#79bbff; }`,`.`+e+`-solve:active { background:#c6e2ff; }`,`.`+e+`-solvepop { position:fixed; z-index:9999; min-width:232px; max-width:300px; background:var(--panel,#fff); border:1px solid var(--border,#e4e7ed); border-radius:8px; box-shadow:0 6px 22px rgba(0,0,0,.16); padding:6px; font-size:12.5px; color:var(--body,#606266); }`,`.`+e+`-solvepop-head { padding:4px 8px 7px; color:var(--text,#303133); font-weight:600; font-size:12px; border-bottom:1px solid var(--line,#ebeef5); margin-bottom:4px; }`,`.`+e+`-solvepop-list { display:flex; flex-direction:column; max-height:264px; overflow-y:auto; }`,`.`+e+`-solvepop-item { border:none; background:transparent; text-align:left; padding:5px 8px; border-radius:5px; cursor:pointer; color:var(--body,#606266); font:inherit; font-size:12.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }`,`.`+e+`-solvepop-item:hover { background:var(--hover,rgba(128,128,128,.12)); }`,`.`+e+`-solvepop-item.cur { color:#409eff; font-weight:600; }`,`.`+e+`-solvepop-cancel { width:100%; margin-top:4px; border:none; background:transparent; color:var(--dim,#909399); font:inherit; font-size:12px; padding:4px; cursor:pointer; border-top:1px solid var(--line,#ebeef5); }`,`.`+e+`-solvepop-cancel:hover { color:var(--text,#303133); }`,`.`+e+`-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }`,`.`+e+`-toast.ok { background:#529b2e; }`,`.`+e+`-toast.err { background:#e64545; }`,`.`+e+`-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }`].join(`
`)}function R(e){let t=`dsh-solve-styles-`+e,n=document.getElementById(t);if(n!==null&&n.tagName===`STYLE`)return()=>n.remove();let r=document.createElement(`style`);return r.id=t,r.textContent=L(e),(document.head??document.documentElement).appendChild(r),()=>{document.getElementById(t)?.remove()}}function z(e){let t=e.prefix,n,r,i=()=>{r?.(),r=void 0,n!==void 0&&(n.remove(),n=void 0)},a=(e,n)=>{let r=document.createElement(`div`);r.className=t+`-toast `+(n?`ok`:`err`),r.textContent=e,document.body.appendChild(r),window.setTimeout(()=>{r.classList.add(`out`),window.setTimeout(()=>r.remove(),350)},4200)},o=async(t,n,r)=>{let i=e.current();try{let o=await fetch(e.endpoint,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({kind:t,task:t===`task`?n:void 0,err:t===`error`?n:void 0,from_session:i||void 0,to_session:r})}),s=await o.json().catch(()=>null);if(s===null||s.success!==!0){a(`投递失败：`+String(s?.error??`HTTP `+o.status),!1);return}let c=s.data;a(c?.delivered===!0?`✓ `+String(c?.note??`已投递`):`⚠ `+String(c?.error??s.error??`投递失败`),c?.delivered===!0)}catch(e){a(`请求异常：`+String(e instanceof Error?e.message:e),!1)}};return{toast:a,openPicker:(s,c,l)=>{let u=e.resolveSnapshot(c,l);if(u===null){a(`⚠ 数据已刷新，请重试`,!1);return}i();let d=e.candidates();if(d.length===0){o(u.kind,u.snap);return}let f=document.createElement(`div`);f.className=t+`-solvepop`;let p=document.createElement(`div`);p.className=t+`-solvepop-head`,p.textContent=`投递给窗口排查处置`,f.appendChild(p);let m=document.createElement(`div`);m.className=t+`-solvepop-list`;for(let e of d){let n=document.createElement(`button`);n.type=`button`,n.className=t+`-solvepop-item`+(e.current?` cur`:``),n.textContent=(e.current?`● `:`○ `)+e.label,n.addEventListener(`click`,()=>{i(),o(u.kind,u.snap,e.sid)}),m.appendChild(n)}f.appendChild(m);let h=document.createElement(`button`);h.type=`button`,h.className=t+`-solvepop-cancel`,h.textContent=`取消`,h.addEventListener(`click`,i),f.appendChild(h);let g;try{g=typeof e.host==`function`?e.host():e.host}catch{g=void 0}(g??document.body).appendChild(f),n=f;let _=s.getBoundingClientRect(),v=40+d.length*30+32,y=_.bottom+6;y+v>window.innerHeight&&(y=Math.max(6,_.top-v-6)),f.style.position=`fixed`,f.style.left=Math.min(_.left,Math.max(6,window.innerWidth-280))+`px`,f.style.top=y+`px`;let b=e=>{let t=e.target;t!==null&&f.contains(t)||(document.removeEventListener(`click`,b,!0),r=void 0,i())};document.addEventListener(`click`,b,!0),r=()=>document.removeEventListener(`click`,b,!0)},close:i}}function B(){let i=!1,a=`agent_virtual`,o=`current`,s=0,c,l,u=()=>{if(!i){i=!0,console.log(`[dashboard-holdings] opening board`),document.documentElement.setAttribute(t,``);for(let e of n)document.documentElement.removeAttribute(e);window.dispatchEvent(new CustomEvent(r,{detail:`dashboard-holdings`})),h(),_(a)}},d=()=>{i&&(i=!1,console.log(`[dashboard-holdings] closing board`),document.documentElement.removeAttribute(t),g())},f=()=>{i?d():u()},p=()=>{console.log(`[dashboard-holdings] manual refresh`),_(a)},m=e=>{console.log(`[dashboard-holdings] switching account to`,e),a=e,o=`current`,s=0,_(e)},h=()=>{g(),l=window.setInterval(()=>{i&&_(a)},15e3)},g=()=>{l!==void 0&&(clearInterval(l),l=void 0)},_=async e=>{try{let t=`/dashboard/api/holdings?account=${encodeURIComponent(e)}`,n=await(await fetch(t)).json();if(!n.success)throw Error(n.error||`Unknown error`);let r=n.data;v(r)}catch(e){console.error(`[dashboard-holdings] fetch failed:`,e),b(String(e))}},v=t=>{c=t;let n=document.querySelector(e);n&&(n.innerHTML=y(t,o,s))},b=t=>{let n=document.querySelector(e);n&&(n.innerHTML=`
      <div class="dsh-hld-board">
        <div class="dsh-hld-wrap">
          <div class="dsh-hld-head">
            <h1 class="dsh-hld-title">持仓看板</h1>
          </div>
          <div class="dsh-hld-banner show">
            数据加载失败: ${t}
          </div>
        </div>
      </div>
    `)},x=e=>{let t=String(e||`current`);if(t===o||(o=t,!c))return;let n=document.getElementById(`dsh-hld-watch`);if(n===null){v(c);return}let r=document.createElement(`template`);r.innerHTML=P(c,o);let i=r.content.firstElementChild;if(i===null){v(c);return}n.replaceWith(i)},S=e=>{let t=c?.tradeHistory?.length??0,n=Math.max(1,Math.ceil(t/8)),r=Math.max(0,Math.min(Math.trunc(Number(e)||0),n-1));if(r===s||(s=r,!c))return;let i=document.getElementById(`dsh-hld-hx`);if(i===null){v(c);return}let a=document.createElement(`template`);a.innerHTML=T(c,s);let o=a.content.firstElementChild;if(o===null){v(c);return}i.replaceWith(o)},C=()=>{let e=window;try{return String((e.__dshHldSessions??e.__dshHldCtx?.sessions)?.list?.getSnapshot?.().current??``)}catch{return``}},w=z({endpoint:`/dashboard/api/holdings/solve`,prefix:`dsh-hld`,candidates:()=>{let e=window,t=[];try{let n=(e.__dshHldSessions??e.__dshHldCtx?.sessions)?.list?.getSnapshot?.(),r=Array.isArray(n?.items)?n.items:(n?.ids??[]).map(e=>({id:e,title:e})),i=new Set(e.__dshHldWorkspaces?.list?.getSnapshot?.().archivedSessionIds??e.__dshHldCtx?.workspaces?.list?.getSnapshot?.().archivedSessionIds??[]),a=C();for(let e of r){let n=String(e?.id??``);if(!n||i.has(n))continue;let r=!!e?.blank,o=String(e?.origin??``);if(r||o.startsWith(`subagent`))continue;let s=String(e?.title??e?.displayTitle??``).slice(0,42);t.push({sid:n,label:s||n,current:n===a})}}catch{}return t},current:C,resolveSnapshot:(e,t)=>{if(e!==`task`)return null;let n=c?.automation;if(!n||n.engine===!0)return null;let r=(n.tasks??[]).find(e=>String(e.name)===String(t.name??``));if(!r)return null;let i=String(c?.summary?.lastUpdated??``);return{kind:`task`,snap:{name:r.name,src:String(r.command||`Agent OS 调度任务`),scheduleExpr:r.scheduleExpr,nextRunAt:r.nextRunAt,lastRun:{status:r.lastStatus,triggeredAt:r.lastAt,finishedAt:r.lastAt,err:r.lastError},todayTriggered:r.todayTriggered,todaySuccess:r.todaySuccess,fetchedAt:i,error:r.lastError}}}});return{openBoard:u,closeBoard:d,toggleBoard:f,getSnapshot:()=>({boardOpen:i}),refresh:p,switchAccount:m,watchSwitch:x,historyPageSwitch:S,solveTask:e=>{if(!e)return;let t=String(e.dataset?.solveTask??``);t&&w.openPicker(e,`task`,{name:t})}}}function V(e){let t,n=()=>{if(t!==void 0)return;let e=a();e!==void 0&&(t=document.createElement(`div`),t.setAttribute(`data-dsh-hld-view`,``),t.className=`dsh-hld-view`,e.appendChild(t),console.log(`[dashboard-holdings] board container mounted`))},i=new MutationObserver(()=>{n()});i.observe(document.body,{childList:!0,subtree:!0}),n(),window.__dshHldRefresh=()=>e.refresh(),window.__dshHldSwitchAccount=t=>e.switchAccount(t),window.__dshHldWatchTab=t=>e.watchSwitch(String(t)),window.__dshHldHistoryPage=t=>e.historyPageSwitch(Number(t)),window.__dshHldSolveTask=t=>e.solveTask(t);let o=t=>{t.detail!==`dashboard-holdings`&&e.getSnapshot().boardOpen&&e.closeBoard()};window.addEventListener(r,o);let s=t=>{if(!e.getSnapshot().boardOpen)return;let n=t.target;n!==null&&n.closest(`[data-dsh-hld-view]`)===null&&n.closest(`[class*="dsh-hld-foot"]`)===null&&n.closest(`[data-dsh-hld-entry]`)===null&&e.closeBoard()};return document.addEventListener(`click`,s,!0),()=>{window.removeEventListener(r,o),document.removeEventListener(`click`,s,!0),i.disconnect(),t!==void 0&&t.remove(),delete window.__dshHldRefresh,delete window.__dshHldSwitchAccount,delete window.__dshHldWatchTab,delete window.__dshHldHistoryPage,delete window.__dshHldSolveTask,console.log(`[dashboard-holdings] board unmounted`)}}function H(e){let t,n=()=>{let t=document.createElement(`button`);return t.type=`button`,t.className=`dsh-hld-entry`,t.dataset.dshHldEntry=``,t.setAttribute(`aria-label`,`账户持仓`),t.title=`账户持仓看板`,t.innerHTML=`<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 2 V8 L12 11"/><path d="M8 8 L4 5"/></svg><span class="dsh-hld-entry-label">账户持仓</span>`,t.addEventListener(`click`,t=>{t.preventDefault(),t.stopPropagation(),e.toggle()}),t},r=()=>{let e=i();if(e===void 0)return!1;if(e.querySelector(`[data-dsh-hld-entry]`)!==null){let n=e.querySelector(`[data-dsh-hld-entry]`);return n!==void 0&&t===void 0&&(t=n),!0}let r=n(),a=e.querySelector(`[class*="logoRow"]`);return a!==null&&a.nextSibling!==null?e.insertBefore(r,a.nextSibling):e.prepend(r),t=r,!0};r();let a=new MutationObserver(()=>{(t===void 0||!document.contains(t)||t.parentElement===null)&&r()});a.observe(document.body,{childList:!0,subtree:!0});let o=window.setInterval(()=>{(t===void 0||!document.contains(t))&&r()},5e3),s=()=>{t?.setAttribute(`data-active`,e.isActive()?`true`:`false`)},c=window.setInterval(s,1e3);return s(),()=>{a.disconnect(),window.clearInterval(o),window.clearInterval(c),t?.remove(),t=void 0}}function U(){let e=`dsh-hld-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
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

/* ================= 浅色监控主题（design page1，固定色板） ================= */
.dsh-hld-board {
  --panel:#fff; --line:#ebeef5; --border:#e4e7ed;
  --text:#303133; --body:#606266; --dim:#909399; --faint:#c0c4cc;
  --up:#f56c6c; --down:#67c23a; --warn:#e6a23c; --accent:#409eff;
  background:#f0f2f5; color:var(--body);
  font:13px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  padding:18px 22px 56px;
}
.dsh-hld-wrap { max-width: 1560px; }

/* 顶栏 */
.dsh-hld-topbar { display:flex; align-items:center; gap:18px; flex-wrap:wrap; margin-bottom:16px; }
.dsh-hld-topbar h1 { font-size:20px; font-weight:600; color:#1f2d3d; margin:0; letter-spacing:.3px; }
.dsh-hld-title .sub { color:var(--dim); font-size:12px; font-weight:400; margin-left:10px; }
.dsh-hld-tools { margin-left:auto; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
.dsh-hld-updated { color:var(--dim); font-size:12px; }
.dsh-hld-updated b { color:var(--body); font-weight:500; font-variant-numeric:tabular-nums; }
.dsh-hld-acct { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--dim); }
.dsh-hld-acct select {
  border:1px solid var(--border); border-radius:6px; background:var(--panel);
  color:var(--text); padding:4px 8px; font-size:12px; outline:none; cursor:pointer;
}
.dsh-hld-acct select:focus { border-color:var(--accent); }
.dsh-hld-refresh {
  background:var(--panel); color:var(--accent); border:1px solid var(--accent);
  border-radius:6px; padding:4px 14px; font-size:12px; cursor:pointer;
}
.dsh-hld-refresh:hover { background:#ecf5ff; }
.dsh-hld-refresh:active { opacity:.8; }

/* 摘要卡 */
.dsh-hld-summary { background:var(--panel); border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.05); margin-bottom:16px; overflow:hidden; }
.dsh-hld-sum-top { display:flex; align-items:center; padding:16px 20px 0; }
.dsh-hld-sum-pnl { padding:0 28px 14px 0; }
.dsh-hld-sum-pnl.right { border-left:1px solid var(--line); padding-left:28px; }
.dsh-hld-sum-pnl .n { font-size:13px; color:var(--dim); margin-bottom:4px; }
.dsh-hld-sum-pnl .v { font-size:26px; font-weight:600; color:var(--text); font-variant-numeric:tabular-nums; }
.dsh-hld-sum-pnl .v small { font-size:14px; font-weight:500; margin-left:6px; }
.dsh-hld-sum-pnl .v.up { color:var(--up); }
.dsh-hld-sum-pnl .v.down { color:var(--down); }
.dsh-hld-sum-pnl .v.flat { color:var(--body); }
.dsh-hld-sum-assets { display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid var(--line); }
.dsh-hld-sum-assets .asset-item { padding:12px 20px; }
.dsh-hld-sum-assets .asset-item + .asset-item { border-left:1px solid var(--line); }
.asset-item .n { font-size:12px; color:var(--dim); display:flex; align-items:center; gap:6px; }
.asset-item .v { font-size:18px; font-weight:600; color:var(--text); margin-top:2px; font-variant-numeric:tabular-nums; }
.legend-dot { display:inline-block; width:8px; height:8px; border-radius:50%; }

/* 合规风险行 */
.dsh-hld-risk { display:flex; flex-wrap:wrap; gap:8px; padding:12px 20px; border-top:1px solid var(--line); background:#fafbfc; }
.dsh-hld-chip { display:inline-flex; align-items:center; gap:5px; font-size:12px; padding:3px 10px; border-radius:999px; background:#f4f4f5; color:var(--body); }
.dsh-hld-chip.ok { background:#f0f9eb; color:#529b2e; }
.dsh-hld-chip.warn { background:#fdf6ec; color:var(--warn); }
.dsh-hld-chip.bad { background:#fef0f0; color:#f56c6c; }

/* 卡片 */
.dsh-hld-card { background:var(--panel); border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.05); margin-bottom:16px; overflow:hidden; }
.dsh-hld-card .hd { display:flex; align-items:baseline; justify-content:space-between; gap:12px; padding:13px 18px; border-bottom:1px solid #f0f0f0; flex-wrap:wrap; }
.dsh-hld-card .hd .t { font-size:15px; font-weight:600; color:var(--text); }
.dsh-hld-card .hd .more { font-size:12px; color:var(--dim); font-weight:400; }

/* 表格 */
.dsh-hld-card .tblwrap { overflow-x:auto; }
.dsh-hld-card table { width:100%; border-collapse:collapse; font-size:12px; min-width:760px; }
.dsh-hld-card th { text-align:left; color:var(--dim); font-weight:500; font-size:12px; padding:9px 14px; border-bottom:1px solid var(--line); background:#fafbfc; white-space:nowrap; }
.dsh-hld-card td { padding:10px 14px; border-bottom:1px solid var(--line); vertical-align:top; color:var(--body); }
.dsh-hld-card tr:last-child td { border-bottom:none; }
.dsh-hld-card th.r, .dsh-hld-card td.r { text-align:right; }
.dsh-hld-card td.r { font-variant-numeric:tabular-nums; }
.dsh-hld-card td .sub { display:block; color:var(--dim); font-size:11px; margin-top:2px; }
.dsh-hld-card .dim { color:var(--faint); font-size:11px; }
.dsh-hld-card td.up { color:var(--up); }
.dsh-hld-card td.down { color:var(--down); }

/* 名称 + 代码 */
.sec-name { color:var(--text); font-weight:500; white-space:nowrap; }
.sec-code { color:var(--faint); font-size:11px; margin-left:4px; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }

/* 买卖点参考列 */
.dsh-hld-card td.bp { line-height:1.9; }
.dsh-hld-sl { color:var(--warn); font-weight:600; white-space:nowrap; }
.dsh-hld-s { color:var(--down); white-space:nowrap; }
.dsh-hld-card td.bp .src { display:block; color:var(--faint); font-size:11px; line-height:1.6; }

/* 标签 */
.dsh-hld-tag { display:inline-block; padding:1px 8px; border-radius:4px; font-size:11px; line-height:1.7; white-space:nowrap; }
.dsh-hld-tag.buy  { background:#fef0f0; color:#f56c6c; }
.dsh-hld-tag.sell { background:#f0f9eb; color:#67c23a; }
.dsh-hld-tag.on   { background:#ecf5ff; color:#409eff; }
.dsh-hld-tag.off  { background:#f4f4f5; color:#909399; }
.dsh-hld-tag.warn, .dsh-hld-tag.trig { background:#fdf6ec; color:#e6a23c; }
.dsh-hld-tag.ok   { background:#f0f9eb; color:#529b2e; }
.dsh-hld-tag.bad  { background:#fef0f0; color:#f56c6c; }
.dsh-hld-tag.wait { background:#fdf6ec; color:#e6a23c; }

/* 盯盘中心：账户归属 tab（pill 带计数）+ 规则列表（2026-09-05 · 对齐执行看板调度任务 tab+列表） */
.dsh-hld-wtabs { display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:12px 18px 8px; border-bottom:1px solid #f0f0f0; }
.dsh-hld-wtab { appearance:none; display:inline-flex; align-items:center; gap:6px; border:1px solid var(--border); background:#fff;
  color:var(--body); font:inherit; font-size:12px; padding:3px 13px; border-radius:999px; cursor:pointer; transition:all .15s; }
.dsh-hld-wtab:hover { border-color:#b3d8ff; color:#1d6fe0; background:#f7fbff; }
.dsh-hld-wtab.act { background:#409eff; border-color:#409eff; color:#fff; font-weight:500; }
.dsh-hld-wtab .c { font-style:normal; font-weight:600; opacity:.85; font-variant-numeric:tabular-nums; }
.dsh-hld-wtabs + .tblwrap table { min-width:880px; }
.dsh-hld-auto .tblwrap table { min-width:700px; }
.dsh-hld-auto td .sub { margin-left:0; display:block; font-size:11px; }
.dsh-hld-auto th.exe, .dsh-hld-auto td.exe { width:56px; white-space:nowrap; }
.dsh-hld-echip { display:inline-block; font:600 9.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; padding:0 4px; border-radius:3px; white-space:nowrap; }
.dsh-hld-echip.v2 { background:#e8f1fd; color:#3370c9; }
.dsh-hld-echip.dh { background:#f3ecfa; color:#8b5fc8; }
.dsh-hld-echip.ts { background:#e0f4f6; color:#1498a8; }
.dsh-hld-auto-note { margin:2px 18px 0; padding:6px 12px; border:1px dashed #e6c36b; background:#fdf9ec; color:#8a6d1a; border-radius:6px; font-size:12px; line-height:1.5; }
.dsh-hld-tag.oth { background:#f4f4f5; color:#606266; }
.dsh-hld-card td.ctx { color:var(--dim); max-width:340px; }
.dsh-hld-card td.cond { color:var(--body); white-space:nowrap; }
.cond-up { color:var(--up); font-weight:600; }
.cond-down { color:var(--down); font-weight:600; }

/* 空态 */
.dsh-hld-empty { text-align:center; color:var(--dim); padding:26px 0 !important; }
.dsh-hld-emptybox { padding:30px 20px; text-align:center; color:var(--dim); font-size:13px; }

/* 错误横幅（board-mount renderError 复用） */
.dsh-hld-head { display:flex; align-items:baseline; gap:12px; margin-bottom:14px; }
.dsh-hld-title { font-size:18px; font-weight:600; color:var(--text); margin:0; }
.dsh-hld-banner { display:none; background:#fef0f0; border:1px solid #fde2e2; color:#f56c6c; padding:10px 16px; border-radius:8px; margin-bottom:14px; font-size:13px; }
.dsh-hld-banner.show { display:block; }
/* ===== 历史交易分页（dsh-hld-pg） ===== */
.dsh-hld-pg { display:flex; align-items:center; gap:8px; padding:10px 14px; border-top:1px solid #ebeef5; flex-wrap:wrap; }
.dsh-hld-pg .dsh-hld-pgb { min-width:26px; height:24px; padding:0 9px; border:1px solid #dcdfe6; border-radius:4px; background:#fff; color:#606266; font-size:12px; line-height:22px; cursor:pointer; font-family:inherit; }
.dsh-hld-pg .dsh-hld-pgb:hover:not(:disabled) { border-color:#409eff; color:#409eff; }
.dsh-hld-pg .dsh-hld-pgb:disabled { color:#c0c4cc; background:#f5f7fa; cursor:not-allowed; }
.dsh-hld-pg .dsh-hld-pgb.act { background:#409eff; border-color:#409eff; color:#fff; }
.dsh-hld-pg-nums { display:inline-flex; gap:4px; align-items:center; }
.dsh-hld-pg .gap { padding:0 2px; color:#c0c4cc; }
.dsh-hld-pg-cnt { margin-left:auto; font-size:12px; color:#909399; white-space:nowrap; }
`,(document.head??document.documentElement).appendChild(t)}const W=[`slots`,`sessions`,`workspaces`];function G(e){try{try{window.__dshHldCtx=e,window.__dshHldSessions=e.sessions,window.__dshHldWorkspaces=e.workspaces}catch{}U(),R(`dsh-hld`),window.__dshHldClient?.dispose();let t=B(),n=V(t),r=H({isActive:()=>t.getSnapshot().boardOpen,toggle:()=>t.toggleBoard()});window.__dshHldClient={dispose:()=>{n(),r(),t.closeBoard()}}}catch(e){console.error(`[dashboard-holdings] client half failed to start:`,e)}}exports.apply=G,exports.inject=W,exports.name=`@pi-investment/dashboard-holdings/client`;