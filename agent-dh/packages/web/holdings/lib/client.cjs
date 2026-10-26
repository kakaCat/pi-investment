Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");function t(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function n(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}const r=e=>String(e).padStart(2,`0`);function i(e){if(!e)return null;let t=new Date(String(e));return Number.isNaN(t.getTime())?null:t}function a(e,t){if(!e)return`—`;let n=i(e);if(!n)return String(e).slice(0,16).replace(`T`,` `);let a=new Date,o=n.getFullYear()===a.getFullYear()&&n.getMonth()===a.getMonth()&&n.getDate()===a.getDate(),s=r(n.getHours())+`:`+r(n.getMinutes());return t?.omitDateIfToday&&o?s:(t?.withYear?n.getFullYear()+`-`+r(n.getMonth()+1)+`-`+r(n.getDate()):r(n.getMonth()+1)+`-`+r(n.getDate()))+` `+s}function o(e){return[`.`+e+`-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }`,`.`+e+`-toast.ok { background:#529b2e; }`,`.`+e+`-toast.err { background:#e64545; }`,`.`+e+`-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }`].join(`
`)}function s(e){let t=`dsh-toast-styles-`+e,n=document.getElementById(t);if(n!==null&&n.tagName===`STYLE`)return()=>n.remove();let r=document.createElement(`style`);return r.id=t,r.textContent=o(e),(document.head??document.documentElement).appendChild(r),()=>{document.getElementById(t)?.remove()}}function c(e,t,n,r=4200){let i=document.createElement(`div`);i.className=n+`-toast `+(t?`ok`:`err`),i.textContent=e,document.body.appendChild(i),window.setTimeout(()=>{i.classList.add(`out`),window.setTimeout(()=>i.remove(),350)},r)}function l(e){let{prefix:n,icon:r,label:i,title:a,controller:o}=e,s=n.replace(/-([a-z])/g,(e,t)=>t.toUpperCase())+`Entry`,c=`[data-`+n+`-entry]`,l,u=()=>{let e=document.createElement(`button`);return e.type=`button`,e.className=n+`-entry`,e.dataset[s]=``,e.setAttribute(`aria-label`,a),e.title=a,e.innerHTML=r+`<span class="`+n+`-entry-label">`+i+`</span>`,e.addEventListener(`click`,e=>{e.preventDefault(),e.stopPropagation(),o.toggle()}),e},d=()=>{let e=t();if(e===void 0)return!1;if(e.querySelector(c)!==null){let t=e.querySelector(c);return t!==void 0&&l===void 0&&(l=t),!0}let n=u(),r=e.querySelector(`[class*="logoRow"]`);return r!==null&&r.nextSibling!==null?e.insertBefore(n,r.nextSibling):e.prepend(n),l=n,!0};d();let f=new MutationObserver(()=>{(l===void 0||!document.contains(l)||l.parentElement===null)&&d()});f.observe(document.body,{childList:!0,subtree:!0});let p=window.setInterval(()=>{(l===void 0||!document.contains(l))&&d()},5e3),m=()=>{l?.setAttribute(`data-active`,o.isActive()?`true`:`false`)},h=window.setInterval(m,1e3);return m(),()=>{f.disconnect(),window.clearInterval(p),window.clearInterval(h),l?.remove(),l=void 0}}const u=`dsh-right-tab-host`,d=`dsh-right-tab-host-style`,f=`
.${u}{display:flex;flex-direction:column;height:100%;min-height:0;overflow:hidden}
.${u}>*{min-height:0}
.${u} .dsh-right-tab-error{padding:16px 18px;color:#b94a48;font:13px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
`;function p(){if(typeof document>`u`||document.getElementById(d)!==null)return;let e=document.createElement(`style`);e.id=d,e.textContent=f,document.head.appendChild(e)}function m(t){return function(n){let r=(0,e.useRef)(null);return(0,e.useEffect)(()=>{let e=r.current;if(e===null)return;let n;try{n=t.mount(e)}catch(n){console.error(`[page-kit] 右栏看板挂载失败 `+t.id+`:`,n);let r=document.createElement(`div`);r.className=`dsh-right-tab-error`,r.textContent=`看板加载失败：`+(n instanceof Error?n.message:String(n)),e.appendChild(r)}return()=>{try{typeof n==`function`&&n()}catch(e){console.error(`[page-kit] 右栏看板卸载清理失败 `+t.id+`:`,e)}}},[]),(0,e.createElement)(`div`,{ref:r,className:u,"data-right-tab":t.id})}}function h(e,t){let n=e??{},r=n.sidebarRightTabs,i=n.sidebarRight,a=n.slots;if(r===void 0||typeof r.register!=`function`)throw Error(`sidebarRightTabs 服务不可用（DSH 官方右侧栏未加载）`);if(i===void 0||typeof i.openTab!=`function`)throw Error(`sidebarRight 服务不可用（DSH 官方右侧栏未加载）`);p();let o=[];if(((e,t)=>{try{if(typeof n.effect==`function`){n.effect(e,t);return}let r=e();typeof r==`function`&&o.push(r)}catch(e){console.error(`[page-kit] 右栏注册失败 `+t+`:`,e)}})(()=>r.register({id:t.id,kind:t.kind,title:()=>t.title,keepMounted:!0}),`tab-type:`+t.id),a!==void 0&&typeof a.register==`function`){let e=m(t);try{typeof a.inject==`function`?a.inject(`sidebar.right.pane.tab`,()=>a.register({name:`sidebar.right.pane.tab`,key:t.id},e)):a.register({name:`sidebar.right.pane.tab`,key:t.id},e)}catch(e){console.error(`[page-kit] 右栏正文注册失败 `+t.id+`:`,e)}}else console.error(`[page-kit] slots 服务不可用，右栏正文未注册 `+t.id);let s=()=>{try{return i.openTab(t.kind),!0}catch(e){return console.error(`[page-kit] 右栏打开失败 `+t.kind+`:`,e),!1}},c=()=>{try{if(typeof i.isExpanded==`function`&&i.isExpanded()===!1||typeof i.active!=`function`)return!1;let e=i.active();return e!=null&&e.kind===t.kind}catch{return!1}},l=()=>{if(c())try{let e=i.active?.();e!=null&&e.id!==void 0&&i.close?.(e.id)}catch(e){console.error(`[page-kit] 右栏关闭失败 `+t.kind+`:`,e)}};return{open:s,toggle:()=>{c()?l():s()},close:l,isActive:c,dispose:()=>{l();for(let e of o.splice(0))try{e()}catch{}}}}const g=(e,t=2)=>(Number.isFinite(Number(e))?Number(e):0).toLocaleString(`zh-CN`,{minimumFractionDigits:t,maximumFractionDigits:t}),_=e=>{let t=Number(e)||0;return(t>0?`+`:``)+t.toLocaleString(`zh-CN`,{maximumFractionDigits:2})},v=e=>{let t=Number(e)||0;return(t>0?`+`:``)+t.toFixed(2)+`%`},y=e=>{let t=Number(e)||0;return t>1e-4?`up`:t<-1e-4?`down`:`flat`},b=e=>{let t=e.context;if(typeof t==`string`)return t;try{return JSON.stringify(t??``)}catch{return``}},x={600519:`贵州茅台`,"000858":`五粮液`,"000568":`泸州老窖`,600809:`山西汾酒`,600600:`青岛啤酒`,601288:`农业银行`,601398:`工商银行`,601939:`建设银行`,601988:`中国银行`,600036:`招商银行`,"000001":`平安银行`,6e5:`浦发银行`,601166:`兴业银行`,600016:`民生银行`,601328:`交通银行`,601318:`中国平安`,601601:`中国太保`,601628:`中国人寿`,600030:`中信证券`,601688:`华泰证券`,600900:`长江电力`,601857:`中国石油`,600028:`中国石化`,601088:`中国神华`,600019:`宝钢股份`,600585:`海螺水泥`,601668:`中国建筑`,601390:`中国中铁`,601766:`中国中车`,600104:`上汽集团`,601633:`长城汽车`,601238:`广汽集团`,"000333":`美的集团`,"000651":`格力电器`,600690:`海尔智家`,300750:`宁德时代`,"002594":`比亚迪`,601012:`隆基绿能`,600438:`通威股份`,"002460":`赣锋锂业`,600276:`恒瑞医药`,603259:`药明康德`,"000538":`云南白药`,300760:`迈瑞医疗`,"002415":`海康威视`,"000063":`中兴通讯`,"002230":`科大讯飞`,"002475":`立讯精密`,"002241":`歌尔股份`,688981:`中芯国际`,688111:`金山办公`,603986:`兆易创新`,"002049":`紫光国微`,300782:`卓胜微`,"002371":`北方华创`,688012:`中微公司`,"002463":`沪电股份`,"002815":`崇达技术`,"002050":`三花智控`,"000807":`云铝股份`,601138:`工业富联`,"002352":`顺丰控股`,601888:`中国中免`,"000725":`京东方A`,"002714":`牧原股份`,300498:`温氏股份`,601111:`中国国航`,600029:`南方航空`,600150:`中国船舶`,601989:`中国重工`,600893:`航发动力`,"002179":`中航光电`,300059:`东方财富`,600031:`三一重工`};function S(e){if(e.enabled===!1)return!1;if(e.expires_at){let t=new Date(e.expires_at).getTime();if(Number.isFinite(t)&&t<=Date.now())return!1}return!0}function C(e){let t={};for(let n of e){let e=b(n),r=/([\u4e00-\u9fa5]{2,10})\s*\(?0*(\d{6})\)?/g,i;for(;(i=r.exec(e))!==null;)t[i[2]]=i[1]}return t}function w(e,t){if(!e)return`—`;let n=String(e).replace(/\D/g,``).slice(-6);return x[n]??t[n]??n}const T=e=>String(e??``).replace(/\D/g,``);function E(e,t,n){let r=String(t??``).replace(/\D/g,``).slice(-6),i=String(e??``).trim();return i&&i!==r&&i!==String(t??``)?i:w(t,n)}function D(e){return/^(30|68)/.test(e)?-.1:-.08}function O(e,t=`current`,r=0){let i=e.summary??{},o=Array.isArray(e.accounts)?e.accounts:[],s=e.currentAccount??``,c=Array.isArray(e.positions)?e.positions:[],l=Array.isArray(e.watchRules)?e.watchRules:[],u=C(l),d=l.filter(e=>{let t=e.account;return t!=null&&t!==``&&t!==s?!1:S(e)}),f=o.length>1?`<div class="dsh-hld-acct">
         <label for="dsh-hld-account-switch">账户</label>
         <select id="dsh-hld-account-switch"
           onchange="window.__dshHldSwitchAccount && window.__dshHldSwitchAccount(this.value)">
           ${o.map(e=>`<option value="${n(e.account_name)}" ${e.account_name===s?`selected`:``}>${n(e.display_name||e.account_name)}（${e.positions_count??0} 仓）</option>`).join(``)}
         </select>
       </div>`:``,p=i.lastUpdated?a(i.lastUpdated):`—`,m=i.totalValue?i.dailyChange/(i.totalValue-i.dailyChange)*100:0;return`<div class="dsh-hld-board">
  <div class="dsh-hld-topbar">
    <div class="dsh-hld-title">
      <h1>账户持仓看板</h1>
      <div class="sub">只读监控 · 交易操作由 agent 执行</div>
    </div>
    <div class="dsh-hld-tools">
      ${f}
      <div class="dsh-hld-updated">更新于 <b>${n(p)}</b></div>
      <button type="button" class="dsh-hld-refresh" onclick="window.__dshHldRefresh && window.__dshHldRefresh()">↻ 刷新</button>
    </div>
  </div>

  ${k(i,m,e)}

  ${ee(c,u,d)}

  ${j(e)}

  ${N(e,r)}

  ${V(e)}

  ${H(e,t)}
</div>`}function k(e,t,n){let r=y(e.dailyChange),i=y(e.totalPnl),a=Number(n.compliance?.cashRatio??(e.totalValue?e.cash/e.totalValue*100:0)),o=Number(n.compliance?.maxSingleStock??0),s=Number(n.compliance?.maxIndustry??0),c=Number(n.compliance?.maxDrawdown60d??0),l=(n.positions??[]).filter(e=>Number(e.profitLossPct)<=D(e.symbol)+1).length,u=(e,t,n=!1)=>`<span class="dsh-hld-chip ${e?`ok`:n?`warn`:`bad`}">${t} ${e?`✅`:`⚠️`}</span>`;return`<div class="dsh-hld-summary">
  <div class="dsh-hld-sum-top">
    <div class="dsh-hld-sum-pnl">
      <div class="n">今日盈亏</div>
      <div class="v ${r}">${_(e.dailyChange)} <small>${v(t)}</small></div>
    </div>
    <div class="dsh-hld-sum-pnl right">
      <div class="n">持仓盈亏</div>
      <div class="v ${i}">${_(e.totalPnl)} <small>${v(e.totalPnlPct)}</small></div>
    </div>
  </div>
  <div class="dsh-hld-sum-assets">
    <div class="asset-item"><div class="n">总资产</div><div class="v">${g(e.totalValue)}</div></div>
    <div class="asset-item"><div class="n"><span class="legend-dot" style="background:#f56c6c"></span>持仓市值（${e.positions??0} 只）</div><div class="v">${g(e.totalMarketValue)}</div></div>
    <div class="asset-item"><div class="n"><span class="legend-dot" style="background:#e6a23c"></span>可用资金</div><div class="v">${g(e.cash)}</div></div>
  </div>
  <div class="dsh-hld-risk">
    ${u(a>=10,`现金占比 `+a.toFixed(1)+`% · 铁律 ≥10%`)}
    ${u(o<=20,`单股最大 `+o.toFixed(2)+`% · 上限 20%`)}
    ${u(s<=40,`单行业最大 `+s.toFixed(1)+`% · 上限 40%`)}
    ${c>8?u(!1,`60日回撤 -`+c.toFixed(1)+`%（熔断线 -8%）`,!0):u(!0,`60日回撤 `+c.toFixed(1)+`%（熔断线 -8%）`)}
    ${l>0?u(!1,l+` 只临近止损`,!0):u(!0,`无临近止损`)}
  </div>
</div>`}function ee(e,t,n){let r=new Set(n.map(e=>T(e.symbol))),i=e.map(e=>A(e,t,r)).join(``),a=e.length===0?`<tr><td colspan="7" class="dsh-hld-empty">当前账户暂无持仓 — 空仓等待信号是正确决策</td></tr>`:``;return`<div class="dsh-hld-card">
  <div class="hd"><span class="t">持仓明细（${e.length}）</span><span class="more">买卖点参考 = 止损铁律 + 止盈参考(+10%) · 具体交易由 agent 执行</span></div>
  <div class="tblwrap"><table>
    <tr>
      <th>名称/代码</th><th class="r">市值/股数</th><th class="r">现价/成本</th>
      <th class="r">今日盈亏</th><th class="r">持仓盈亏</th><th>买卖点参考</th><th>盯盘</th>
    </tr>
    ${i}${a}
  </table></div>
</div>`}function A(e,t,r){let i=E(e.name,e.symbol,t),a=T(e.symbol),o=D(a),s=(Number(e.avgCost)||0)*(1+o),c=(Number(e.avgCost)||0)*1.1,l=(Number(e.profitLossPct)||0)<=o+1,u=e.currentPrice?(Number(e.currentPrice)-s)/Number(e.currentPrice)*100:0,d=r.has(a),f=l?`<span class="dsh-hld-tag trig">⚠️ 临近止损</span>`:d?`<span class="dsh-hld-tag on">已挂盯盘</span>`:`<span class="dsh-hld-tag off">—</span>`,p=l?`<span class="dsh-hld-sl">⚠️ 临近止损 ${g(s)}（${Math.abs(o*100)}%）</span><br><span class="dsh-hld-s">反弹减 / 止盈参考 ${g(c)}（+10%）</span>`:`<span class="dsh-hld-sl">止损 ${g(s)}（-${Math.abs(o*100)}% 档）</span><br><span class="dsh-hld-s">止盈参考 ${g(c)}（+10%）</span>`;return`<tr>
  <td><span class="sec-name">${n(i)}</span> <span class="sec-code">${n(a)}</span></td>
  <td class="r">${g(e.currentValue,0)}<span class="sub">${e.quantity??0} 股 · 可卖 ${e.sharesAvailable??0}</span></td>
  <td class="r">${g(e.currentPrice)}<span class="sub">成本 ${g(e.avgCost)}</span></td>
  <td class="r ${y(e.profitToday)}">${_(e.profitToday)}<span class="sub">今日</span></td>
  <td class="r ${y(e.profitLoss)}">${_(e.profitLoss)}<span class="sub">${v(e.profitLossPct)}</span></td>
  <td class="bp">
    ${p}
    <span class="src">依据：成本 ${g(e.avgCost)} · 距止损线 +${Math.max(u,0).toFixed(1)}% · 铁律优先不补仓</span>
  </td>
  <td>${f}</td>
</tr>`}function j(e){let t=Array.isArray(e.todayTrades)?e.todayTrades:[];if(t.length===0)return`<div class="dsh-hld-card">
      <div class="hd"><span class="t">今日自动交易（0）</span><span class="more">agent 的买卖动作都会显示在这里</span></div>
      <div class="dsh-hld-emptybox">今日尚无自动交易 — 没有信号时空仓等待是正确决策</div>
    </div>`;let r={BUY:{tag:`buy`,text:`买入`},SELL:{tag:`sell`,text:`卖出`}},i={filled:`✅ 已成交`,partial:`⏳ 部分成交`,pending:`⏳ 待执行`,rejected:`❌ 已拒绝`,cancelled:`— 已撤单`},o=C(e.watchRules??[]),s=t.map(e=>{let t=r[String(e.action??``).toUpperCase()]??{tag:`off`,text:String(e.action??``)},s=Number(e.filled_price)||Number(e.price),c=s*(e.shares??0),l=i[String(e.status??``)]??String(e.status??``);return`<tr>
        <td><span class="dsh-hld-tag ${t.tag}">${t.text}</span></td>
        <td><span class="sec-name">${n(E(e.name,e.symbol,o))}</span> <span class="sec-code">${n(T(e.symbol))}</span></td>
        <td class="r">${g(s)}<span class="sub">× ${e.shares??0} 股</span></td>
        <td class="r">${g(c)}</td>
        <td>${n(String(e.reason??`—`).slice(0,64))}</td>
        <td>${l}</td>
        <td class="dim">${n(a(e.created_at))}</td>
      </tr>`}).join(``);return`<div class="dsh-hld-card">
  <div class="hd"><span class="t">今日自动交易（${t.length}）</span><span class="more">agent 已完成 / 进行中的自动交易</span></div>
  <div class="tblwrap"><table>
    <tr><th>方向</th><th>股票</th><th class="r">成交价</th><th class="r">金额</th><th>理由</th><th>状态</th><th>时间</th></tr>
    ${s}
  </table></div>
</div>`}function M(e,t,n){if(t<=9){let r=``;for(let i=0;i<t;i++)r+=n(i,String(i+1),i===e);return r}let r=[...new Set([0,t-1,e-1,e,e+1].filter(e=>e>=0&&e<t))].sort((e,t)=>e-t),i=``,a=-2;for(let t of r)t-a>1&&(i+=`<span class="gap">…</span>`),i+=n(t,String(t+1),t===e),a=t;return i}function N(e,t){let r=Array.isArray(e.tradeHistory)?e.tradeHistory:[],i=Math.max(1,Math.ceil(r.length/8)),o=Math.min(Math.max(0,Math.trunc(Number(t)||0)),i-1);if(r.length===0)return`<div class="dsh-hld-card" id="dsh-hld-hx">
      <div class="hd"><span class="t">历史交易（0）</span><span class="more">${n(String(e.currentAccount??``))} · agent 成交后自动归档到此</span></div>
      <div class="dsh-hld-emptybox">该账户暂无历史交易记录</div>
    </div>`;let s=r.slice(o*8,(o+1)*8),c=C(e.watchRules??[]),l={BUY:{tag:`buy`,text:`买入`},SELL:{tag:`sell`,text:`卖出`}},u=s.map(e=>{let t=String(e.action??``).toUpperCase(),r=l[t]??{tag:`off`,text:String(e.action??``)},i=Number(e.filled_price)||Number(e.price),o=Number(e.amount)||i*(e.shares??0),s=Number(e.realized_pnl),u=t===`SELL`&&Number.isFinite(s),d=u&&s!==0?y(s):`flat`,f=Number(e.realized_pnl_rate),p=u&&Number.isFinite(f)&&f!==0?`<span class="sub">`+v(f)+`</span>`:``,m=String(e.reason??`—`);return`<tr>
        <td><span class="dsh-hld-tag ${r.tag}">${r.text}</span></td>
        <td><span class="sec-name">${n(E(e.name,e.symbol,c))}</span> <span class="sec-code">${n(T(e.symbol))}</span></td>
        <td class="r">${g(i)}<span class="sub">× ${e.shares??0} 股</span></td>
        <td class="r">${g(o)}</td>
        <td class="r ${d}">${u?_(s)+p:`<span class="dim">—</span>`}</td>
        <td title="${n(m)}">${n(m.slice(0,60))}</td>
        <td class="dim">${n(a(e.created_at))}</td>
      </tr>`}).join(``),d=i<=1?``:`<div class="dsh-hld-pg">
        <button type="button" class="dsh-hld-pgb"${o===0?` disabled`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${o-1})">‹ 上一页</button>
        <span class="dsh-hld-pg-nums">${M(o,i,(e,t,n)=>`<button type="button" class="dsh-hld-pgb${n?` act`:``}"${e===o?` aria-current="page"`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${e})">${t}</button>`)}</span>
        <button type="button" class="dsh-hld-pgb"${o>=i-1?` disabled`:``} onclick="window.__dshHldHistoryPage && window.__dshHldHistoryPage(${o+1})">下一页 ›</button>
        <span class="dsh-hld-pg-cnt">第 ${o+1}/${i} 页 · 共 ${r.length} 笔</span>
      </div>`;return`<div class="dsh-hld-card" id="dsh-hld-hx">
  <div class="hd"><span class="t">历史交易（${r.length}）</span><span class="more">${n(String(e.currentAccount??``))} · agent 全部成交明细 · 倒序</span></div>
  <div class="tblwrap"><table>
    <tr><th>方向</th><th>股票</th><th class="r">成交价</th><th class="r">金额</th><th class="r">实现盈亏</th><th>理由</th><th>时间</th></tr>
    ${u}
  </table></div>
  ${d}
</div>`}function P(e,t,r,i,a){let o=e=>e.account??``,s=e.filter(e=>S(e)),c=s.filter(e=>o(e)===``),l=s.filter(e=>o(e)===r).concat(c),u=[];for(let e of s){let t=o(e);t!==``&&t!==r&&!u.includes(t)&&u.push(t)}let d=new Map;for(let e of i)d.set(e.account_name,e.display_name||e.account_name);let f=e=>d.get(e)??e,p=new Set([`current`,`all`,...u]).has(a)?a:`current`,m=p===`all`?s:p===`current`?l:s.filter(e=>o(e)===p),h=(e,t,r,i)=>`<button type="button" class="dsh-hld-wtab${p===e?` act`:``}" data-wkey="${e}" title="${n(i)}" onclick="window.__dshHldWatchTab && window.__dshHldWatchTab('${e.replace(/'/g,``)}')">${n(t)}<i class="c">${r}</i></button>`,g=[h(`current`,`本账户`,l.length,`当前账户归属 + 通用观察（${f(r)}）`)];for(let e of u)g.push(h(e,f(e),s.filter(t=>o(t)===e).length,`归属账户：${e}`));g.push(h(`all`,`全部`,s.length,`全部账户规则汇总`));let _=m.map(e=>{let i=b(e),a=i.replace(/\s+/g,` `).trim(),s=(e.conditions??[]).map(U).filter(Boolean),c=s.slice(0,3).join(` <span class="dim">·</span> `)+(s.length>3?` <span class="dim">+`+(s.length-3)+`</span>`:``),l=W(i),u=o(e),d=u===``?`off`:u===r?`on`:`oth`,p=u===``?`通用观察`:u===r?`本账户`:f(u);return`<tr>
      <td><span class="sec-name">${n(w(e.symbol,t))}</span> <span class="sec-code">${n(T(e.symbol))}</span></td>
      <td><span class="dsh-hld-tag ${l.cls}">${l.text}</span></td>
      <td class="cond">${c||`<span class="dim">—</span>`}</td>
      <td>${e.enabled?`<span class="dsh-hld-tag on">监控中</span>`:`<span class="dsh-hld-tag off">已停用</span>`}</td>
      <td><span class="dsh-hld-tag ${d}" title="${n(u||`通用观察`)}">${n(p)}</span></td>
      <td class="ctx" title="${n(a.slice(0,400))}">${n(a.slice(0,44))}${a.length>44?`…`:``}</td>
    </tr>`}).join(``),v=p===`current`?`本账户暂无归属/通用观察规则 — 开仓后 agent 会自动挂上止损/止盈盯盘；可切换上方其他账户 / 全部 tab`:p===`all`?`暂无任何盯盘规则`:`该账户暂无归属盯盘规则`,y=m.length===0?`<tr class="dsh-hld-empty"><td colspan="6">`+v+`</td></tr>`:``;return`<div class="dsh-hld-card" id="dsh-hld-watch">
  <div class="hd"><span class="t">盯盘中心（${s.length}）</span><span class="more">账户归属 tab · 默认本账户（含通用观察）· 触发后由 agent 决策，无需人工盯盘</span></div>
  <div class="dsh-hld-wtabs">${g.join(``)}</div>
  <div class="tblwrap"><table>
    <tr><th>股票</th><th>监控性质</th><th>触发条件</th><th>状态</th><th>归属账户</th><th>监控摘要</th></tr>
    ${_}${y}
  </table></div>
</div>`}const F={"v13-simulation-trading":`模拟交易执行`,v13_daily_check:`模拟交易执行`,"v13-risk-check":`风控检查`,v13_risk_check:`风控检查`,"v13-verification":`验证裁决`,v13_verification:`验证裁决`,"v13-weekly-report":`每周报告`,v13_weekly_report:`每周报告`,"v14-simulation-trading":`模拟交易执行`,v14_daily_check:`模拟交易执行`,morning_ai_analysis:`晨间 AI 分析`,realtime_quick_check:`盘中快速检查`,daily_ai_review:`每日 AI 复盘`,daily_recall_audit:`每日回查审计`,weekly_evolution:`周度策略进化`,weekly_memory_distill:`周度记忆蒸馏`,weekly_tool_roi_review:`周度工具 ROI 复盘`,"pre-market-routine":`盘前例行检查`,"afternoon-open-check-live":`午后开盘检查`,"post-market-routine-live":`盘后例行复盘`,"m4-circuit-breaker-live":`M4 回撤熔断巡检`,"weekly-report-m6":`M6 学习飞轮周报`,"agent-brain-morning-analysis":`晨间 AI 分析`,"agent-brain-realtime-check":`盘中快速检查`,"agent-brain-daily-review":`每日 AI 复盘`,"agent-brain-daily-audit":`每日回查审计`,"agent-brain-weekly-evolution":`周度策略进化`,"agent-brain-weekly-distill":`周度记忆蒸馏`,"agent-brain-weekly-roi":`周度工具 ROI 复盘`},I={success:{cls:`ok`,text:`成功`},failed:{cls:`bad`,text:`失败`},skipped:{cls:`wait`,text:`跳过`},pending:{cls:`on`,text:`待执行`},unknown:{cls:`off`,text:`未知`},"":{cls:`off`,text:`从未运行`}};function L(e){let t=String(e??``).trim().split(/\s+/);if(t.length!==5)return String(e||`—`);let[,n,,,r]=t,i=(String(n).padStart(2,`0`)||`--`)+`:`+(t[0].padStart(2,`0`)||`--`),a=String(r);return!a||a===`*`?`每天 `+i:/^\d+$/.test(a)?`周`+`日一二三四五六`[Number(a)%7]+` `+i:/^1-5$/.test(a)?`工作日 `+i:/^(0|6)(,(0|6))?$/.test(a)?`周末 `+i:/^1-5$/.test(a.replace(/,/g,`-`))?`工作日 `+i:a+` `+i}const R={v2:`quantsys-v2 引擎 cron 自动执行（不走 agent）`,ts:`fin-agent（agent-ts）智能体执行`,dh:`agent-dh · investor 例行执行`};function z(e){return e!==`v2`&&e!==`ts`&&e!==`dh`?`<span class="dim">—</span>`:`<span class="dsh-hld-echip `+e+`" title="`+n(R[e]??``)+`">`+e+`</span>`}function B(e,t=!0,r=!1,i=``){let o=F[String(e.name)]??F[String(e.command)]??String(e.name||e.command||`?`),s=L(e.scheduleExpr),c=I[String(e.lastStatus??``)]??I.unknown,l=e.lastAt?a(e.lastAt):`—`,u=e.nextRunAt?a(e.nextRunAt):`—`,d=e.todayTriggered>0?e.todaySuccess+`/`+e.todayTriggered:`—`,f=e.enabled,p=f?c.cls:`off`,m=f?c.text:`未启用`,h=[String(e.name||``),String(e.command||``),e.lastError?`最近错误: `+String(e.lastError).slice(0,120):``].filter(Boolean).join(` · `),g=f&&String(e.lastStatus??``)===`failed`,_=t?`<td class="r">${d}</td><td class="dim">${u}</td>`:r?`<td class="op">${g?`<button type="button" class="dsh-hld-solve" data-solve-task="${n(String(e.name||``))}"
              title="投递给 investor 窗口排查处置此任务" onclick="window.__dshHldSolveTask && window.__dshHldSolveTask(this)">我来解决</button>`:`<span class="dim">—</span>`}</td>`:``;return`<tr title="${n(h)}">
    <td><span class="dsh-hld-tag ${p}">${m}</span></td>
    <td>${n(o)}<span class="sub dim"> ${n(e.command)}</span></td>
    <td class="exe">${z(i)}</td>
    <td>${n(s)}</td>
    <td class="dim">${l}</td>
    ${_}
  </tr>`}function V(e){let t=e.automation;if(!t||t.tasks.length===0)return``;let r=t.tasks,i=t.engine===!0,a=i?`引擎定时任务`:`执行例行任务`,o=t.executor?` · `+t.executor:``,s=t.note?`<div class="dsh-hld-auto-note">⚠️ ${n(t.note)}</div>`:``,c=(e.watchRules??[]).filter(e=>e.account===t.accountName&&S(e)).length,l=r.map(e=>i?B(e,!0,!1,t.executorCode):B(e,!1,!0,t.executorCode)).join(``),u=i?`<th class="r">今日 成/触</th><th>下次运行</th>`:`<th>处理</th>`;return`<div class="dsh-hld-card dsh-hld-auto">
  <div class="hd"><span class="t">账户自动化流程</span>
    <span class="more">${n(t.displayName)}${o} · ${r.length} 个${a} · 盯盘规则 ${c} 条（见下方盯盘中心）</span></div>
  ${s}
  <div class="tblwrap"><table class="dsh-hld-autotbl">
    <tr><th>状态</th><th>任务</th><th class="exe">执行</th><th>计划时刻</th><th>上次运行</th>${u}</tr>
    ${l}
  </table></div>
</div>`}function H(e,t){let n=C(e.watchRules??[]);return P(e.watchRules??[],n,e.currentAccount??``,Array.isArray(e.accounts)?e.accounts:[],t)}function U(e){let t=e.params;if(e.type===`price_break`||String(e.operator||``).toLowerCase().includes(`price`)){if(t&&t.price!==void 0&&t.price!==null){let e=t.direction===`above`?`突破`:t.direction===`below`?`跌破`:`触碰`;return`<span class="cond-${t.direction===`above`?`up`:`down`}">${e}${g(t.price)}</span>`}if(e.threshold!==void 0&&e.threshold!==null)return`价格 `+e.threshold}return e.threshold!==void 0&&e.threshold!==null&&e.operator?String(e.operator||e.type).toUpperCase()+` `+e.threshold:String(e.type??e.operator??`条件`)}function W(e){return/止损|风控|破位|减仓保护/.test(e)?{cls:`warn`,text:`止损监控`}:/买入|低吸|介入|加仓|建仓|补仓/.test(e)?{cls:`buy`,text:`买入提醒`}:/卖出|止盈|减仓|高抛|目标价/.test(e)?{cls:`sell`,text:`卖出提醒`}:{cls:`on`,text:`常规监控`}}const G=[`accounts`,`currentAccount`,`summary`,`positions`,`automation`,`compliance`],K=[`watchRules`,`tradeHistory`,`todayTrades`];[...G,...K];function q(e){let t=Array.isArray(e?.parts)?e.parts:[];return K.every(e=>t.includes(e))}function J(e,t){return q(t)?e%4==0?`full`:`hot`:`full`}function Y(e,t,n){return e===`mount`?null:J(e===`open`?1:t,n)}function X(e,t){if(t===void 0||t.length===0)return{...e};let n=t,r={};for(let t of n)t in e&&(r[t]=e[t]);return r}function Z(e){return[`.`+e+`-solve { flex:none; border:1px solid #c6e2ff; background:#ecf5ff; color:#409eff; border-radius:5px; padding:2px 9px; font-size:11.5px; line-height:1.7; cursor:pointer; white-space:nowrap; vertical-align:middle; }`,`.`+e+`-solve:hover { background:#d9ecff; border-color:#79bbff; }`,`.`+e+`-solve:active { background:#c6e2ff; }`,`.`+e+`-solvepop { position:fixed; z-index:9999; min-width:232px; max-width:300px; background:var(--panel,#fff); border:1px solid var(--border,#e4e7ed); border-radius:8px; box-shadow:0 6px 22px rgba(0,0,0,.16); padding:6px; font-size:12.5px; color:var(--body,#606266); }`,`.`+e+`-solvepop-head { padding:4px 8px 7px; color:var(--text,#303133); font-weight:600; font-size:12px; border-bottom:1px solid var(--line,#ebeef5); margin-bottom:4px; }`,`.`+e+`-solvepop-list { display:flex; flex-direction:column; max-height:264px; overflow-y:auto; }`,`.`+e+`-solvepop-item { border:none; background:transparent; text-align:left; padding:5px 8px; border-radius:5px; cursor:pointer; color:var(--body,#606266); font:inherit; font-size:12.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }`,`.`+e+`-solvepop-item:hover { background:var(--hover,rgba(128,128,128,.12)); }`,`.`+e+`-solvepop-item.cur { color:#409eff; font-weight:600; }`,`.`+e+`-solvepop-item.off { color:var(--dim,#909399); font-style:italic; }`,`.`+e+`-solvepop-cancel { width:100%; margin-top:4px; border:none; background:transparent; color:var(--dim,#909399); font:inherit; font-size:12px; padding:4px; cursor:pointer; border-top:1px solid var(--line,#ebeef5); }`,`.`+e+`-solvepop-cancel:hover { color:var(--text,#303133); }`,`.`+e+`-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }`,`.`+e+`-toast.ok { background:#529b2e; }`,`.`+e+`-toast.err { background:#e64545; }`,`.`+e+`-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }`].join(`
`)}function Q(e){let t=`dsh-solve-styles-`+e,n=document.getElementById(t);if(n!==null&&n.tagName===`STYLE`)return()=>n.remove();let r=document.createElement(`style`);return r.id=t,r.textContent=Z(e),(document.head??document.documentElement).appendChild(r),()=>{document.getElementById(t)?.remove()}}function te(e){let t=e.prefix,n,r,i=()=>{r?.(),r=void 0,n!==void 0&&(n.remove(),n=void 0)},a=(e,n)=>{let r=document.createElement(`div`);r.className=t+`-toast `+(n?`ok`:`err`),r.textContent=e,document.body.appendChild(r),window.setTimeout(()=>{r.classList.add(`out`),window.setTimeout(()=>r.remove(),350)},4200)},o=async(t,n,r)=>{let i=e.current();console.log(`[solve-kit] postSolve`,{endpoint:e.endpoint,kind:t,toSession:r,from:i});try{let o=await fetch(e.endpoint,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({kind:t,task:t===`task`?n:void 0,err:t===`error`?n:void 0,from_session:i||void 0,to_session:r})}),s=await o.json().catch(()=>null);if(console.log(`[solve-kit] response`,s),s===null||s.success!==!0){a(`投递失败：`+String(s?.error??`HTTP `+o.status),!1);return}let c=s.data;if(a(c?.delivered===!0?`✓ `+String(c?.note??`已投递`):`⚠ `+String(c?.error??s.error??`投递失败`),c?.delivered===!0),c?.delivered===!0&&c.target?.sessionId)try{let e=window,t=e.__dshHldSessions??e.__dshExecSessions??e.__dshBbdSessions??e.__dshPmSessions??e.__dshHldCtx?.sessions??e.__dshExecCtx?.sessions??e.__dshBbdCtx?.sessions??e.__dshPmCtx?.sessions;t&&typeof t.open==`function`?(console.log(`[solve-kit] auto-opening target session:`,c.target.sessionId),t.open(c.target.sessionId)):console.warn(`[solve-kit] sessions service not available for auto-open`)}catch(e){console.warn(`[solve-kit] failed to auto-open session:`,e)}}catch(e){a(`请求异常：`+String(e instanceof Error?e.message:e),!1)}},s=e=>{let t=e.lastIndexOf(`session-`);return t>=0&&e.length>=t+16?`w-`+e.slice(t+8,t+16):e};return{toast:a,openPicker:(c,l,u)=>{console.log(`[solve-kit] openPicker`,{kind:l,identity:u});let d=e.resolveSnapshot(l,u);if(console.log(`[solve-kit] resolveSnapshot`,d),d===null){a(`⚠ 数据已刷新，请重试`,!1);return}i();let f=c.getBoundingClientRect();(async()=>{let t=null;try{let n=await e.online?.();Array.isArray(n)&&(t=new Set(n.map(String)))}catch{}let n=e.candidates();if(n.length===0&&t!==null&&t.size>0){let r=String(e.current()??``);n=[...t].map(e=>({sid:String(e),label:s(String(e)),current:String(e)===r})),console.warn(`[solve-kit] 会话候选为空，回退在线窗口清单合成候选`,n.length)}if(n.length===0){o(d.kind,d.snap);return}p(n,t,f)})();let p=(a,s,c)=>{let l=document.createElement(`div`);l.className=t+`-solvepop`;let u=document.createElement(`div`);u.className=t+`-solvepop-head`,u.textContent=`投递给窗口排查处置`+(s===null?``:`（● 当前 / ○ 在线 / ○离线）`),l.appendChild(u);let f=document.createElement(`div`);f.className=t+`-solvepop-list`;let p=(e,n)=>{let r=document.createElement(`button`);return r.type=`button`,r.className=t+`-solvepop-item`+(e.current?` cur`:``)+(n?``:` off`),r.textContent=(e.current?`● `:`○ `)+e.label+(n?``:`（离线）`),r.addEventListener(`click`,()=>{if(!n){if(!window.confirm(`窗口「`+e.label+`」不在线（agent 未加载），直接投递必失败。

确定改投到当前在线窗口处理吗？
（或先到该窗口发一条消息激活后再重试）`))return;i(),o(d.kind,d.snap);return}i(),o(d.kind,d.snap,e.sid)}),r},m=a.filter(e=>s===null||e.current||s.has(e.sid)),h=a.filter(e=>!(s===null||e.current||s.has(e.sid)));m.sort((e,t)=>Number(t.current)-Number(e.current));for(let e of m)f.appendChild(p(e,!0));if(h.length>0){let e=document.createElement(`div`);e.style.display=`none`;for(let t of h)e.appendChild(p(t,!1));let n=document.createElement(`button`);n.type=`button`,n.className=t+`-solvepop-cancel`;let r=e=>{n.textContent=(e?`▾ 收起离线窗口`:`▸ 显示离线/已归档窗口`)+`（`+h.length+`）`};r(!1),n.addEventListener(`click`,()=>{let t=e.style.display!==`none`;e.style.display=t?`none`:``,r(!t)}),f.appendChild(n),f.appendChild(e)}l.appendChild(f);let g=document.createElement(`button`);g.type=`button`,g.className=t+`-solvepop-cancel`,g.textContent=`取消`,g.addEventListener(`click`,i),l.appendChild(g);let _;try{_=typeof e.host==`function`?e.host():e.host}catch{_=void 0}(_??document.body).appendChild(l),n=l;let v=40+(m.length+ +(h.length>0))*30+32,y=c.bottom+6;y+v>window.innerHeight&&(y=Math.max(6,c.top-v-6)),l.style.position=`fixed`,l.style.left=Math.max(6,Math.min(c.left,Math.max(6,window.innerWidth-280)))+`px`,l.style.top=y+`px`;let b=e=>{let t=e.target;t!==null&&l.contains(t)||(document.removeEventListener(`click`,b,!0),r=void 0,i())};document.addEventListener(`click`,b,!0),r=()=>document.removeEventListener(`click`,b,!0)}},close:i}}let $;function ne(){let e=`agent_brain`,t=`current`,n=0,r,i,a=0,o=0,s=async(t,n=`full`)=>{let i=++o,a=t;try{let s=`/dashboard/api/holdings?account=`+encodeURIComponent(t)+(n===`hot`?`&parts=hot`:``),l=await(await fetch(s)).json();if(!l.success)throw Error(l.error||`Unknown error`);let u=l.data;if(i!==o){console.log(`[dashboard-holdings] 丢弃过期响应（有更新的请求在后）: `+a);return}if(a!==e){console.log(`[dashboard-holdings] 丢弃跨账户响应: `+a+`（当前 `+e+`）`);return}let d=r===void 0?{...u,currentAccount:a,parts:u.parts}:{...r,...X(u,u.parts),currentAccount:a,parts:u.parts};c(d)}catch(e){console.error(`[dashboard-holdings] fetch failed:`,e),l(String(e))}},c=e=>{r=e;let a=$;if(!a){console.error(`[dashboard-holdings] 渲染失败：右栏看板容器尚未挂载 [data-dsh-hld-view]（容器由页面挂载层在右侧栏 tab 里创建；找不到时数据会全部丢失）`),i===void 0&&(i=window.setTimeout(()=>{i=void 0;let r=$;r?(console.log(`[dashboard-holdings] 重试成功：容器已就绪，补渲染`),r.innerHTML=O(e,t,n)):console.error(`[dashboard-holdings] 重试仍失败：容器始终未出现 —— 看板将无法显示任何数据`)},400));return}a.innerHTML=O(e,t,n),console.log(`[dashboard-holdings] 已渲染：账户=`+(e.currentAccount??`?`)+`，账户数=`+(e.accounts?.length??0)+`，持仓行=`+(e.positions?.length??0))},l=e=>{let t=$;t&&(t.innerHTML=`<div class="dsh-hld-board"><div class="dsh-hld-wrap"><div class="dsh-hld-head"><h1 class="dsh-hld-title">持仓看板</h1></div><div class="dsh-hld-banner show">数据加载失败: `+e+`</div></div></div>`)},u=e=>{let n=String(e||`current`);if(n===t||(t=n,!r))return;let i=$?.querySelector(`#dsh-hld-watch`)??null;if(i===null){c(r);return}let a=document.createElement(`template`);a.innerHTML=H(r,t);let o=a.content.firstElementChild;if(o===null){c(r);return}i.replaceWith(o)},d=e=>{let t=r?.tradeHistory?.length??0,i=Math.max(1,Math.ceil(t/8)),a=Math.max(0,Math.min(Math.trunc(Number(e)||0),i-1));if(a===n||(n=a,!r))return;let o=$?.querySelector(`#dsh-hld-hx`)??null;if(o===null){c(r);return}let s=document.createElement(`template`);s.innerHTML=N(r,n);let l=s.content.firstElementChild;if(l===null){c(r);return}o.replaceWith(l)},f=te({endpoint:`/dashboard/api/holdings/solve`,prefix:`dsh-hld`,candidates:()=>[],current:()=>{let e=window;try{return String((e.__dshHldSessions??e.__dshHldCtx?.sessions)?.list?.getSnapshot?.().current??``)}catch{return``}},resolveSnapshot:(e,t)=>{if(e!==`task`)return null;let n=r?.automation;if(!n||n.engine===!0)return null;let i=(n.tasks??[]).find(e=>String(e.name)===String(t.name??``));if(!i)return null;let a=String(r?.summary?.lastUpdated??``);return{kind:`task`,snap:{name:i.name,src:String(i.command||`Agent OS 调度任务`),scheduleExpr:i.scheduleExpr,nextRunAt:i.nextRunAt,lastRun:{status:i.lastStatus,triggeredAt:i.lastAt,finishedAt:i.lastAt,err:i.lastError},todayTriggered:i.todayTriggered,todaySuccess:i.todaySuccess,fetchedAt:a,error:i.lastError}}}});return{openBoard:()=>void 0,closeBoard:()=>void 0,toggleBoard:()=>void 0,getSnapshot:()=>({boardOpen:!1}),refresh:()=>{a+=1;let t=Y(`poll`,a,r);t!==null&&(console.log(`[dashboard-holdings] refresh (`+t+`)`),s(e,t))},refreshOnOpen:()=>{a=0;let t=Y(`open`,1,r);t!==null&&(console.log(`[dashboard-holdings] open refresh (`+t+`)`),s(e,t))},switchAccount:r=>{console.log(`[dashboard-holdings] switching account to`,r),e=r,t=`current`,n=0,a=0,s(r)},watchSwitch:u,historyPageSwitch:d,solveTask:e=>{if(!e)return;let t=String(e.dataset?.solveTask??``);t&&f.openPicker(e,`task`,{name:t})}}}function re(e,t){let n=document.createElement(`div`);n.setAttribute(`data-dsh-hld-view`,``),n.className=`dsh-hld-view`,t.appendChild(n),$=n,window.__dshHldRefresh=()=>e.refresh(),window.__dshHldSwitchAccount=t=>e.switchAccount(t),window.__dshHldWatchTab=t=>e.watchSwitch(String(t)),window.__dshHldHistoryPage=t=>e.historyPageSwitch(Number(t)),window.__dshHldSolveTask=t=>e.solveTask(t),e.refreshOnOpen();let r=window.setInterval(()=>{document.hidden||e.refresh()},15e3);return console.log(`[dashboard-holdings] board mounted in right sidebar tab`),()=>{window.clearInterval(r),delete window.__dshHldRefresh,delete window.__dshHldSwitchAccount,delete window.__dshHldWatchTab,delete window.__dshHldHistoryPage,delete window.__dshHldSolveTask,$===n&&($=void 0),n.remove(),console.log(`[dashboard-holdings] board unmounted`)}}function ie(e){return l({prefix:`dsh-hld`,icon:`<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 2 V8 L12 11"/><path d="M8 8 L4 5"/></svg>`,label:`账户持仓`,title:`账户持仓看板`,controller:e})}function ae(){let e=`dsh-hld-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
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

/* 看板正文在右侧栏 tab 内常显（右栏自带显隐与折叠） */
.dsh-hld-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
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
`,(document.head??document.documentElement).appendChild(t)}const oe=[`slots`,`sessions`,`workspaces`,`sidebarRight`,`sidebarRightTabs`];function se(e){try{try{window.__dshHldCtx=e,window.__dshHldSessions=e.sessions,window.__dshHldWorkspaces=e.workspaces}catch{}ae(),Q(`dsh-hld`),s(`dsh-hld`),window.__dshHldClient?.dispose();let t=ne(),n=h(e,{id:`@pi-investment/dashboard-holdings`,kind:`dashboard-holdings`,title:`账户持仓`,mount:e=>re(t,e)}),r=ie({isActive:()=>n.isActive(),toggle:()=>{if(n.isActive()){n.close();return}n.open()||c(`请先打开一个会话 —— 右侧栏需要有会话才能停靠看板`,!1,`dsh-hld`)}});window.__dshHldClient={dispose:()=>{r(),n.dispose()}}}catch(e){console.error(`[dashboard-holdings] client half failed to start:`,e)}}exports.apply=se,exports.inject=oe,exports.name=`@pi-investment/dashboard-holdings/client`;