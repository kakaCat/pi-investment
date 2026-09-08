window.__ModuleLoader__.load({
		id: "@pi-investment/dashboard-bulletin",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});const e=`dsh-panel-activate`;function t(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function n(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}function r(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}const i=e=>String(e).padStart(2,`0`);function a(e){if(!e)return null;let t=new Date(String(e));return Number.isNaN(t.getTime())?null:t}function o(e,t){if(!e)return`—`;let n=a(e);if(!n)return String(e).slice(0,16).replace(`T`,` `);let r=new Date,o=n.getFullYear()===r.getFullYear()&&n.getMonth()===r.getMonth()&&n.getDate()===r.getDate(),s=i(n.getHours())+`:`+i(n.getMinutes());return t?.omitDateIfToday&&o?s:(t?.withYear?n.getFullYear()+`-`+i(n.getMonth()+1)+`-`+i(n.getDate()):i(n.getMonth()+1)+`-`+i(n.getDate()))+` `+s}function s(e){return[`.`+e+`-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }`,`.`+e+`-toast.ok { background:#529b2e; }`,`.`+e+`-toast.err { background:#e64545; }`,`.`+e+`-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }`].join(`
		`)}function c(e){let t=`dsh-toast-styles-`+e,n=document.getElementById(t);if(n!==null&&n.tagName===`STYLE`)return()=>n.remove();let r=document.createElement(`style`);return r.id=t,r.textContent=s(e),(document.head??document.documentElement).appendChild(r),()=>{document.getElementById(t)?.remove()}}function l(e,t,n,r=4200){let i=document.createElement(`div`);i.className=n+`-toast `+(t?`ok`:`err`),i.textContent=e,document.body.appendChild(i),window.setTimeout(()=>{i.classList.add(`out`),window.setTimeout(()=>i.remove(),350)},r)}function u(e){let{prefix:n,icon:r,label:i,title:a,controller:o}=e,s=n.replace(/-([a-z])/g,(e,t)=>t.toUpperCase())+`Entry`,c=`[data-`+n+`-entry]`,l,u=()=>{let e=document.createElement(`button`);return e.type=`button`,e.className=n+`-entry`,e.dataset[s]=``,e.setAttribute(`aria-label`,a),e.title=a,e.innerHTML=r+`<span class="`+n+`-entry-label">`+i+`</span>`,e.addEventListener(`click`,e=>{e.preventDefault(),e.stopPropagation(),o.toggle()}),e},d=()=>{let e=t();if(e===void 0)return!1;if(e.querySelector(c)!==null){let t=e.querySelector(c);return t!==void 0&&l===void 0&&(l=t),!0}let n=u(),r=e.querySelector(`[class*="logoRow"]`);return r!==null&&r.nextSibling!==null?e.insertBefore(n,r.nextSibling):e.prepend(n),l=n,!0};d();let f=new MutationObserver(()=>{(l===void 0||!document.contains(l)||l.parentElement===null)&&d()});f.observe(document.body,{childList:!0,subtree:!0});let p=window.setInterval(()=>{(l===void 0||!document.contains(l))&&d()},5e3),m=()=>{l?.setAttribute(`data-active`,o.isActive()?`true`:`false`)},h=window.setInterval(m,1e3);return m(),()=>{f.disconnect(),window.clearInterval(p),window.clearInterval(h),l?.remove(),l=void 0}}function d(t){let{panelName:r,activeAttr:i,otherActiveAttrs:a,pollMs:o=3e4,pauseOnHidden:s=!1,dispatchTarget:c=`window`,listenTarget:l=`window`,buildContainer:u,onMount:d,onPoll:f,onOpen:p,onClose:m}=t,h=!1,g,_,v,y=!1,b=()=>{if(g!==void 0||y)return;let e=n();if(e===void 0)return;let t=u();e.appendChild(t),g=t,v=d(t)??void 0},x=new MutationObserver(()=>{b()});x.observe(document.body,{childList:!0,subtree:!0}),b();let S=()=>{if(!(h||y)){h=!0,b();for(let e of a)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(i,``),(c===`document`?document:window).dispatchEvent(new CustomEvent(e,{detail:r})),D(),p?.()}},C=()=>{!h||y||(h=!1,document.documentElement.removeAttribute(i),O(),m?.())},w=()=>{h?C():S()},T=()=>h,E=()=>{h&&f()},D=()=>{O(),_=window.setInterval(E,o)},O=()=>{_!==void 0&&(clearInterval(_),_=void 0)},k=()=>{document.hidden?O():h&&D()};s&&document.addEventListener(`visibilitychange`,k);let A=e=>{if(!h)return;let n=e.target;if(n===null||g!==void 0&&(g===n||g.contains(n)))return;let r=`[data-`+t.prefix+`-entry]`;n.closest(r)===null&&C()};document.addEventListener(`click`,A,!0);let j=e=>{let t=e.detail;t!==void 0&&t!==r&&h&&C()},M=l===`document`?document:window;return M.addEventListener(e,j),{open:S,close:C,toggle:w,isActive:T,dispose:()=>{y||(y=!0,O(),s&&document.removeEventListener(`visibilitychange`,k),document.removeEventListener(`click`,A,!0),M.removeEventListener(e,j),x.disconnect(),v?.(),g?.remove(),g=void 0)}}}const f=`[data-dsh-bbd-view]`,p=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-exec-active`,`data-dsh-hld-active`,`data-dsh-gen-active`],m={open:`待认领`,claimed:`已认领`,paused:`暂停`,blocked:`卡住`,done:`已完成`,dropped:`已删除`,archived:`已归档`},h={open:`amber`,claimed:`blue`,paused:`gray`,blocked:`red`,done:`green`,dropped:`gray`,archived:`gray`},g={finding:`发现`,question:`疑问`,review:`复盘`,proposal:`倡议`},_={finding:`finding`,question:`question`,review:`review`,proposal:`proposal`},v=[{key:`active`,label:`悬赏池`},{key:`open`,label:`待认领`},{key:`claimed`,label:`已认领`},{key:`paused`,label:`暂停`},{key:`blocked`,label:`卡住`},{key:`done`,label:`已完成`},{key:`dropped`,label:`已删除`},{key:`all`,label:`全部`}],y=[{key:`all`,label:`全部`},{key:`finding`,label:`发现`},{key:`question`,label:`疑问`},{key:`review`,label:`复盘`},{key:`proposal`,label:`倡议`}],b=e=>(Number(e.open)||0)+(Number(e.claimed)||0)+(Number(e.paused)||0)+(Number(e.blocked)||0)+(Number(e.done)||0)+(Number(e.dropped)||0)+(Number(e.archived)||0);function x(e,t){let n=e=>Number(e)||0;switch(t){case`active`:return n(e.open)+n(e.claimed)+n(e.paused)+n(e.blocked);case`all`:return b(e);default:return n(e[t])}}function S(e,t){let n=e.kind?`<span class="dsh-bbd-kind `+_[e.kind]+`">`+r(g[e.kind]??e.kind)+`</span>`:``,i=e.status===`open`?`<span class="dsh-bbd-badge bounty">悬赏</span>`:``,a=e.stale?`<span class="dsh-bbd-badge stale">滞留超时</span>`:``,s=h[e.status]??`gray`,c=m[e.status]??e.status,l=e.author?r(e.author):`<span class="dim">—</span>`,u=e.assignee?r(e.assignee):`<span class="dim">未认领</span>`,d=(e.moderation_log?.length??0)>0?`<div class="dsh-bbd-log"><div class="dsh-bbd-log-hd">变更记录</div>`+e.moderation_log.map(e=>`<div class="dsh-bbd-log-row"><b>`+r(e.action)+`</b> · `+r(e.actor)+` · `+o(e.timestamp)+(e.note?` — `+r(e.note):``)+`</div>`).join(``)+`</div>`:``,f=e.status===`done`&&e.closed_at?`<span class="dim"> · 完成于 `+o(e.closed_at)+`</span>`:``,p=e.status===`dropped`&&e.drop_reason?`<div class="dsh-bbd-drop">删除原因：`+r(e.drop_reason)+`</div>`:``,v=t?` exp`:``,y=e.status===`open`||e.status===`claimed`||e.status===`paused`||e.status===`blocked`?`<div class="dsh-bbd-acts"><button type="button" class="dsh-bbd-btn solve" data-bbd-solve>我来解决</button><button type="button" class="dsh-bbd-btn delegate" data-bbd-delegate>转交</button><span class="dsh-bbd-acts-hint">认领后任务直投对应窗口，由对方自主处理并闭环</span></div><div class="dsh-bbd-pick" data-bbd-pick hidden><div class="dsh-bbd-pick-hd">转交给哪个窗口？<button type="button" class="dsh-bbd-pick-close" data-bbd-pickclose>✕ 取消</button></div><div class="dsh-bbd-pick-list" data-bbd-picklist></div></div>`:``;return`<article class="dsh-bbd-post `+s+v+`" data-bbd-id="`+r(e.id)+`" title="点击展开/收起全文"><div class="dsh-bbd-bar"></div><div class="dsh-bbd-body"><div class="dsh-bbd-meta-top"><span class="dsh-bbd-status `+s+`">`+r(c)+`</span>`+n+i+a+`</div><h3 class="dsh-bbd-title">`+r(e.title)+`</h3><div class="dsh-bbd-content">`+r(e.content)+`</div>`+p+`<div class="dsh-bbd-meta">作者 <b>`+l+`</b> · 认领人 <b>`+u+`</b> · 认领 `+(Number(e.claim_count)||0)+` 次 · 上报 `+o(e.created_at)+` · v`+(Number(e.revision)||1)+f+`</div>`+d+y+`</div></article>`}function C(e,t){return!Array.isArray(e)||e.length===0?`<section id="dsh-bbd-posts" class="dsh-bbd-posts"><div class="dsh-bbd-emptybox">当前筛选下暂无帖子</div></section>`:`<section id="dsh-bbd-posts" class="dsh-bbd-posts">`+e.map(e=>S(e,t.has(e.id))).join(``)+`</section>`}function w(e){let t=e.page_size||20,n=Math.max(1,Math.ceil((Number(e.total)||0)/t)),i=Math.min(Math.max(1,Number(e.page)||1),n),a=[];for(let e=1;e<=n;e++)a.push(`<button type="button" class="dsh-bbd-pgb`+(e===i?` act`:``)+`" data-bbd-page="`+e+`"`+(e===i?` disabled`:``)+`>`+e+`</button>`);return`<div id="dsh-bbd-pg" class="dsh-bbd-pg"><button type="button" class="dsh-bbd-pgnav" data-bbd-page="`+(i-1)+`"`+(i<=1?` disabled`:``)+`>上一页</button><span class="dsh-bbd-pg-nums">`+a.join(``)+`</span><button type="button" class="dsh-bbd-pgnav" data-bbd-page="`+(i+1)+`"`+(i>=n?` disabled`:``)+`>下一页</button><span class="dsh-bbd-pg-cnt">共 `+(Number(e.total)||0)+` 条 · 第 `+i+`/`+n+` 页</span></div>`+(e.rangeNote?`<div class="dsh-bbd-rangenote">`+r(e.rangeNote)+`</div>`:``)}function T(e,t,n){let i=e.degraded?`<div class="dsh-bbd-banner show">数据源（Agent OS）不可达，以下为降级空数据：`+r(e.error??``)+` —— 数据来自 board_post/board_read 工具同源公告板存储（RFC 014 独立表）。</div>`:`<div class="dsh-bbd-banner"></div>`,a=v.map(n=>`<button type="button" class="dsh-bbd-pill`+(t.status===n.key?` act`:``)+`" data-bbd-status="`+n.key+`">`+r(n.label)+`<i class="c">`+x(e.counts,n.key)+`</i></button>`).join(``),s=y.map(e=>`<button type="button" class="dsh-bbd-pill kind`+(t.kind===e.key?` act`:``)+`" data-bbd-kind="`+e.key+`">`+r(e.label)+`</button>`).join(``);return`<div class="dsh-bbd-board"><div class="dsh-bbd-wrap"><div class="dsh-bbd-head"><h1 class="dsh-bbd-title">公告板<span class="sub">Agent OS · 我来解决/转交 → 任务直投窗口，board_update 闭环</span></h1><div class="dsh-bbd-tools">`+(Number(e.staleActive)>0?`<span class="dsh-bbd-chip warn">滞留超 48h `+(Number(e.staleActive)||0)+`</span>`:`<span class="dsh-bbd-chip ok">滞留超 48h 0</span>`)+`<span class="dsh-bbd-updated">更新 <b>`+o(e.fetchedAt)+`</b> · 30s 轮询</span><button type="button" class="dsh-bbd-refresh" id="dsh-bbd-refresh">↻ 刷新</button></div></div>`+i+`<div class="dsh-bbd-filters"><div class="dsh-bbd-frow">`+a+`</div><div class="dsh-bbd-frow kind">`+s+`</div></div>`+C(e.posts,n)+w(e)+`</div></div>`}function E(){let e=`active`,t=`all`,n=1,i=new Set,a=()=>{let r=new URLSearchParams;return r.set(`status`,e),t!==`all`&&r.set(`kind`,t),r.set(`page`,String(n)),r.set(`page_size`,`20`),`/dashboard/api/bulletin/posts?`+r.toString()},o=async()=>{try{let n=await(await fetch(a())).json();if(!n?.success)throw Error(n?.error||`Unknown error`);let r=n.data,o=document.getElementById(`dsh-bbd-posts`);if(o===null){c(r);return}let s=document.createElement(`template`);s.innerHTML=C(r.posts,i);let l=s.content.firstElementChild;if(l===null){c(r);return}o.replaceWith(l);let u=document.getElementById(`dsh-bbd-pg`),d=document.createElement(`template`);d.innerHTML=w(r);let f=d.content.firstElementChild;u!==null&&f!==null?u.replaceWith(f):f!==null&&d.content.lastChild&&document.querySelector(`.dsh-bbd-board .dsh-bbd-wrap`)?.appendChild(d.content.lastChild),document.querySelectorAll(`[data-bbd-status]`).forEach(t=>{t.classList.toggle(`act`,t.dataset.bbdStatus===e)}),document.querySelectorAll(`[data-bbd-kind]`).forEach(e=>{e.classList.toggle(`act`,e.dataset.bbdKind===t)})}catch(e){console.error(`[dashboard-bulletin] partial fetch failed:`,e),l(String(e))}},s=async()=>{try{let e=await(await fetch(a())).json();if(!e?.success)throw Error(e?.error||`Unknown error`);c(e.data)}catch(e){console.error(`[dashboard-bulletin] fetch failed:`,e),l(String(e))}},c=r=>{let a=document.querySelector(f);if(a){a.innerHTML=T(r,{status:e,kind:t,page:n},i);for(let e of i){let t=document.querySelector(`[data-bbd-id="`+CSS.escape(e)+`"]`);t!==null&&t.classList.add(`exp`)}}},l=e=>{let t=document.querySelector(f);t&&(t.innerHTML=`<div class="dsh-bbd-board"><div class="dsh-bbd-wrap"><div class="dsh-bbd-head"><h1 class="dsh-bbd-title">公告板</h1></div><div class="dsh-bbd-banner show">数据加载失败: `+r(e)+`</div></div></div>`)},u=r=>{r.status!==void 0&&r.status!==e&&(e=r.status,n=1),r.kind!==void 0&&r.kind!==t&&(t=r.kind,n=1),r.page!==void 0&&Number(r.page)>0&&Number(r.page)!==n&&(n=Math.trunc(Number(r.page))),o()};return{openBoard:()=>void 0,closeBoard:()=>void 0,toggleBoard:()=>void 0,getSnapshot:()=>({boardOpen:!1}),refresh:s,statusTab:e=>u({status:e}),kindTab:e=>u({kind:e}),pageTo:e=>u({page:e}),toggleExpanded:e=>{i.has(e)?i.delete(e):i.add(e);let t=document.querySelector(`[data-bbd-id="`+CSS.escape(e)+`"]`);t!==null&&t.classList.toggle(`exp`,i.has(e))}}}function D(e){window.__dshBbdRefresh=()=>e.refresh(),window.__dshBbdStatusTab=t=>e.statusTab(String(t)),window.__dshBbdKind=t=>e.kindTab(String(t)),window.__dshBbdPage=t=>e.pageTo(Number(t));let t=d({prefix:`dsh-bbd`,panelName:`dashboard-bulletin`,activeAttr:`data-dsh-bbd-active`,otherActiveAttrs:p,pollMs:3e4,buildContainer:()=>{let e=document.createElement(`div`);return e.setAttribute(`data-dsh-bbd-view`,``),e.className=`dsh-bbd-view`,e},onMount:()=>{e.refresh();let t=t=>{let n=t.target;if(n===null)return;let r=n.closest(`[data-bbd-solve],[data-bbd-delegate]`);if(r!==null){let e=r.closest(`[data-bbd-id]`)?.dataset.bbdId;if(e){if(r.hasAttribute(`data-bbd-solve`))j(e,`solve`);else{let e=r.closest(`[data-bbd-id]`);e&&A(e)}}return}if(n.closest(`[data-bbd-pickclose]`)!==null){k();return}let i=n.closest(`[data-bbd-picksession]`);if(i!==null&&i.dataset.bbdPicksession){let e=i.closest(`[data-bbd-id]`)?.dataset.bbdId;e&&(k(),j(e,`delegate`,i.dataset.bbdPicksession));return}let a=n.closest(`[data-bbd-id]`);if(a!==null&&a.dataset.bbdId&&n.closest(`button`)===null){e.toggleExpanded(a.dataset.bbdId);return}let o=n.closest(`[data-bbd-status]`);if(o!==null&&o.dataset.bbdStatus){window.__dshBbdStatusTab(o.dataset.bbdStatus);return}let s=n.closest(`[data-bbd-kind]`);if(s!==null&&s.dataset.bbdKind){window.__dshBbdKind(s.dataset.bbdKind);return}let c=n.closest(`[data-bbd-page]`);if(c!==null&&c.dataset.bbdPage){window.__dshBbdPage(c.dataset.bbdPage);return}n.closest(`#dsh-bbd-refresh`)!==null&&window.__dshBbdRefresh()};return document.addEventListener(`click`,t,!0),()=>{document.removeEventListener(`click`,t,!0)}},onPoll:()=>e.refresh()}),n=e;return n.openBoard=t.open,n.closeBoard=t.close,n.toggleBoard=t.toggle,n.getSnapshot=()=>({boardOpen:t.isActive()}),()=>{t.dispose(),delete window.__dshBbdRefresh,delete window.__dshBbdStatusTab,delete window.__dshBbdKind,delete window.__dshBbdPage,console.log(`[dashboard-bulletin] board unmounted`)}}const O=()=>{let e=window,t=e.__dshBbdSessions;if(!t?.list)try{t=e.__dshBbdCtx?.sessions,t?.list&&(e.__dshBbdSessions=t)}catch{}let n=null;try{let t=e.__dshBbdWorkspaces;t?.list||(t=e.__dshBbdCtx?.workspaces);let r=t?.list?.getSnapshot?.()?.archivedSessionIds;Array.isArray(r)&&(n=new Set(r.map(String)))}catch{}let r=[];try{let e=t?.list?.getSnapshot?.();if(!e)return r;let i=String(e.current??``),a=Array.isArray(e.items)?e.items:Array.isArray(e.ids)?e.ids.map(t=>e.byId?.[t]).filter(Boolean):[];for(let e of a){let t=String(e?.id??e?.sessionId??``);!t||e.blank||n?.has(t)||e?.origin!==`subagent`&&r.push({sid:t,label:String(e.displayTitle??e.title??t),current:t===i})}}catch{}return r},k=()=>{document.querySelectorAll(`[data-bbd-pick]:not([hidden])`).forEach(e=>{e.hidden=!0})},A=e=>{let t=e.querySelector(`[data-bbd-pick]`);if(t===null)return;if(!t.hidden){t.hidden=!0;return}k();let n=t.querySelector(`[data-bbd-picklist]`),i=O();n!==null&&(n.innerHTML=i.length===0?`<div class="dsh-bbd-pick-empty">暂无可转窗口（会话列表为空或未就绪）——请稍候重试或点「我来解决」</div>`:i.map(e=>`<button type="button" class="dsh-bbd-picksession`+(e.current?` cur`:``)+`" data-bbd-picksession="`+r(e.sid)+`">`+r(e.label)+(e.current?`<i>当前</i>`:``)+`</button>`).join(``)),t.hidden=!1},j=async(e,t,n)=>{let r=``;try{r=String(window.__dshBbdSessions?.list?.getSnapshot?.()?.current??``)}catch{}let i=document.querySelector(`[data-bbd-id="`+CSS.escape(e)+`"] [data-bbd-`+(t===`solve`?`solve`:`delegate`)+`]`),a=i?.textContent??``;i!==null&&(i.disabled=!0,i.textContent=`处理中…`),l(`正在`+(t===`solve`?`认领`:`转交`)+`…`,!0,`dsh-bbd`);try{let i=await fetch(`/dashboard/api/bulletin/action`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({post_id:e,action:t,to_session:n,from_session:r||void 0})}),a=await i.json().catch(()=>null);if(a===null||a.success!==!0){l(`动作失败：`+(a?.error??`HTTP `+i.status),!1,`dsh-bbd`);return}let o=a.data?.delivery?.delivered===!0;l((o?`✓ `:`⚠ `)+String(a.data?.note??`已认领，等待窗口闭环`),o,`dsh-bbd`),window.__dshBbdRefresh?.()}catch(e){l(`请求异常：`+String(e instanceof Error?e.message:e),!1,`dsh-bbd`)}finally{i!==null&&(i.disabled=!1,i.textContent=a)}};function M(e){return u({prefix:`dsh-bbd`,icon:`<svg width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='currentColor' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><rect x='3' y='2.5' width='10' height='11' rx='1.5'/><path d='M6 6.5h4M6 9h4'/></svg>`,label:`公告板`,title:`公告板`,controller:e})}function N(){let e=`dsh-bbd-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
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
		`,(document.head??document.documentElement).appendChild(t)}const P=[`sessions`,`workspaces`];function F(e){try{window.__dshBbdCtx=e,window.__dshBbdSessions=e?.sessions,window.__dshBbdWorkspaces=e?.workspaces}catch{}try{N(),c(`dsh-bbd`),window.__dshBbdClient?.dispose?.();let e=E(),t=D(e),n=M({isActive:()=>e.getSnapshot().boardOpen,toggle:()=>e.toggleBoard()});window.__dshBbdClient={dispose:()=>{try{t()}catch{}try{n()}catch{}try{e.closeBoard()}catch{}}},console.info(`[dashboard-bulletin] phase2 board client ready`)}catch(e){console.error(`[dashboard-bulletin] client half failed to start:`,e)}}exports.apply=F,exports.inject=P,exports.name=`@pi-investment/dashboard-bulletin/client`;
			return module.exports;
		}
	});

