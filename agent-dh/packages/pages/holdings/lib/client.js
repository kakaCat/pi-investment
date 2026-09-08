window.__ModuleLoader__.load({
		id: "@pi-investment/dashboard-holdings",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});const e=`dsh-panel-activate`;function t(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function n(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}function r(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}const i=e=>String(e).padStart(2,`0`);function a(e){if(!e)return null;let t=new Date(String(e));return Number.isNaN(t.getTime())?null:t}function o(e,t){if(!e)return`—`;let n=a(e);if(!n)return String(e).slice(0,16).replace(`T`,` `);let r=new Date,o=n.getFullYear()===r.getFullYear()&&n.getMonth()===r.getMonth()&&n.getDate()===r.getDate(),s=i(n.getHours())+`:`+i(n.getMinutes());return t?.omitDateIfToday&&o?s:(t?.withYear?n.getFullYear()+`-`+i(n.getMonth()+1)+`-`+i(n.getDate()):i(n.getMonth()+1)+`-`+i(n.getDate()))+` `+s}function s(e){let{prefix:n,icon:r,label:i,title:a,controller:o}=e,s=n.replace(/-([a-z])/g,(e,t)=>t.toUpperCase())+`Entry`,c=`[data-`+n+`-entry]`,l,u=()=>{let e=document.createElement(`button`);return e.type=`button`,e.className=n+`-entry`,e.dataset[s]=``,e.setAttribute(`aria-label`,a),e.title=a,e.innerHTML=r+`<span class="`+n+`-entry-label">`+i+`</span>`,e.addEventListener(`click`,e=>{e.preventDefault(),e.stopPropagation(),o.toggle()}),e},d=()=>{let e=t();if(e===void 0)return!1;if(e.querySelector(c)!==null){let t=e.querySelector(c);return t!==void 0&&l===void 0&&(l=t),!0}let n=u(),r=e.querySelector(`[class*="logoRow"]`);return r!==null&&r.nextSibling!==null?e.insertBefore(n,r.nextSibling):e.prepend(n),l=n,!0};d();let f=new MutationObserver(()=>{(l===void 0||!document.contains(l)||l.parentElement===null)&&d()});f.observe(document.body,{childList:!0,subtree:!0});let p=window.setInterval(()=>{(l===void 0||!document.contains(l))&&d()},5e3),m=()=>{l?.setAttribute(`data-active`,o.isActive()?`true`:`false`)},h=window.setInterval(m,1e3);return m(),()=>{f.disconnect(),window.clearInterval(p),window.clearInterval(h),l?.remove(),l=void 0}}const c=`[data-dsh-hld-view]`,l=`data-dsh-hld-active`,u=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-exec-active`,`data-dsh-bbd-active`,`data-dsh-gen-active`],d=(e,t=2)=>(Number.isFinite(Number(e))?Number(e):0).toLocaleString(`zh-CN`,{minimumFractionDigits:t,maximumFractionDigits:t}),f=e=>{let t=Number(e)||0;return(t>0?`+`:``)+t.toLocaleString(`zh-CN`,{maximumFractionDigits:2})},p=e=>{let t=Number(e)||0;return(t>0?`+`:``)+t.toFixed(2)+`%`},m=e=>{let t=Number(e)||0;return t>1e-4?`up`:t<-1e-4?`down`:`flat`},h=e=>{let t=e.context;if(typeof t==`string`)return t;try{return JSON.stringify(t??``)}catch{return``}},g={600519:`贵州茅台`,"000858":`五粮液`,"000568":`泸州老窖`,600809:`山西汾酒`,600600:`青岛啤酒`,601288:`农业银行`,601398:`工商银行`,601939:`建设银行`,601988:`中国银行`,600036:`招商银行`,"000001":`平安银行`,6e5:`浦发银行`,601166:`兴业银行`,600016:`民生银行`,601328:`交通银行`,601318:`中国平安`,601601:`中国太保`,601628:`中国人寿`,600030:`中信证券`,601688:`华泰证券`,600900:`长江电力`,601857:`中国石油`,600028:`中国石化`,601088:`中国神华`,600019:`宝钢股份`,600585:`海螺水泥`,601668:`中国建筑`,601390:`中国中铁`,601766:`中国中车`,600104:`上汽集团`,601633:`长城汽车`,601238:`广汽集团`,"000333":`美的集团`,"000651":`格力电器`,600690:`海尔智家`,300750:`宁德时代`,"002594":`比亚迪`,601012:`隆基绿能`,600438:`通威股份`,"002460":`赣锋锂业`,600276:`恒瑞医药`,603259:`药明康德`,"000538":`云南白药`,300760:`迈瑞医疗`,"002415":`海康威视`,"000063":`中兴通讯`,"002230":`科大讯飞`,"002475":`立讯精密`,"002241":`歌尔股份`,688981:`中芯国际`,688111:`金山办公`,603986:`兆易创新`,"002049":`紫光国微`,300782:`卓胜微`,"002371":`北方华创`,688012:`中微公司`,"002463":`沪电股份`,"002815":`崇达技术`,"002050":`三花智控`,"000807":`云铝股份`,601138:`工业富联`,"002352":`顺丰控股`,601888:`中国中免`,"000725":`京东方A`,"002714":`牧原股份`,300498:`温氏股份`,601111:`中国国航`,600029:`南方航空`,600150:`中国船舶`,601989:`中国重工`,600893:`航发动力`,"002179":`中航光电`,300059:`东方财富`,600031:`三一重工`};function _(e){if(e.enabled===!1)return!1;if(e.expires_at){let t=new Date(e.expires_at).getTime();if(Number.isFinite(t)&&t<=Date.now())return!1}return!0}function v(e){let t={};for(let n of e){let e=h(n),r=/([\u4e00-\u9fa5]{2,10})\s*\(?0*(\d{6})\)?/g,i;for(;(i=r.exec(e))!==null;)t[i[2]]=i[1]}return t}function y(e,t){if(!e)return`—`;let n=String(e).replace(/\D/g,``).slice(-6);return g[n]??t[n]??n}const b=e=>String(e??``).replace(/\D/g,``);function x(e){return/^(30|68)/.test(e)?-.1:-.08}function S(e,t=`current`,n=0){let i=e.summary??{},a=Array.isArray(e.accounts)?e.accounts:[],s=e.currentAccount??``,c=Array.isArray(e.positions)?e.positions:[],l=Array.isArray(e.watchRules)?e.watchRules:[],u=v(l),d=l.filter(e=>{let t=e.account;return t!=null&&t!==``&&t!==s?!1:_(e)}),f=a.length>1?`<div class="dsh-hld-acct">
		         <label for="dsh-hld-account-switch">账户</label>
		         <select id="dsh-hld-account-switch"
		           onchange="window.__dshHldSwitchAccount && window.__dshHldSwitchAccount(this.value)">
		           ${a.map(e=>`<option value="${r(e.account_name)}" ${e.account_name===s?`selected`:``}>${r(e.display_name||e.account_name)}（${e.positions_count??0} 仓）</option>`).join(``)}
		         </select>
		       </div>`:``,p=i.lastUpdated?o(i.lastUpdated):`—`,m=i.totalValue?i.dailyChange/(i.totalValue-i.dailyChange)*100:0;return`<div class="dsh-hld-board">
		  <div class="dsh-hld-topbar">
		    <div class="dsh-hld-title">
		      <h1>账户持仓看板</h1>
		      <div class="sub">只读监控 · 交易操作由 agent 执行</div>
		    </div>
		    <div class="dsh-hld-tools">
		      ${f}
		      <div class="dsh-hld-updated">更新于 <b>${r(p)}</b></div>
		      <button type="button" class="dsh-hld-refresh" onclick="window.__dshHldRefresh && window.__dshHldRefresh()">↻ 刷新</button>
		    </div>
		  </div>
		
		  ${C(i,m,e)}
		
		  ${w(c,u,d)}
		
		  ${E(e)}
		
		  ${O(e,n)}
		
		  ${I(e)}
		
		  ${L(e,t)}
		</div>`}function C(e,t,n){let r=m(e.dailyChange),i=m(e.totalPnl),a=Number(n.compliance?.cashRatio??(e.totalValue?e.cash/e.totalValue*100:0)),o=Number(n.compliance?.maxSingleStock??0),s=Number(n.compliance?.maxIndustry??0),c=Number(n.compliance?.maxDrawdown60d??0),l=(n.positions??[]).filter(e=>Number(e.profitLossPct)<=x(e.symbol)+1).length,u=(e,t,n=!1)=>`<span class="dsh-hld-chip ${e?`ok`:n?`warn`:`bad`}">${t} ${e?`✅`:`⚠️`}</span>`;return`<div class="dsh-hld-summary">
		  <div class="dsh-hld-sum-top">
		    <div class="dsh-hld-sum-pnl">
		      <div class="n">今日盈亏</div>
		      <div class="v ${r}">${f(e.dailyChange)} <small>${p(t)}</small></div>
		    </div>
		    <div class="dsh-hld-sum-pnl right">
		      <div class="n">持仓盈亏</div>
		      <div class="v ${i}">${f(e.totalPnl)} <small>${p(e.totalPnlPct)}</small></div>
		    </div>
		  </div>
		  <div class="dsh-hld-sum-assets">
		    <div class="asset-item"><div class="n">总资产</div><div class="v">${d(e.totalValue)}</div></div>
		    <div class="asset-item"><div class="n"><span class="legend-dot" style="background:#f56c6c"></span>持仓市值（${e.positions??0} 只）</div><div class="v">${d(e.totalMarketValue)}</div></div>
		    <div class="asset-item"><div class="n"><span class="legend-dot" style="background:#e6a23c"></span>可用资金</div><div class="v">${d(e.cash)}</div></div>
		  </div>
		  <div class="dsh-hld-risk">
		    ${u(a>=10,`现金占比 `+a.toFixed(1)+`% · 铁律 ≥10%`)}
		    ${u(o<=20,`单股最大 `+o.toFixed(2)+`% · 上限 20%`)}
		    ${u(s<=40,`单行业最大 `+s.toFixed(1)+`% · 上限 40%`)}
		    ${c>8?u(!1,`60日回撤 -`+c.toFixed(1)+`%（熔断线 -8%）`,!0):u(!0,`60日回撤 `+c.toFixed(1)+`%（熔断线 -8%）`)}
		    ${l>0?u(!1,l+` 只临近止损`,!0):u(!0,`无临近止损`)}
		  </div>
		</div>`}function w(e,t,n){let r=new Set(n.map(e=>b(e.symbol))),i=e.map(e=>T(e,t,r)).join(``),a=e.length===0?`<tr><td colspan="7" class="dsh-hld-empty">当前账户暂无持仓 — 空仓等待信号是正确决策</td></tr>`:``;return`<div class="dsh-hld-card">
		  <div class="hd"><span class="t">持仓明细（${e.length}）</span><span class="more">买卖点参考 = 止损铁律 + 止盈参考(+10%) · 具体交易由 agent 执行</span></div>
		  <div class="tblwrap"><table>
		    <tr>
		      <th>名称/代码</th><th class="r">市值/股数</th><th class="r">现价/成本</th>
		      <th class="r">今日盈亏</th><th class="r">持仓盈亏</th><th>买卖点参考</th><th>盯盘</th>
		    </tr>
		    ${i}${a}
		  </table></div>
		</div>`}function T(e,t,n){let i=y(e.symbol,t),a=b(e.symbol),o=x(a),s=(Number(e.avgCost)||0)*(1+o),c=(Number(e.avgCost)||0)*1.1,l=(Number(e.profitLossPct)||0)<=o+1,u=e.currentPrice?(Number(e.currentPrice)-s)/Number(e.currentPrice)*100:0,h=n.has(a),g=l?`<span class="dsh-hld-tag trig">⚠️ 临近止损</span>`:h?`<span class="dsh-hld-tag on">已挂盯盘</span>`:`<span class="dsh-hld-tag off">—</span>`,_=l?`<span class="dsh-hld-sl">⚠️ 临近止损 ${d(s)}（${Math.abs(o*100)}%）</span><br><span class="dsh-hld-s">反弹减 / 止盈参考 ${d(c)}（+10%）</span>`:`<span class="dsh-hld-sl">止损 ${d(s)}（-${Math.abs(o*100)}% 档）</span><br><span class="dsh-hld-s">止盈参考 ${d(c)}（+10%）</span>`;return`<tr>
		  <td><span class="sec-name">${r(i)}</span> <span class="sec-code">${r(a)}</span></td>
		  <td class="r">${d(e.currentValue,0)}<span class="sub">${e.quantity??0} 股 · 可卖 ${e.sharesAvailable??0}</span></td>
		  <td class="r">${d(e.currentPrice)}<span class="sub">成本 ${d(e.avgCost)}</span></td>
		  <td class="r ${m(e.profitToday)}">${f(e.profitToday)}<span class="sub">今日</span></td>
		  <td class="r ${m(e.profitLoss)}">${f(e.profitLoss)}<span class="sub">${p(e.profitLossPct)}</span></td>
		  <td class="bp">
		    ${_}
		    <span class="src">依据：成本 ${d(e.avgCost)} · 距止损线 +${Math.max(u,0).toFixed(1)}% · 铁律优先不补仓</span>
		  </td>
		  <td>${g}</td>
		</tr>`}function E(e){let t=Array.isArray(e.todayTrades)?e.todayTrades:[];if(t.length===0)return`<div class="dsh-hld-card">
		      <div class="hd"><span class="t">今日自动交易（0）</span><span class="more">agent 的买卖动作都会显示在这里</span></div>
		      <div class="dsh-hld-emptybox">今日尚无自动交易 — 没有信号时空仓等待是正确决策</div>
		    </div>`;let n={BUY:{tag:`buy`,text:`买入`},SELL:{tag:`sell`,text:`卖出`}},i={filled:`✅ 已成交`,partial:`⏳ 部分成交`,pending:`⏳ 待执行`,rejected:`❌ 已拒绝`,cancelled:`— 已撤单`},a=v(e.watchRules??[]),s=t.map(e=>{let t=n[String(e.action??``).toUpperCase()]??{tag:`off`,text:String(e.action??``)},s=Number(e.filled_price)||Number(e.price),c=s*(e.shares??0),l=i[String(e.status??``)]??String(e.status??``);return`<tr>
		        <td><span class="dsh-hld-tag ${t.tag}">${t.text}</span></td>
		        <td><span class="sec-name">${r(y(e.symbol,a))}</span> <span class="sec-code">${r(b(e.symbol))}</span></td>
		        <td class="r">${d(s)}<span class="sub">× ${e.shares??0} 股</span></td>
		        <td class="r">${d(c)}</td>
		        <td>${r(String(e.reason??`—`).slice(0,64))}</td>
		        <td>${l}</td>
		        <td class="dim">${r(o(e.created_at))}</td>
		      </tr>`}).join(``);return`<div class="dsh-hld-card">
		  <div class="hd"><span class="t">今日自动交易（${t.length}）</span><span class="more">agent 已完成 / 进行中的自动交易</span></div>
		  <div class="tblwrap"><table>
		    <tr><th>方向</th><th>股票</th><th class="r">成交价</th><th class="r">金额</th><th>理由</th><th>状态</th><th>时间</th></tr>
		    ${s}
		  </table></div>
		</div>`}function D(e,t,n){if(t<=9){let r=``;for(let i=0;i<t;i++)r+=n(i,String(i+1),i===e);return r}let r=[...new Set([0,t-1,e-1,e,e+1].filter(e=>e>=0&&e<t))].sort((e,t)=>e-t),i=``,a=-2;for(let t of r)t-a>1&&(i+=`<span class="gap">…</span>`),i+=n(t,String(t+1),t===e),a=t;return i}function O(e,t){let n=Array.isArray(e.tradeHistory)?e.tradeHistory:[],i=Math.max(1,Math.ceil(n.length/8)),a=Math.min(Math.max(0,Math.trunc(Number(t)||0)),i-1);if(n.length===0)return`<div class="dsh-hld-card" id="dsh-hld-hx">
		      <div class="hd"><span class="t">历史交易（0）</span><span class="more">${r(String(e.currentAccount??``))} · agent 成交后自动归档到此</span></div>
		      <div class="dsh-hld-emptybox">该账户暂无历史交易记录</div>
		    </div>`;let s=n.slice(a*8,(a+1)*8),c=v(e.watchRules??[]),l={BUY:{tag:`buy`,text:`买入`},SELL:{tag:`sell`,text:`卖出`}},u=s.map(e=>{let t=String(e.action??``).toUpperCase(),n=l[t]??{tag:`off`,text:String(e.action??``)},i=Number(e.filled_price)||Number(e.price),a=Number(e.amount)||i*(e.shares??0),s=Number(e.realized_pnl),u=t===`SELL`&&Number.isFinite(s),h=u&&s!==0?m(s):`flat`,g=Number(e.realized_pnl_rate),_=u&&Number.isFinite(g)&&g!==0?`<span class="sub">`+p(g)+`</span>`:``,v=String(e.reason??`—`);return`<tr>
		        <td><span class="dsh-hld-tag ${n.tag}">${n.text}</span></td>
		        <td><span class="sec-name">${r(y(e.symbol,c))}</span> <span class="sec-code">${r(b(e.symbol))}</span></td>
		        <td class="r">${d(i)}<span class="sub">× ${e.shares??0} 股</span></td>
		        <td class="r">${d(a)}</td>
		        <td class="r ${h}">${u?f(s)+_:`<span class="dim">—</span>`}</td>
		        <td title="${r(v)}">${r(v.slice(0,60))}</td>
		        <td class="dim">${r(o(e.created_at))}</td>
		      </tr>`}).join(``),h=i<=1?``:`<div class="dsh-hld-pg">
		        <button type="button" class="dsh-hld-pgb"${a===0?` disabled`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${a-1})">‹ 上一页</button>
		        <span class="dsh-hld-pg-nums">${D(a,i,(e,t,n)=>`<button type="button" class="dsh-hld-pgb${n?` act`:``}"${e===a?` aria-current="page"`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${e})">${t}</button>`)}</span>
		        <button type="button" class="dsh-hld-pgb"${a>=i-1?` disabled`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${a+1})">下一页 ›</button>
		        <span class="dsh-hld-pg-cnt">第 ${a+1}/${i} 页 · 共 ${n.length} 笔</span>
		      </div>`;return`<div class="dsh-hld-card" id="dsh-hld-hx">
		  <div class="hd"><span class="t">历史交易（${n.length}）</span><span class="more">${r(String(e.currentAccount??``))} · agent 全部成交明细 · 倒序</span></div>
		  <div class="tblwrap"><table>
		    <tr><th>方向</th><th>股票</th><th class="r">成交价</th><th class="r">金额</th><th class="r">实现盈亏</th><th>理由</th><th>时间</th></tr>
		    ${u}
		  </table></div>
		  ${h}
		</div>`}function k(e,t,n,i,a){let o=e=>e.account??``,s=e.filter(e=>_(e)),c=s.filter(e=>o(e)===``),l=s.filter(e=>o(e)===n).concat(c),u=[];for(let e of s){let t=o(e);t!==``&&t!==n&&!u.includes(t)&&u.push(t)}let d=new Map;for(let e of i)d.set(e.account_name,e.display_name||e.account_name);let f=e=>d.get(e)??e,p=new Set([`current`,`all`,...u]).has(a)?a:`current`,m=p===`all`?s:p===`current`?l:s.filter(e=>o(e)===p),g=(e,t,n,i)=>`<button type="button" class="dsh-hld-wtab${p===e?` act`:``}" data-wkey="${e}" title="${r(i)}" onclick="window.__dshHldWatchTab && window.__dshHldWatchTab('${e.replace(/'/g,``)}')">${r(t)}<i class="c">${n}</i></button>`,v=[g(`current`,`本账户`,l.length,`当前账户归属 + 通用观察（${f(n)}）`)];for(let e of u)v.push(g(e,f(e),s.filter(t=>o(t)===e).length,`归属账户：${e}`));v.push(g(`all`,`全部`,s.length,`全部账户规则汇总`));let x=m.map(e=>{let i=h(e),a=i.replace(/\s+/g,` `).trim(),s=(e.conditions??[]).map(R).filter(Boolean),c=s.slice(0,3).join(` <span class="dim">·</span> `)+(s.length>3?` <span class="dim">+`+(s.length-3)+`</span>`:``),l=z(i),u=o(e),d=u===``?`off`:u===n?`on`:`oth`,p=u===``?`通用观察`:u===n?`本账户`:f(u);return`<tr>
		      <td><span class="sec-name">${r(y(e.symbol,t))}</span> <span class="sec-code">${r(b(e.symbol))}</span></td>
		      <td><span class="dsh-hld-tag ${l.cls}">${l.text}</span></td>
		      <td class="cond">${c||`<span class="dim">—</span>`}</td>
		      <td>${e.enabled?`<span class="dsh-hld-tag on">监控中</span>`:`<span class="dsh-hld-tag off">已停用</span>`}</td>
		      <td><span class="dsh-hld-tag ${d}" title="${r(u||`通用观察`)}">${r(p)}</span></td>
		      <td class="ctx" title="${r(a.slice(0,400))}">${r(a.slice(0,44))}${a.length>44?`…`:``}</td>
		    </tr>`}).join(``),S=p===`current`?`本账户暂无归属/通用观察规则 — 开仓后 agent 会自动挂上止损/止盈盯盘；可切换上方其他账户 / 全部 tab`:p===`all`?`暂无任何盯盘规则`:`该账户暂无归属盯盘规则`,C=m.length===0?`<tr class="dsh-hld-empty"><td colspan="6">`+S+`</td></tr>`:``;return`<div class="dsh-hld-card" id="dsh-hld-watch">
		  <div class="hd"><span class="t">盯盘中心（${s.length}）</span><span class="more">账户归属 tab · 默认本账户（含通用观察）· 触发后由 agent 决策，无需人工盯盘</span></div>
		  <div class="dsh-hld-wtabs">${v.join(``)}</div>
		  <div class="tblwrap"><table>
		    <tr><th>股票</th><th>监控性质</th><th>触发条件</th><th>状态</th><th>归属账户</th><th>监控摘要</th></tr>
		    ${x}${C}
		  </table></div>
		</div>`}const A={"v13-simulation-trading":`模拟交易执行`,v13_daily_check:`模拟交易执行`,"v13-risk-check":`风控检查`,v13_risk_check:`风控检查`,"v13-verification":`验证裁决`,v13_verification:`验证裁决`,"v13-weekly-report":`每周报告`,v13_weekly_report:`每周报告`,"v14-simulation-trading":`模拟交易执行`,v14_daily_check:`模拟交易执行`,morning_ai_analysis:`晨间 AI 分析`,realtime_quick_check:`盘中快速检查`,daily_ai_review:`每日 AI 复盘`,daily_recall_audit:`每日回查审计`,weekly_evolution:`周度策略进化`,weekly_memory_distill:`周度记忆蒸馏`,weekly_tool_roi_review:`周度工具 ROI 复盘`,"pre-market-routine":`盘前例行检查`,"afternoon-open-check-live":`午后开盘检查`,"post-market-routine-live":`盘后例行复盘`,"m4-circuit-breaker-live":`M4 回撤熔断巡检`,"weekly-report-m6":`M6 学习飞轮周报`,"agent-brain-morning-analysis":`晨间 AI 分析`,"agent-brain-realtime-check":`盘中快速检查`,"agent-brain-daily-review":`每日 AI 复盘`,"agent-brain-daily-audit":`每日回查审计`,"agent-brain-weekly-evolution":`周度策略进化`,"agent-brain-weekly-distill":`周度记忆蒸馏`,"agent-brain-weekly-roi":`周度工具 ROI 复盘`},j={success:{cls:`ok`,text:`成功`},failed:{cls:`bad`,text:`失败`},skipped:{cls:`wait`,text:`跳过`},pending:{cls:`on`,text:`待执行`},unknown:{cls:`off`,text:`未知`},"":{cls:`off`,text:`从未运行`}};function M(e){let t=String(e??``).trim().split(/\s+/);if(t.length!==5)return String(e||`—`);let[,n,,,r]=t,i=(String(n).padStart(2,`0`)||`--`)+`:`+(t[0].padStart(2,`0`)||`--`),a=String(r);return!a||a===`*`?`每天 `+i:/^\d+$/.test(a)?`周`+`日一二三四五六`[Number(a)%7]+` `+i:/^1-5$/.test(a)?`工作日 `+i:/^(0|6)(,(0|6))?$/.test(a)?`周末 `+i:/^1-5$/.test(a.replace(/,/g,`-`))?`工作日 `+i:a+` `+i}const N={v2:`quantsys-v2 引擎 cron 自动执行（不走 agent）`,ts:`fin-agent（agent-ts）智能体执行`,dh:`agent-dh · investor 例行执行`};function P(e){return e!==`v2`&&e!==`ts`&&e!==`dh`?`<span class="dim">—</span>`:`<span class="dsh-hld-echip `+e+`" title="`+r(N[e]??``)+`">`+e+`</span>`}function F(e,t=!0,n=!1,i=``){let a=A[String(e.name)]??A[String(e.command)]??String(e.name||e.command||`?`),s=M(e.scheduleExpr),c=j[String(e.lastStatus??``)]??j.unknown,l=e.lastAt?o(e.lastAt):`—`,u=e.nextRunAt?o(e.nextRunAt):`—`,d=e.todayTriggered>0?e.todaySuccess+`/`+e.todayTriggered:`—`,f=e.enabled,p=f?c.cls:`off`,m=f?c.text:`未启用`,h=[String(e.name||``),String(e.command||``),e.lastError?`最近错误: `+String(e.lastError).slice(0,120):``].filter(Boolean).join(` · `),g=f&&String(e.lastStatus??``)===`failed`,_=t?`<td class="r">${d}</td><td class="dim">${u}</td>`:n?`<td class="op">${g?`<button type="button" class="dsh-hld-solve" data-solve-task="${r(String(e.name||``))}"
		              title="投递给 investor 窗口排查处置此任务" onclick="window.__dshHldSolveTask && window.__dshHldSolveTask(this)">我来解决</button>`:`<span class="dim">—</span>`}</td>`:``;return`<tr title="${r(h)}">
		    <td><span class="dsh-hld-tag ${p}">${m}</span></td>
		    <td>${r(a)}<span class="sub dim"> ${r(e.command)}</span></td>
		    <td class="exe">${P(i)}</td>
		    <td>${r(s)}</td>
		    <td class="dim">${l}</td>
		    ${_}
		  </tr>`}function I(e){let t=e.automation;if(!t||t.tasks.length===0)return``;let n=t.tasks,i=t.engine===!0,a=i?`引擎定时任务`:`执行例行任务`,o=t.executor?` · `+t.executor:``,s=t.note?`<div class="dsh-hld-auto-note">⚠️ ${r(t.note)}</div>`:``,c=(e.watchRules??[]).filter(e=>e.account===t.accountName&&_(e)).length,l=n.map(e=>i?F(e,!0,!1,t.executorCode):F(e,!1,!0,t.executorCode)).join(``),u=i?`<th class="r">今日 成/触</th><th>下次运行</th>`:`<th>处理</th>`;return`<div class="dsh-hld-card dsh-hld-auto">
		  <div class="hd"><span class="t">账户自动化流程</span>
		    <span class="more">${r(t.displayName)}${o} · ${n.length} 个${a} · 盯盘规则 ${c} 条（见下方盯盘中心）</span></div>
		  ${s}
		  <div class="tblwrap"><table class="dsh-hld-autotbl">
		    <tr><th>状态</th><th>任务</th><th class="exe">执行</th><th>计划时刻</th><th>上次运行</th>${u}</tr>
		    ${l}
		  </table></div>
		</div>`}function L(e,t){let n=v(e.watchRules??[]);return k(e.watchRules??[],n,e.currentAccount??``,Array.isArray(e.accounts)?e.accounts:[],t)}function R(e){let t=e.params;if(e.type===`price_break`||String(e.operator||``).toLowerCase().includes(`price`)){if(t&&t.price!==void 0&&t.price!==null){let e=t.direction===`above`?`突破`:t.direction===`below`?`跌破`:`触碰`;return`<span class="cond-${t.direction===`above`?`up`:`down`}">${e}${d(t.price)}</span>`}if(e.threshold!==void 0&&e.threshold!==null)return`价格 `+e.threshold}return e.threshold!==void 0&&e.threshold!==null&&e.operator?String(e.operator||e.type).toUpperCase()+` `+e.threshold:String(e.type??e.operator??`条件`)}function z(e){return/止损|风控|破位|减仓保护/.test(e)?{cls:`warn`,text:`止损监控`}:/买入|低吸|介入|加仓|建仓|补仓/.test(e)?{cls:`buy`,text:`买入提醒`}:/卖出|止盈|减仓|高抛|目标价/.test(e)?{cls:`sell`,text:`卖出提醒`}:{cls:`on`,text:`常规监控`}}function B(e){return[`.`+e+`-solve { flex:none; border:1px solid #c6e2ff; background:#ecf5ff; color:#409eff; border-radius:5px; padding:2px 9px; font-size:11.5px; line-height:1.7; cursor:pointer; white-space:nowrap; vertical-align:middle; }`,`.`+e+`-solve:hover { background:#d9ecff; border-color:#79bbff; }`,`.`+e+`-solve:active { background:#c6e2ff; }`,`.`+e+`-solvepop { position:fixed; z-index:9999; min-width:232px; max-width:300px; background:var(--panel,#fff); border:1px solid var(--border,#e4e7ed); border-radius:8px; box-shadow:0 6px 22px rgba(0,0,0,.16); padding:6px; font-size:12.5px; color:var(--body,#606266); }`,`.`+e+`-solvepop-head { padding:4px 8px 7px; color:var(--text,#303133); font-weight:600; font-size:12px; border-bottom:1px solid var(--line,#ebeef5); margin-bottom:4px; }`,`.`+e+`-solvepop-list { display:flex; flex-direction:column; max-height:264px; overflow-y:auto; }`,`.`+e+`-solvepop-item { border:none; background:transparent; text-align:left; padding:5px 8px; border-radius:5px; cursor:pointer; color:var(--body,#606266); font:inherit; font-size:12.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }`,`.`+e+`-solvepop-item:hover { background:var(--hover,rgba(128,128,128,.12)); }`,`.`+e+`-solvepop-item.cur { color:#409eff; font-weight:600; }`,`.`+e+`-solvepop-cancel { width:100%; margin-top:4px; border:none; background:transparent; color:var(--dim,#909399); font:inherit; font-size:12px; padding:4px; cursor:pointer; border-top:1px solid var(--line,#ebeef5); }`,`.`+e+`-solvepop-cancel:hover { color:var(--text,#303133); }`,`.`+e+`-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }`,`.`+e+`-toast.ok { background:#529b2e; }`,`.`+e+`-toast.err { background:#e64545; }`,`.`+e+`-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }`].join(`
		`)}function V(e){let t=`dsh-solve-styles-`+e,n=document.getElementById(t);if(n!==null&&n.tagName===`STYLE`)return()=>n.remove();let r=document.createElement(`style`);return r.id=t,r.textContent=B(e),(document.head??document.documentElement).appendChild(r),()=>{document.getElementById(t)?.remove()}}function H(e){let t=e.prefix,n,r,i=()=>{r?.(),r=void 0,n!==void 0&&(n.remove(),n=void 0)},a=(e,n)=>{let r=document.createElement(`div`);r.className=t+`-toast `+(n?`ok`:`err`),r.textContent=e,document.body.appendChild(r),window.setTimeout(()=>{r.classList.add(`out`),window.setTimeout(()=>r.remove(),350)},4200)},o=async(t,n,r)=>{let i=e.current();try{let o=await fetch(e.endpoint,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({kind:t,task:t===`task`?n:void 0,err:t===`error`?n:void 0,from_session:i||void 0,to_session:r})}),s=await o.json().catch(()=>null);if(s===null||s.success!==!0){a(`投递失败：`+String(s?.error??`HTTP `+o.status),!1);return}let c=s.data;a(c?.delivered===!0?`✓ `+String(c?.note??`已投递`):`⚠ `+String(c?.error??s.error??`投递失败`),c?.delivered===!0)}catch(e){a(`请求异常：`+String(e instanceof Error?e.message:e),!1)}};return{toast:a,openPicker:(s,c,l)=>{let u=e.resolveSnapshot(c,l);if(u===null){a(`⚠ 数据已刷新，请重试`,!1);return}i();let d=e.candidates();if(d.length===0){o(u.kind,u.snap);return}let f=document.createElement(`div`);f.className=t+`-solvepop`;let p=document.createElement(`div`);p.className=t+`-solvepop-head`,p.textContent=`投递给窗口排查处置`,f.appendChild(p);let m=document.createElement(`div`);m.className=t+`-solvepop-list`;for(let e of d){let n=document.createElement(`button`);n.type=`button`,n.className=t+`-solvepop-item`+(e.current?` cur`:``),n.textContent=(e.current?`● `:`○ `)+e.label,n.addEventListener(`click`,()=>{i(),o(u.kind,u.snap,e.sid)}),m.appendChild(n)}f.appendChild(m);let h=document.createElement(`button`);h.type=`button`,h.className=t+`-solvepop-cancel`,h.textContent=`取消`,h.addEventListener(`click`,i),f.appendChild(h);let g;try{g=typeof e.host==`function`?e.host():e.host}catch{g=void 0}(g??document.body).appendChild(f),n=f;let _=s.getBoundingClientRect(),v=40+d.length*30+32,y=_.bottom+6;y+v>window.innerHeight&&(y=Math.max(6,_.top-v-6)),f.style.position=`fixed`,f.style.left=Math.min(_.left,Math.max(6,window.innerWidth-280))+`px`,f.style.top=y+`px`;let b=e=>{let t=e.target;t!==null&&f.contains(t)||(document.removeEventListener(`click`,b,!0),r=void 0,i())};document.addEventListener(`click`,b,!0),r=()=>document.removeEventListener(`click`,b,!0)},close:i}}function U(){let t=!1,n=`agent_virtual`,r=`current`,i=0,a,o,s=()=>{if(!t){t=!0,console.log(`[dashboard-holdings] opening board`),document.documentElement.setAttribute(l,``);for(let e of u)document.documentElement.removeAttribute(e);window.dispatchEvent(new CustomEvent(e,{detail:`dashboard-holdings`})),h(),_(n)}},d=()=>{t&&(t=!1,console.log(`[dashboard-holdings] closing board`),document.documentElement.removeAttribute(l),g())},f=()=>{t?d():s()},p=()=>{console.log(`[dashboard-holdings] manual refresh`),_(n)},m=e=>{console.log(`[dashboard-holdings] switching account to`,e),n=e,r=`current`,i=0,_(e)},h=()=>{g(),o=window.setInterval(()=>{t&&_(n)},15e3)},g=()=>{o!==void 0&&(clearInterval(o),o=void 0)},_=async e=>{try{let t=`/dashboard/api/holdings?account=${encodeURIComponent(e)}`,n=await(await fetch(t)).json();if(!n.success)throw Error(n.error||`Unknown error`);let r=n.data;v(r)}catch(e){console.error(`[dashboard-holdings] fetch failed:`,e),y(String(e))}},v=e=>{a=e;let t=document.querySelector(c);t&&(t.innerHTML=S(e,r,i))},y=e=>{let t=document.querySelector(c);t&&(t.innerHTML=`
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
		    `)},b=e=>{let t=String(e||`current`);if(t===r||(r=t,!a))return;let n=document.getElementById(`dsh-hld-watch`);if(n===null){v(a);return}let i=document.createElement(`template`);i.innerHTML=L(a,r);let o=i.content.firstElementChild;if(o===null){v(a);return}n.replaceWith(o)},x=e=>{let t=a?.tradeHistory?.length??0,n=Math.max(1,Math.ceil(t/8)),r=Math.max(0,Math.min(Math.trunc(Number(e)||0),n-1));if(r===i||(i=r,!a))return;let o=document.getElementById(`dsh-hld-hx`);if(o===null){v(a);return}let s=document.createElement(`template`);s.innerHTML=O(a,i);let c=s.content.firstElementChild;if(c===null){v(a);return}o.replaceWith(c)},C=()=>{let e=window;try{return String((e.__dshHldSessions??e.__dshHldCtx?.sessions)?.list?.getSnapshot?.().current??``)}catch{return``}},w=H({endpoint:`/dashboard/api/holdings/solve`,prefix:`dsh-hld`,candidates:()=>{let e=window,t=[];try{let n=(e.__dshHldSessions??e.__dshHldCtx?.sessions)?.list?.getSnapshot?.(),r=Array.isArray(n?.items)?n.items:(n?.ids??[]).map(e=>({id:e,title:e})),i=new Set(e.__dshHldWorkspaces?.list?.getSnapshot?.().archivedSessionIds??e.__dshHldCtx?.workspaces?.list?.getSnapshot?.().archivedSessionIds??[]),a=C();for(let e of r){let n=String(e?.id??``);if(!n||i.has(n))continue;let r=!!e?.blank,o=String(e?.origin??``);if(r||o.startsWith(`subagent`))continue;let s=String(e?.title??e?.displayTitle??``).slice(0,42);t.push({sid:n,label:s||n,current:n===a})}}catch{}return t},current:C,resolveSnapshot:(e,t)=>{if(e!==`task`)return null;let n=a?.automation;if(!n||n.engine===!0)return null;let r=(n.tasks??[]).find(e=>String(e.name)===String(t.name??``));if(!r)return null;let i=String(a?.summary?.lastUpdated??``);return{kind:`task`,snap:{name:r.name,src:String(r.command||`Agent OS 调度任务`),scheduleExpr:r.scheduleExpr,nextRunAt:r.nextRunAt,lastRun:{status:r.lastStatus,triggeredAt:r.lastAt,finishedAt:r.lastAt,err:r.lastError},todayTriggered:r.todayTriggered,todaySuccess:r.todaySuccess,fetchedAt:i,error:r.lastError}}}});return{openBoard:s,closeBoard:d,toggleBoard:f,getSnapshot:()=>({boardOpen:t}),refresh:p,switchAccount:m,watchSwitch:b,historyPageSwitch:x,solveTask:e=>{if(!e)return;let t=String(e.dataset?.solveTask??``);t&&w.openPicker(e,`task`,{name:t})}}}function W(t){let r,i=()=>{if(r!==void 0)return;let e=n();e!==void 0&&(r=document.createElement(`div`),r.setAttribute(`data-dsh-hld-view`,``),r.className=`dsh-hld-view`,e.appendChild(r),console.log(`[dashboard-holdings] board container mounted`))},a=new MutationObserver(()=>{i()});a.observe(document.body,{childList:!0,subtree:!0}),i(),window.__dshHldRefresh=()=>t.refresh(),window.__dshHldSwitchAccount=e=>t.switchAccount(e),window.__dshHldWatchTab=e=>t.watchSwitch(String(e)),window.__dshHldHistoryPage=e=>t.historyPageSwitch(Number(e)),window.__dshHldSolveTask=e=>t.solveTask(e);let o=e=>{e.detail!==`dashboard-holdings`&&t.getSnapshot().boardOpen&&t.closeBoard()};window.addEventListener(e,o);let s=e=>{if(!t.getSnapshot().boardOpen)return;let n=e.target;n!==null&&n.closest(`[data-dsh-hld-view]`)===null&&n.closest(`[class*="dsh-hld-foot"]`)===null&&n.closest(`[data-dsh-hld-entry]`)===null&&t.closeBoard()};return document.addEventListener(`click`,s,!0),()=>{window.removeEventListener(e,o),document.removeEventListener(`click`,s,!0),a.disconnect(),r!==void 0&&r.remove(),delete window.__dshHldRefresh,delete window.__dshHldSwitchAccount,delete window.__dshHldWatchTab,delete window.__dshHldHistoryPage,delete window.__dshHldSolveTask,console.log(`[dashboard-holdings] board unmounted`)}}function G(e){return s({prefix:`dsh-hld`,icon:`<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 2 V8 L12 11"/><path d="M8 8 L4 5"/></svg>`,label:`账户持仓`,title:`账户持仓看板`,controller:e})}function K(){let e=`dsh-hld-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
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
		`,(document.head??document.documentElement).appendChild(t)}const q=[`slots`,`sessions`,`workspaces`];function J(e){try{try{window.__dshHldCtx=e,window.__dshHldSessions=e.sessions,window.__dshHldWorkspaces=e.workspaces}catch{}K(),V(`dsh-hld`),window.__dshHldClient?.dispose();let t=U(),n=W(t),r=G({isActive:()=>t.getSnapshot().boardOpen,toggle:()=>t.toggleBoard()});window.__dshHldClient={dispose:()=>{n(),r(),t.closeBoard()}}}catch(e){console.error(`[dashboard-holdings] client half failed to start:`,e)}}exports.apply=J,exports.inject=q,exports.name=`@pi-investment/dashboard-holdings/client`;
			return module.exports;
		}
	});

