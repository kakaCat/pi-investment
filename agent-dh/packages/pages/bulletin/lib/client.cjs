Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});const e=`[data-dsh-bbd-view]`,t=`data-dsh-bbd-active`,n=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-exec-active`,`data-dsh-hld-active`],r=`dsh-panel-activate`;function i(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function a(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}const o=e=>String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e),s=e=>{if(!e)return`—`;let t=new Date(e);if(Number.isNaN(t.getTime()))return String(e).slice(0,16).replace(`T`,` `);let n=e=>String(e).padStart(2,`0`);return t.getFullYear()+`-`+n(t.getMonth()+1)+`-`+n(t.getDate())+` `+n(t.getHours())+`:`+n(t.getMinutes())},c={open:`待认领`,claimed:`已认领`,paused:`暂停`,blocked:`卡住`,done:`已完成`,dropped:`已删除`,archived:`已归档`},l={open:`amber`,claimed:`blue`,paused:`gray`,blocked:`red`,done:`green`,dropped:`gray`,archived:`gray`},u={finding:`发现`,question:`疑问`,review:`复盘`,proposal:`倡议`},d={finding:`finding`,question:`question`,review:`review`,proposal:`proposal`},f=[{key:`active`,label:`悬赏池`},{key:`open`,label:`待认领`},{key:`claimed`,label:`已认领`},{key:`paused`,label:`暂停`},{key:`blocked`,label:`卡住`},{key:`done`,label:`已完成`},{key:`dropped`,label:`已删除`},{key:`all`,label:`全部`}],p=[{key:`all`,label:`全部`},{key:`finding`,label:`发现`},{key:`question`,label:`疑问`},{key:`review`,label:`复盘`},{key:`proposal`,label:`倡议`}],m=e=>(Number(e.open)||0)+(Number(e.claimed)||0)+(Number(e.paused)||0)+(Number(e.blocked)||0)+(Number(e.done)||0)+(Number(e.dropped)||0)+(Number(e.archived)||0);function h(e,t){let n=e=>Number(e)||0;switch(t){case`active`:return n(e.open)+n(e.claimed)+n(e.paused)+n(e.blocked);case`all`:return m(e);default:return n(e[t])}}function g(e,t){let n=e.kind?`<span class="dsh-bbd-kind `+d[e.kind]+`">`+o(u[e.kind]??e.kind)+`</span>`:``,r=e.status===`open`?`<span class="dsh-bbd-badge bounty">悬赏</span>`:``,i=e.stale?`<span class="dsh-bbd-badge stale">滞留超时</span>`:``,a=l[e.status]??`gray`,f=c[e.status]??e.status,p=e.author?o(e.author):`<span class="dim">—</span>`,m=e.assignee?o(e.assignee):`<span class="dim">未认领</span>`,h=(e.moderation_log?.length??0)>0?`<div class="dsh-bbd-log"><div class="dsh-bbd-log-hd">变更记录</div>`+e.moderation_log.map(e=>`<div class="dsh-bbd-log-row"><b>`+o(e.action)+`</b> · `+o(e.actor)+` · `+s(e.timestamp)+(e.note?` — `+o(e.note):``)+`</div>`).join(``)+`</div>`:``,g=e.status===`done`&&e.closed_at?`<span class="dim"> · 完成于 `+s(e.closed_at)+`</span>`:``,_=e.status===`dropped`&&e.drop_reason?`<div class="dsh-bbd-drop">删除原因：`+o(e.drop_reason)+`</div>`:``,v=t?` exp`:``,y=e.status===`open`||e.status===`claimed`||e.status===`paused`||e.status===`blocked`?`<div class="dsh-bbd-acts"><button type="button" class="dsh-bbd-btn solve" data-bbd-solve>我来解决</button><button type="button" class="dsh-bbd-btn delegate" data-bbd-delegate>转交</button><span class="dsh-bbd-acts-hint">认领后任务直投对应窗口，由对方自主处理并闭环</span></div><div class="dsh-bbd-pick" data-bbd-pick hidden><div class="dsh-bbd-pick-hd">转交给哪个窗口？<button type="button" class="dsh-bbd-pick-close" data-bbd-pickclose>✕ 取消</button></div><div class="dsh-bbd-pick-list" data-bbd-picklist></div></div>`:``;return`<article class="dsh-bbd-post `+a+v+`" data-bbd-id="`+o(e.id)+`" title="点击展开/收起全文"><div class="dsh-bbd-bar"></div><div class="dsh-bbd-body"><div class="dsh-bbd-meta-top"><span class="dsh-bbd-status `+a+`">`+o(f)+`</span>`+n+r+i+`</div><h3 class="dsh-bbd-title">`+o(e.title)+`</h3><div class="dsh-bbd-content">`+o(e.content)+`</div>`+_+`<div class="dsh-bbd-meta">作者 <b>`+p+`</b> · 认领人 <b>`+m+`</b> · 认领 `+(Number(e.claim_count)||0)+` 次 · 上报 `+s(e.created_at)+` · v`+(Number(e.revision)||1)+g+`</div>`+h+y+`</div></article>`}function _(e,t){return!Array.isArray(e)||e.length===0?`<section id="dsh-bbd-posts" class="dsh-bbd-posts"><div class="dsh-bbd-emptybox">当前筛选下暂无帖子</div></section>`:`<section id="dsh-bbd-posts" class="dsh-bbd-posts">`+e.map(e=>g(e,t.has(e.id))).join(``)+`</section>`}function v(e){let t=e.page_size||20,n=Math.max(1,Math.ceil((Number(e.total)||0)/t)),r=Math.min(Math.max(1,Number(e.page)||1),n),i=[];for(let e=1;e<=n;e++)i.push(`<button type="button" class="dsh-bbd-pgb`+(e===r?` act`:``)+`" data-bbd-page="`+e+`"`+(e===r?` disabled`:``)+`>`+e+`</button>`);return`<div id="dsh-bbd-pg" class="dsh-bbd-pg"><button type="button" class="dsh-bbd-pgnav" data-bbd-page="`+(r-1)+`"`+(r<=1?` disabled`:``)+`>上一页</button><span class="dsh-bbd-pg-nums">`+i.join(``)+`</span><button type="button" class="dsh-bbd-pgnav" data-bbd-page="`+(r+1)+`"`+(r>=n?` disabled`:``)+`>下一页</button><span class="dsh-bbd-pg-cnt">共 `+(Number(e.total)||0)+` 条 · 第 `+r+`/`+n+` 页</span></div>`+(e.rangeNote?`<div class="dsh-bbd-rangenote">`+o(e.rangeNote)+`</div>`:``)}function y(e,t,n){let r=e.degraded?`<div class="dsh-bbd-banner show">数据源（Agent OS）不可达，以下为降级空数据：`+o(e.error??``)+` —— 数据来自 board_post/board_read 工具同源 memory（tag office:board）。</div>`:`<div class="dsh-bbd-banner"></div>`,i=f.map(n=>`<button type="button" class="dsh-bbd-pill`+(t.status===n.key?` act`:``)+`" data-bbd-status="`+n.key+`">`+o(n.label)+`<i class="c">`+h(e.counts,n.key)+`</i></button>`).join(``),a=p.map(e=>`<button type="button" class="dsh-bbd-pill kind`+(t.kind===e.key?` act`:``)+`" data-bbd-kind="`+e.key+`">`+o(e.label)+`</button>`).join(``);return`<div class="dsh-bbd-board"><div class="dsh-bbd-wrap"><div class="dsh-bbd-head"><h1 class="dsh-bbd-title">公告板<span class="sub">Agent OS · 我来解决/转交 → 任务直投窗口，board_update 闭环</span></h1><div class="dsh-bbd-tools">`+(Number(e.staleActive)>0?`<span class="dsh-bbd-chip warn">滞留超 48h `+(Number(e.staleActive)||0)+`</span>`:`<span class="dsh-bbd-chip ok">滞留超 48h 0</span>`)+`<span class="dsh-bbd-updated">更新 <b>`+s(e.fetchedAt)+`</b> · 30s 轮询</span><button type="button" class="dsh-bbd-refresh" id="dsh-bbd-refresh">↻ 刷新</button></div></div>`+r+`<div class="dsh-bbd-filters"><div class="dsh-bbd-frow">`+i+`</div><div class="dsh-bbd-frow kind">`+a+`</div></div>`+_(e.posts,n)+v(e)+`</div></div>`}function b(){let i=!1,a=`active`,o=`all`,s=1,c=new Set,l,u=()=>{let e=new URLSearchParams;return e.set(`status`,a),o!==`all`&&e.set(`kind`,o),e.set(`page`,String(s)),e.set(`page_size`,`20`),`/dashboard/api/bulletin/posts?`+e.toString()},d=()=>{if(!i){i=!0,console.log(`[dashboard-bulletin] opening board`);for(let e of n)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(t,``),window.dispatchEvent(new CustomEvent(r,{detail:`dashboard-bulletin`})),E(),b()}},f=()=>{i&&(i=!1,document.documentElement.removeAttribute(t),D())},p=()=>{i?f():d()},m=()=>{b()},h=e=>{e.status!==void 0&&e.status!==a&&(a=e.status,s=1),e.kind!==void 0&&e.kind!==o&&(o=e.kind,s=1),e.page!==void 0&&Number(e.page)>0&&Number(e.page)!==s&&(s=Math.trunc(Number(e.page))),g()},g=async()=>{try{let e=await(await fetch(u())).json();if(!e?.success)throw Error(e?.error||`Unknown error`);let t=e.data,n=document.getElementById(`dsh-bbd-posts`);if(n===null){S(t);return}let r=document.createElement(`template`);r.innerHTML=_(t.posts,c);let i=r.content.firstElementChild;if(i===null){S(t);return}n.replaceWith(i);let s=document.getElementById(`dsh-bbd-pg`),l=document.createElement(`template`);l.innerHTML=v(t);let d=l.content.firstElementChild;s!==null&&d!==null?s.replaceWith(d):d!==null&&l.content.lastChild&&document.querySelector(`.dsh-bbd-board .dsh-bbd-wrap`)?.appendChild(l.content.lastChild),document.querySelectorAll(`[data-bbd-status]`).forEach(e=>{e.classList.toggle(`act`,e.dataset.bbdStatus===a)}),document.querySelectorAll(`[data-bbd-kind]`).forEach(e=>{e.classList.toggle(`act`,e.dataset.bbdKind===o)})}catch(e){console.error(`[dashboard-bulletin] partial fetch failed:`,e),w(String(e))}},b=async()=>{try{let e=await(await fetch(u())).json();if(!e?.success)throw Error(e?.error||`Unknown error`);S(e.data)}catch(e){console.error(`[dashboard-bulletin] fetch failed:`,e),w(String(e))}},S=t=>{let n=document.querySelector(e);n&&(n.innerHTML=y(t,{status:a,kind:o,page:s},c),C())},C=()=>{for(let e of c){let t=document.querySelector(`[data-bbd-id="`+CSS.escape(e)+`"]`);t!==null&&t.classList.add(`exp`)}},w=t=>{let n=document.querySelector(e);n&&(n.innerHTML=`<div class="dsh-bbd-board"><div class="dsh-bbd-wrap"><div class="dsh-bbd-head"><h1 class="dsh-bbd-title">公告板</h1></div><div class="dsh-bbd-banner show">数据加载失败: `+x(t)+`</div></div></div>`)},T=e=>{c.has(e)?c.delete(e):c.add(e);let t=document.querySelector(`[data-bbd-id="`+CSS.escape(e)+`"]`);t!==null&&t.classList.toggle(`exp`,c.has(e))},E=()=>{D(),l=window.setInterval(()=>{i&&b()},3e4)},D=()=>{l!==void 0&&(clearInterval(l),l=void 0)};return{openBoard:d,closeBoard:f,toggleBoard:p,getSnapshot:()=>({boardOpen:i}),refresh:m,statusTab:e=>h({status:e}),kindTab:e=>h({kind:e}),pageTo:e=>h({page:e}),toggleExpanded:T}}const x=e=>String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e);function S(e){let t,n=()=>{if(t!==void 0)return;let e=a();e!==void 0&&(t=document.createElement(`div`),t.setAttribute(`data-dsh-bbd-view`,``),t.className=`dsh-bbd-view`,e.appendChild(t),console.log(`[dashboard-bulletin] board container mounted`))},i=new MutationObserver(()=>{n()});i.observe(document.body,{childList:!0,subtree:!0}),n(),window.__dshBbdRefresh=()=>e.refresh(),window.__dshBbdStatusTab=t=>e.statusTab(String(t)),window.__dshBbdKind=t=>e.kindTab(String(t)),window.__dshBbdPage=t=>e.pageTo(Number(t));let o=t=>{t.detail!==`dashboard-bulletin`&&e.getSnapshot().boardOpen&&e.closeBoard()};window.addEventListener(r,o);let s=t=>{if(!e.getSnapshot().boardOpen)return;let n=t.target;n!==null&&n.closest(`[data-dsh-bbd-view]`)===null&&n.closest(`[data-dsh-bbd-entry]`)===null&&e.closeBoard()};document.addEventListener(`click`,s,!0);let c=t=>{let n=t.target;if(n===null)return;let r=n.closest(`[data-bbd-solve],[data-bbd-delegate]`);if(r!==null){let e=r.closest(`[data-bbd-id]`)?.dataset.bbdId;if(e){if(r.hasAttribute(`data-bbd-solve`))p(e,`solve`);else{let e=r.closest(`[data-bbd-id]`);e&&f(e)}}return}if(n.closest(`[data-bbd-pickclose]`)!==null){d();return}let i=n.closest(`[data-bbd-picksession]`);if(i!==null&&i.dataset.bbdPicksession){let e=i.closest(`[data-bbd-id]`)?.dataset.bbdId;e&&(d(),p(e,`delegate`,i.dataset.bbdPicksession));return}let a=n.closest(`[data-bbd-id]`);if(a!==null&&a.dataset.bbdId&&n.closest(`button`)===null){e.toggleExpanded(a.dataset.bbdId);return}let o=n.closest(`[data-bbd-status]`);if(o!==null&&o.dataset.bbdStatus){window.__dshBbdStatusTab(o.dataset.bbdStatus);return}let s=n.closest(`[data-bbd-kind]`);if(s!==null&&s.dataset.bbdKind){window.__dshBbdKind(s.dataset.bbdKind);return}let c=n.closest(`[data-bbd-page]`);if(c!==null&&c.dataset.bbdPage){window.__dshBbdPage(c.dataset.bbdPage);return}n.closest(`#dsh-bbd-refresh`)!==null&&window.__dshBbdRefresh()},l=(e,t)=>{let n=document.createElement(`div`);n.className=`dsh-bbd-toast `+(t?`ok`:`err`),n.textContent=e,document.body.appendChild(n),window.setTimeout(()=>{n.classList.add(`out`),window.setTimeout(()=>n.remove(),350)},4200)},u=()=>{let e=window,t=e.__dshBbdSessions;if(!t?.list)try{t=e.__dshBbdCtx?.sessions,t?.list&&(e.__dshBbdSessions=t)}catch{}let n=[];try{let e=t?.list?.getSnapshot?.();if(!e)return n;let r=String(e.current??``),i=Array.isArray(e.items)?e.items:Array.isArray(e.ids)?e.ids.map(t=>e.byId?.[t]).filter(Boolean):[];for(let e of i){let t=String(e?.id??e?.sessionId??``);!t||e.blank||n.push({sid:t,label:String(e.displayTitle??e.title??t),current:t===r})}}catch{}return n},d=()=>{document.querySelectorAll(`[data-bbd-pick]:not([hidden])`).forEach(e=>{e.hidden=!0})},f=e=>{let t=e.querySelector(`[data-bbd-pick]`);if(t===null)return;if(!t.hidden){t.hidden=!0;return}d();let n=t.querySelector(`[data-bbd-picklist]`),r=u();n!==null&&(n.innerHTML=r.length===0?`<div class="dsh-bbd-pick-empty">暂无可转窗口（会话列表为空或未就绪）——请稍候重试或点「我来解决」</div>`:r.map(e=>`<button type="button" class="dsh-bbd-picksession`+(e.current?` cur`:``)+`" data-bbd-picksession="`+x(e.sid)+`">`+x(e.label)+(e.current?`<i>当前</i>`:``)+`</button>`).join(``)),t.hidden=!1},p=async(t,n,r)=>{let i=``;try{i=String(window.__dshBbdSessions?.list?.getSnapshot?.()?.current??``)}catch{}let a=document.querySelector(`[data-bbd-id="`+CSS.escape(t)+`"] [data-bbd-`+(n===`solve`?`solve`:`delegate`)+`]`),o=a?.textContent??``;a!==null&&(a.disabled=!0,a.textContent=`处理中…`),l(`正在`+(n===`solve`?`认领`:`转交`)+`…`,!0);try{let a=await fetch(`/dashboard/api/bulletin/action`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({post_id:t,action:n,to_session:r,from_session:i||void 0})}),o=await a.json().catch(()=>null);if(o===null||o.success!==!0){l(`动作失败：`+(o?.error??`HTTP `+a.status),!1);return}let s=o.data?.delivery?.delivered===!0;l((s?`✓ `:`⚠ `)+String(o.data?.note??`已认领，等待窗口闭环`),s),e.refresh()}catch(e){l(`请求异常：`+String(e instanceof Error?e.message:e),!1)}finally{a!==null&&(a.disabled=!1,a.textContent=o)}};return document.addEventListener(`click`,c,!0),()=>{window.removeEventListener(r,o),document.removeEventListener(`click`,s,!0),document.removeEventListener(`click`,c,!0),i.disconnect(),t!==void 0&&t.remove(),delete window.__dshBbdRefresh,delete window.__dshBbdStatusTab,delete window.__dshBbdKind,delete window.__dshBbdPage,console.log(`[dashboard-bulletin] board unmounted`)}}function C(e){let t,n=()=>{let t=document.createElement(`button`);return t.type=`button`,t.className=`dsh-bbd-entry`,t.dataset.dshBbdEntry=``,t.setAttribute(`aria-label`,`公告板`),t.title=`公告板`,t.innerHTML=`<svg width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='currentColor' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><rect x='3' y='2.5' width='10' height='11' rx='1.5'/><path d='M6 6.5h4M6 9h4'/></svg><span class="dsh-bbd-entry-label">公告板</span>`,t.addEventListener(`click`,t=>{t.preventDefault(),t.stopPropagation(),e.toggle()}),t},r=()=>{let e=i();if(e===void 0)return!1;if(e.querySelector(`[data-dsh-bbd-entry]`)!==null){let n=e.querySelector(`[data-dsh-bbd-entry]`);return n!==void 0&&t===void 0&&(t=n),!0}let r=n(),a=e.querySelector(`[class*="logoRow"]`);return a!==null&&a.nextSibling!==null?e.insertBefore(r,a.nextSibling):e.prepend(r),t=r,!0};r();let a=new MutationObserver(()=>{(t===void 0||!document.contains(t)||t.parentElement===null)&&r()});a.observe(document.body,{childList:!0,subtree:!0});let o=window.setInterval(()=>{(t===void 0||!document.contains(t))&&r()},5e3),s=()=>{t?.setAttribute(`data-active`,e.isActive()?`true`:`false`)},c=window.setInterval(s,1e3);return s(),()=>{a.disconnect(),window.clearInterval(o),window.clearInterval(c),t?.remove(),t=void 0}}function w(){let e=`dsh-bbd-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
/* ============================== 顶部侧栏入口（phase1） ============================== */
.dsh-bbd-entry {
  display: flex; align-items: center; gap: 8px; position: relative;
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border: none; border-radius: 8px; background: transparent;
  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
  cursor: pointer; text-align: left;
}
.dsh-bbd-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-bbd-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
.dsh-bbd-entry svg { flex: none; }
[data-sidebar-collapsed] [data-dsh-bbd-entry],
[class*="_collapsed"] [data-dsh-bbd-entry] {
  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
  justify-content: center; gap: 0; text-align: center;
}
[data-sidebar-collapsed] [data-dsh-bbd-entry] .dsh-bbd-entry-label,
[class*="_collapsed"] [data-dsh-bbd-entry] .dsh-bbd-entry-label { display: none; }
[data-sidebar-collapsed] [data-dsh-bbd-entry] svg,
[class*="_collapsed"] [data-dsh-bbd-entry] svg { width: 16px; height: 16px; }

/* ============================== 中心栏看板主体（phase2） ============================== */
/* 显隐开关：会话列隐藏除本板视图外的子节点（各代 selector 都盖到） */
html[data-dsh-bbd-active] [data-pane="conversation"] > *:not([data-dsh-bbd-view]),
html[data-dsh-bbd-active] [class*="centerCol"] > *:not([data-dsh-bbd-view]),
html[data-dsh-bbd-active] .dshDesktopConversationSurface > *:not([data-dsh-bbd-view]) {
  display: none !important;
}
.dsh-bbd-view { display: none; }
html[data-dsh-bbd-active] .dsh-bbd-view {
  display: flex; flex-direction: column; height: 100%; overflow: hidden;
}

.dsh-bbd-board {
  flex: 1; min-height: 0; overflow-y: auto;
  background: #f0f2f5; padding: 18px 22px 56px;
}
.dsh-bbd-wrap { max-width: 960px; margin: 0 auto; }

/* header */
.dsh-bbd-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 6px;
}
.dsh-bbd-title { margin: 0; font-size: 19px; line-height: 1.3; color: #1f2328; }
.dsh-bbd-title .sub { margin-left: 10px; font-size: 12px; font-weight: 400; color: #8a9199; }
.dsh-bbd-tools { display: flex; align-items: center; gap: 10px; }
.dsh-bbd-chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; background: #fff; border: 1px solid #e5e8ec; color: #57606a; }
.dsh-bbd-chip.warn { color: #b45309; background: #fef3c7; border-color: #fde68a; }
.dsh-bbd-chip.ok { color: #059669; background: #ecfdf5; border-color: #a7f3d0; }
.dsh-bbd-updated { font-size: 12px; color: #8a9199; }
.dsh-bbd-updated b { color: #57606a; font-weight: 600; }
.dsh-bbd-refresh {
  border: 1px solid #d0d5da; background: #fff; color: #374151;
  border-radius: 7px; padding: 4px 12px; font-size: 12px; cursor: pointer;
}
.dsh-bbd-refresh:hover { background: #f6f8fa; }

/* degraded banner（RFC D4：Agent OS 不可达显示提示而非白屏） */
.dsh-bbd-banner { display: none; }
.dsh-bbd-banner.show {
  display: block; margin: 10px 0 14px; padding: 10px 14px;
  background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412;
  border-radius: 8px; font-size: 13px; line-height: 1.6;
}

/* 过滤条 */
.dsh-bbd-filters { margin: 8px 0 14px; display: flex; flex-direction: column; gap: 8px; }
.dsh-bbd-frow { display: flex; flex-wrap: wrap; gap: 6px; }
.dsh-bbd-pill {
  display: inline-flex; align-items: center; gap: 6px;
  border: 1px solid #d0d5da; background: #fff; color: #4b5563;
  border-radius: 999px; padding: 4px 12px; font-size: 12.5px; cursor: pointer;
}
.dsh-bbd-pill:hover { border-color: #98a2b3; }
.dsh-bbd-pill.act { background: #2563eb; border-color: #2563eb; color: #fff; font-weight: 500; }
.dsh-bbd-pill i.c {
  font-style: normal; font-size: 11px; min-width: 16px; padding: 0 4px; text-align: center;
  background: rgba(0,0,0,.06); border-radius: 999px; color: inherit;
}
.dsh-bbd-pill.act i.c { background: rgba(255,255,255,.22); }
.dsh-bbd-frow.kind .dsh-bbd-pill { font-size: 12px; padding: 2px 10px; }
.dsh-bbd-frow.kind .dsh-bbd-pill.act { background: #374151; border-color: #374151; }

/* 帖子卡（单列） */
.dsh-bbd-posts { display: flex; flex-direction: column; gap: 10px; }
.dsh-bbd-post {
  display: flex; background: #fff; border: 1px solid #e5e8ec;
  border-radius: 10px; overflow: hidden; cursor: pointer;
  transition: box-shadow .12s ease;
}
.dsh-bbd-post:hover { box-shadow: 0 2px 10px rgba(17,24,39,.08); }
.dsh-bbd-bar { width: 4px; flex: none; }
.dsh-bbd-post.amber .dsh-bbd-bar { background: #f59e0b; }
.dsh-bbd-post.blue  .dsh-bbd-bar { background: #3b82f6; }
.dsh-bbd-post.red   .dsh-bbd-bar { background: #ef4444; }
.dsh-bbd-post.green .dsh-bbd-bar { background: #10b981; }
.dsh-bbd-post.gray  .dsh-bbd-bar { background: #9ca3af; }
.dsh-bbd-post.done  { opacity: .62; }
.dsh-bbd-post.dropped { opacity: .5; }
.dsh-bbd-post.dropped .dsh-bbd-title { text-decoration: line-through; color: #6b7280; }
.dsh-bbd-body { flex: 1; min-width: 0; padding: 12px 16px 11px; }

.dsh-bbd-meta-top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.dsh-bbd-status {
  font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 999px;
}
.dsh-bbd-status.amber { color: #92400e; background: #fef3c7; }
.dsh-bbd-status.blue  { color: #1e40af; background: #dbeafe; }
.dsh-bbd-status.red   { color: #991b1b; background: #fee2e2; }
.dsh-bbd-status.green { color: #065f46; background: #d1fae5; }
.dsh-bbd-status.gray  { color: #4b5563; background: #f3f4f6; }
.dsh-bbd-kind {
  font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid transparent;
}
.dsh-bbd-kind.finding  { color: #1e40af; background: #eff6ff; border-color: #bfdbfe; }
.dsh-bbd-kind.question { color: #6b21a8; background: #faf5ff; border-color: #e9d5ff; }
.dsh-bbd-kind.review   { color: #065f46; background: #ecfdf5; border-color: #a7f3d0; }
.dsh-bbd-kind.proposal { color: #9a3412; background: #fff7ed; border-color: #fed7aa; }
.dsh-bbd-badge { font-size: 11px; padding: 1px 8px; border-radius: 999px; }
.dsh-bbd-badge.bounty { color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; }
.dsh-bbd-badge.stale { color: #b91c1c; background: #fff1f2; border: 1px solid #fecaca; }

.dsh-bbd-title { margin: 0 0 5px; font-size: 15px; line-height: 1.45; color: #1f2328;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.dsh-bbd-content { color: #4b5563; font-size: 13px; line-height: 1.65; white-space: pre-wrap; word-break: break-word;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.dsh-bbd-post.exp .dsh-bbd-title, .dsh-bbd-post.exp .dsh-bbd-content { display: block; -webkit-line-clamp: unset; }
.dsh-bbd-drop { margin-top: 6px; font-size: 12px; color: #b91c1c; }
.dsh-bbd-log { display: none; margin-top: 10px; padding: 8px 10px; background: #f9fafb;
  border-radius: 6px; border: 1px solid #eef0f3; font-size: 12px; }
.dsh-bbd-post.exp .dsh-bbd-log { display: block; }
.dsh-bbd-log-hd { color: #6b7280; font-weight: 600; margin-bottom: 5px; }
.dsh-bbd-log-row { color: #4b5563; line-height: 1.7; }
.dsh-bbd-log-row b { color: #1f2328; }
.dsh-bbd-meta {
  margin-top: 10px; padding-top: 8px; border-top: 1px dashed #eceef1;
  font-size: 12px; color: #8a9199; line-height: 1.7;
}
.dsh-bbd-meta b { color: #57606a; font-weight: 600; }
.dsh-bbd-meta .dim { color: #b6bcc3; }

.dsh-bbd-emptybox {
  padding: 46px 20px; text-align: center; color: #8a9199; font-size: 13px;
  background: #fff; border: 1px dashed #d0d5da; border-radius: 10px;
}

/* 分页 */
.dsh-bbd-pg {
  display: flex; align-items: center; gap: 8px; margin-top: 16px; flex-wrap: wrap;
}
.dsh-bbd-pgnav, .dsh-bbd-pgb {
  border: 1px solid #d0d5da; background: #fff; color: #374151;
  border-radius: 6px; padding: 3px 10px; font-size: 12px; cursor: pointer;
}
.dsh-bbd-pgnav:disabled, .dsh-bbd-pgb:disabled { opacity: .45; cursor: default; }
.dsh-bbd-pgb.act { background: #2563eb; border-color: #2563eb; color: #fff; }
.dsh-bbd-pg-nums { display: inline-flex; gap: 5px; }
.dsh-bbd-pg-cnt { margin-left: auto; font-size: 12px; color: #8a9199; }
.dsh-bbd-rangenote { margin-top: 4px; text-align: right; font-size: 11.5px; color: #b6bcc3; }

/* Task #2：认领/转交动作行 + 转交选择器 + toast */
.dsh-bbd-acts {
  margin-top: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.dsh-bbd-btn {
  border: 1px solid #d0d5da; background: #fff; color: #374151;
  border-radius: 6px; padding: 3px 12px; font-size: 12px; cursor: pointer; line-height: 1.5;
}
.dsh-bbd-btn:hover:not(:disabled) { border-color: #2563eb; color: #2563eb; }
.dsh-bbd-btn:disabled { opacity: .5; cursor: default; }
.dsh-bbd-btn.solve { background: #2563eb; border-color: #2563eb; color: #fff; }
.dsh-bbd-btn.solve:hover:not(:disabled) { background: #1d4ed8; color: #fff; }
.dsh-bbd-btn.delegate { background: #f9fafb; }
.dsh-bbd-acts-hint { font-size: 11px; color: #b6bcc3; }
.dsh-bbd-pick {
  margin-top: 8px; padding: 8px 10px; background: #f6f8fa; border: 1px solid #e2e6ea;
  border-radius: 8px;
}
.dsh-bbd-pick-hd {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  font-size: 12px; color: #374151; margin-bottom: 6px;
}
.dsh-bbd-pick-close {
  border: none; background: transparent; color: #8a9199; cursor: pointer; font-size: 12px; padding: 0 2px;
}
.dsh-bbd-pick-close:hover { color: #b91c1c; }
.dsh-bbd-pick-list { display: flex; flex-direction: column; gap: 4px; max-height: 180px; overflow-y: auto; }
.dsh-bbd-picksession {
  text-align: left; border: 1px solid #d0d5da; background: #fff; color: #374151;
  border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer;
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.dsh-bbd-picksession:hover { border-color: #2563eb; color: #2563eb; }
.dsh-bbd-picksession.cur { border-color: #93c5fd; background: #eff6ff; }
.dsh-bbd-picksession i {
  font-style: normal; font-size: 10.5px; color: #2563eb; background: #dbeafe;
  padding: 0 6px; border-radius: 999px;
}
.dsh-bbd-pick-empty { font-size: 12px; color: #8a9199; }
.dsh-bbd-toast {
  position: fixed; top: 14px; right: 16px; z-index: 9999; max-width: min(420px, 70vw);
  padding: 9px 14px; border-radius: 8px; font-size: 13px; line-height: 1.55;
  box-shadow: 0 6px 22px rgba(15, 23, 42, .16); opacity: 1;
  transition: opacity .35s ease; word-break: break-word;
}
.dsh-bbd-toast.ok { background: #065f46; color: #ecfdf5; border: 1px solid #34d399; }
.dsh-bbd-toast.err { background: #7f1d1d; color: #fef2f2; border: 1px solid #f87171; }
.dsh-bbd-toast.out { opacity: 0; }
`,(document.head??document.documentElement).appendChild(t)}const T=[`sessions`];function E(e){try{window.__dshBbdCtx=e,window.__dshBbdSessions=e?.sessions}catch{}try{w(),window.__dshBbdClient?.dispose?.();let e=b(),t=S(e),n=C({isActive:()=>e.getSnapshot().boardOpen,toggle:()=>e.toggleBoard()});window.__dshBbdClient={dispose:()=>{try{t()}catch{}try{n()}catch{}try{e.closeBoard()}catch{}}},console.info(`[dashboard-bulletin] phase2 board client ready`)}catch(e){console.error(`[dashboard-bulletin] client half failed to start:`,e)}}exports.apply=E,exports.inject=T,exports.name=`@pi-investment/dashboard-bulletin/client`;