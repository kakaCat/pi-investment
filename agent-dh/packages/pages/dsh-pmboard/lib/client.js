window.__ModuleLoader__.load({
		id: "dsh-pmboard",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");const t=`dsh-panel-activate`;function n(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}function r(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}function i(e){let{panelName:r,activeAttr:i,otherActiveAttrs:a,pollMs:o=3e4,pauseOnHidden:s=!1,dispatchTarget:c=`window`,listenTarget:l=`window`,buildContainer:u,onMount:d,onPoll:f,onOpen:p,onClose:m}=e,h=!1,g,_,v,y=!1,b=()=>{if(g!==void 0||y)return;let e=n();if(e===void 0)return;let t=u();e.appendChild(t),g=t,v=d(t)??void 0},x=new MutationObserver(()=>{b()});x.observe(document.body,{childList:!0,subtree:!0}),b();let S=()=>{if(!(h||y)){h=!0,b();for(let e of a)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(i,``),(c===`document`?document:window).dispatchEvent(new CustomEvent(t,{detail:r})),D(),p?.()}},C=()=>{!h||y||(h=!1,document.documentElement.removeAttribute(i),O(),m?.())},w=()=>{h?C():S()},T=()=>h,E=()=>{h&&f()},D=()=>{O(),_=window.setInterval(E,o)},O=()=>{_!==void 0&&(clearInterval(_),_=void 0)},k=()=>{document.hidden?O():h&&D()};s&&document.addEventListener(`visibilitychange`,k);let A=t=>{if(!h)return;let n=t.target;if(n===null||g!==void 0&&(g===n||g.contains(n)))return;let r=`[data-`+e.prefix+`-entry]`;n.closest(r)===null&&C()};document.addEventListener(`click`,A,!0);let j=e=>{let t=e.detail;t!==void 0&&t!==r&&h&&C()},M=l===`document`?document:window;return M.addEventListener(t,j),{open:S,close:C,toggle:w,isActive:T,dispose:()=>{y||(y=!0,O(),s&&document.removeEventListener(`visibilitychange`,k),document.removeEventListener(`click`,A,!0),M.removeEventListener(t,j),x.disconnect(),v?.(),g?.remove(),g=void 0)}}}function a(e){let{page:t,total:n,totalItems:r,pageAttr:i,prevLabel:a=`‹ 上一页`,nextLabel:o=`下一页 ›`}=e;if(n<=1)return``;let s=Math.min(Math.max(1,t),n),c=e=>`<button type="button" class="tpg-num`+(e===s?` act`:``)+`"`+(e===s?` aria-current="page"`:``)+` `+i+`="`+e+`">`+e+`</button>`,l=[];if(n<=7)for(let e=1;e<=n;e++)l.push(c(e));else{let e=[1,s-1,s,s+1,n].filter(e=>e>=1&&e<=n).sort((e,t)=>e-t),t=[];for(let n of e)t.includes(n)||t.push(n);let r=0;for(let e of t)r!==0&&e-r>1&&l.push(`<span class="tpg-gap">…</span>`),l.push(c(e)),r=e}return`<button type="button" class="tpg-arr" `+i+`="`+(s-1)+`"`+(s<=1?` disabled`:``)+`>`+a+`</button><span class="tpg-nums">`+l.join(``)+`</span><button type="button" class="tpg-arr" `+i+`="`+(s+1)+`"`+(s>=n?` disabled`:``)+`>`+o+`</button><span class="tpg-cnt">第 `+s+`/`+n+` 页 · 共 `+r+` 条</span>`}const o=`dsh-pmboard`,s=`项目看板`,c=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`,`data-dsh-bbd-active`,`data-dsh-gen-active`,`data-dsh-exec-active`],l={draft:`立项`,brainstorming:`头脑风暴`,planning:`写计划`,decomposing:`拆分`,implementing:`执行`,accepting:`验收`,done:`完成`,archived:`归档`,canceled:`取消`},u={todo:`待办`,in_progress:`进行中`,integrating:`联调`,testing:`测试`,in_review:`验收`,done:`完成`,canceled:`取消`},d={doc:`文档`,ui:`UI`,analysis:`分析`,implement:`实施`,test:`测试`,review:`评审`,merge:`合并`},f={feature:`功能`,bug:`缺陷`,doc:`文档`,refactor:`重构`,spike:`调研`,chore:`杂项`},p=[`draft`,`brainstorming`,`planning`,`decomposing`,`implementing`,`accepting`,`done`];function m(e){let t=e.startsWith(`session-`)?e.slice(8):e;return`w-${(t.split(`-`)[0]??t).slice(0,8)}`}const h=e=>{let t=new Date(e),n=e=>String(e).padStart(2,`0`);return`${n(t.getMonth()+1)}-${n(t.getDate())} ${n(t.getHours())}:${n(t.getMinutes())}`};function g(e,t){return t===0?`0/0`:`${e}/${t}`}function _(e){return e.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`).map(t=>{let n=e.tasks.filter(e=>e.requirementId===t.id);return{req:t,tasks:n,doneCount:n.filter(e=>e.status===`done`).length,totalCount:n.length,readyIds:e.ready[t.id]??[],blocked:t.blocked||n.some(e=>e.blocked)}})}function v(e,t=Date.now(),n=`lanes`,i={},a=A){let o=_(e),s=p.map(e=>{let n=o.filter(t=>t.req.status===e),r=n.map(e=>O(e,t,a)).join(``);return`
		      <div class="dsh-pm-lane" data-lane="${e}">
		        <div class="dsh-pm-lane-head">
		          <span class="dsh-pm-lane-dot" data-status="${e}"></span>
		          <span class="dsh-pm-lane-title">${l[e]}</span>
		          <span class="dsh-pm-lane-count">${n.length}</span>
		        </div>
		        <div class="dsh-pm-lane-cards">${r}</div>
		      </div>`}).join(``),c=e.requirements.filter(e=>e.status===`archived`||e.status===`canceled`),u=c.length>0?`<div class="dsh-pm-archived-bar">
		         <span class="dsh-pm-archived-label">归档/取消 ${c.length}</span>
		         ${c.map(e=>`<span class="dsh-pm-archived-chip" data-status="${e.status}">${r(e.id)} ${r(e.title)}</span>`).join(``)}
		       </div>`:``,d=`
		    <div class="dsh-pm-viewswitch" role="tablist" aria-label="看板视图">
		      <button type="button" role="tab" class="dsh-pm-viewbtn${n===`lanes`?` active`:``}"
		        data-action="switch-view" data-view="lanes" title="泳道视图（按状态分列）">泳道</button>
		      <button type="button" role="tab" class="dsh-pm-viewbtn${n===`list`?` active`:``}"
		        data-action="switch-view" data-view="list" title="列表视图（按需求汇总，含进度与跳转）">列表</button>
		    </div>`,f=n===`list`?T(e,t,i,a):`<div class="dsh-pm-lanes">${s}</div>`;return`
		    <div class="dsh-pm-board">
		      <div class="dsh-pm-head">
		        <h1 class="dsh-pm-title">项目看板</h1>
		        <span class="dsh-pm-rev">rev ${e.revision}</span>
		        ${d}
		        <button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button>
		        <button type="button" class="dsh-pm-btn" data-action="open-tasks" title="任务总览与甘特图">任务</button>
		        <button type="button" class="dsh-pm-btn primary" data-action="new-req" title="新建需求">+ 需求</button>
		      </div>
		      ${f}
		      ${n===`list`?``:u}
		    </div>`}const y=[10,20,50];function b(e){return e===`updated`||e===`created`||e===`progress`?`desc`:`asc`}const x=[{key:`stage`,label:`阶段`},{key:`progress`,label:`进度`},{key:`updated`,label:`最近更新`},{key:`created`,label:`创建时间`},{key:`title`,label:`名称`}],S={implementing:0,accepting:1,decomposing:2,planning:3,brainstorming:4,draft:5,done:6};function C(e){return e.totalCount>0?e.doneCount/e.totalCount:0}function w(e){switch(e){case`stage`:return(e,t)=>(S[e.req.status]??99)-(S[t.req.status]??99);case`progress`:return(e,t)=>C(e)-C(t);case`created`:return(e,t)=>e.req.createdAt-t.req.createdAt;case`title`:return(e,t)=>e.req.title.localeCompare(t.req.title,`zh-Hans-CN`);default:return(e,t)=>e.req.updatedAt-t.req.updatedAt}}function T(e,t=Date.now(),n={},r=A){let i=n.sortKey??`stage`,o=n.sortDir??b(i),s=n.pageSize!==void 0&&y.includes(n.pageSize)?n.pageSize:10,c=_(e),l=c.filter(e=>e.req.status!==`done`),u=c.filter(e=>e.req.status===`done`),d=w(i),f=o===`asc`?1:-1,p=(e,t)=>d(e,t)*f||t.req.updatedAt-e.req.updatedAt;l.sort(p),u.sort(p);let m=[...l,...u],h=E(i,o,c.length,l.length,u.length,s);if(m.length===0)return`<div class="dsh-pm-list">${h}<div class="dsh-pm-list-empty">暂无进行中的需求</div></div>`;let g=Math.max(1,Math.ceil(m.length/s)),v=Math.min(Math.max(1,n.page??1),g),x=m.slice((v-1)*s,v*s),S=l.length,C=(v-1)*s,T=[];for(let e=0;e<x.length;e++){let n=C+e;l.length>0&&(n===0||n===C&&n<S)&&T.push(`<div class="dsh-pm-list-grouphead" data-group="active">进行中 ${l.length}${n>0?`（续）`:``}</div>`),u.length>0&&(n===S||n===C&&n>=S)&&T.push(`<div class="dsh-pm-list-grouphead" data-group="done">已完成 ${u.length}${n>S?`（续）`:``}</div>`),T.push(D(x[e],t,r))}let O=m.length>s?`<div class="dsh-pm-pager">${a({page:v,total:g,totalItems:m.length,pageAttr:`data-pmpage`})}</div>`:``;return`<div class="dsh-pm-list">${h}${T.join(``)}${O}</div>`}function E(e,t,n,r,i,a){return`
		    <div class="dsh-pm-list-toolbar">
		      <span class="dsh-pm-list-toolbar-label">排序</span>
		      ${x.map(({key:n,label:r})=>{let i=n===e;return`<button type="button" class="dsh-pm-sortbtn${i?` active`:``}" data-action="list-sort" data-key="${n}" title="按${r}排序（再点一次切换升降序）">${r}${i?t===`asc`?` ↑`:` ↓`:``}</button>`}).join(``)}
		      <span class="dsh-pm-list-toolbar-gap"></span>
		      <span class="dsh-pm-list-toolbar-label">每页</span>
		      <select class="dsh-pm-pagesize" data-action="list-size" title="每页条数">${y.map(e=>`<option value="${e}"${e===a?` selected`:``}>${e}</option>`).join(``)}</select>
		      <span class="dsh-pm-list-count">共 ${n} 条 · 进行中 ${r} · 已完成 ${i}</span>
		    </div>`}function D(e,t,n=A){let{req:i,tasks:a,doneCount:o,totalCount:s,blocked:c}=e,d=s>0?Math.round(o/s*100):0,p=a.filter(e=>e.status!==`todo`&&e.status!==`done`&&e.status!==`canceled`).length,_=i.category?`<span class="dsh-pm-cat" data-cat="${i.category}">${f[i.category]??i.category}</span>`:``,v=c?`<span class="dsh-pm-flag blocked">阻塞</span>`:``,y=i.sourceSessionId,b=y!==void 0&&y.length>0&&n.has(y),x=y!==void 0&&y.length>0?M({sid:y,label:m(y),cls:`dsh-pm-window`,kind:`立项来源窗口`,archived:b}):`<span class="dsh-pm-list-nowindow">人工建卡</span>`,S=a.length===0?`<span class="dsh-pm-list-strip-empty">尚未拆分任务</span>`:(()=>{let e={};for(let t of a)e[t.status]=(e[t.status]??0)+1;return[`in_progress`,`integrating`,`testing`,`in_review`,`todo`,`done`].filter(t=>(e[t]??0)>0).map(t=>`<span class="dsh-pm-list-seg" data-status="${t}">${u[t]??t} ${e[t]}</span>`).join(``)})();return`
		      <div class="dsh-pm-list-card${c?` is-blocked`:``}" data-req="${r(i.id)}">
		        <div class="dsh-pm-list-top">
		          <span class="dsh-pm-card-id">${r(i.id)}</span>
		          <span class="dsh-pm-status-badge" data-status="${i.status}">${l[i.status]}</span>
		          ${_}${v}
		          <span class="dsh-pm-list-when">${h(i.updatedAt)}</span>
		        </div>
		        <div class="dsh-pm-list-title" data-action="open-req" data-req="${r(i.id)}">${r(i.title)}</div>
		        <div class="dsh-pm-list-meta">
		          <span class="dsh-pm-list-window-label">来源</span>${x}
		          <span class="dsh-pm-list-seps">·</span>
		          <span class="dsh-pm-list-strip">${S}</span>
		        </div>
		        <div class="dsh-pm-list-progress">
		          <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${d}%"></div></div>
		          <span class="dsh-pm-card-pct">${g(o,s)}</span>
		          <span class="dsh-pm-list-pct">${d}%${p>0?`（${p} 进行中）`:``}</span>
		        </div>
		        <div class="dsh-pm-list-actions">
		          <button type="button" class="dsh-pm-btn sm" data-action="open-req" data-req="${r(i.id)}">查看详情</button>
		          ${y!==void 0&&y.length>0&&!b?`<button type="button" class="dsh-pm-btn sm primary" data-action="jump-session" data-sid="${r(y)}">跳转会话</button>`:b?`<button type="button" class="dsh-pm-btn sm" disabled title="该需求来自一个已归档的会话：日志保留、侧栏不可见，无法跳转">会话已归档</button>`:``}
		        </div>
		      </div>`}function O(e,t,n=A){let{req:i,tasks:a,doneCount:o,totalCount:s,readyIds:c,blocked:l}=e,u=s>0?Math.round(o/s*100):0,d=i.category?`<span class="dsh-pm-cat" data-cat="${i.category}">${f[i.category]??i.category}</span>`:``,p=Fe(i)+Le(i)+Re(i),m=l?`<span class="dsh-pm-flag blocked">阻塞</span>`:``,h=i.paused?`<span class="dsh-pm-flag paused">暂停</span>`:``,_=c.length>0?`<span class="dsh-pm-flag ready">${c.length} ready</span>`:``,v=Pe(i,t),y=N(i,n)+ee(a,n),b=k(i);return`
		    <div class="dsh-pm-card${l?` is-blocked`:``}" data-req="${r(i.id)}" data-action="open-req">
		      <div class="dsh-pm-card-top">
		        <span class="dsh-pm-card-id">${r(i.id)}</span>
		        ${d}${p}${m}${h}${_}
		      </div>
		      <div class="dsh-pm-card-title">${r(i.title)}</div>
		      <div class="dsh-pm-card-progress">
		        <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${u}%"></div></div>
		        <span class="dsh-pm-card-pct">${g(o,s)}</span>
		      </div>
		      ${v}
		      ${y}
		      ${b}
		    </div>`}function k(e){let t=(t,n,i)=>{let a=i?.primary===!0?`dsh-pm-btn sm primary`:`dsh-pm-btn sm`,o=i?.title===void 0?``:` title="${r(i.title)}"`;return`<button type="button" class="${a}" data-action="move-req" data-to="${t}" data-id="${r(e.id)}"${o}>${n}</button>`},n=``;switch(e.status){case`draft`:n=t(`brainstorming`,`开始头脑风暴`,{primary:!0,title:`进入头脑风暴；窗口接手开工时会自动进入`})+t(`canceled`,`取消`,{title:`取消该需求（仅人可操作）`});break;case`brainstorming`:n=t(`planning`,`写计划`,{primary:!0,title:`方案谈定 → 进入写计划阶段（计划在此阶段提交待人批准）`})+t(`draft`,`退回`,{title:`退回立项`});break;case`planning`:n=t(`decomposing`,`落库拆分`,{primary:!0,title:`计划获批后落库任务卡；未获批会被代码级拒绝`})+t(`brainstorming`,`退回重谈`,{title:`方案要改 → 退回头脑风暴`});break;case`decomposing`:n=t(`implementing`,`开始执行`,{primary:!0,title:`进入执行；任务开工时系统会自动推进`});break;case`implementing`:n=t(`accepting`,`提交验收`,{primary:!0,title:`进入验收；任务全部完成时系统会自动推进`});break;case`accepting`:n=t(`done`,`验收通过`,{primary:!0,title:`完成该需求；窗口 agent 交付后也可自行完成`});break;case`done`:n=t(`archived`,`归档`,{title:`归档归集文档（仅人可操作）`});break;default:n=``}return n.length===0?``:`<div class="dsh-pm-card-actions">${n}</div>`}const A=new Set;function j(e,t){return t.has(e)}function M(e){let{sid:t,label:n,cls:i,kind:a,archived:o}=e;return o?`<span class="${i} is-archived" aria-disabled="true" title="${a}已归档（${r(t)}）：日志保留、侧栏不可见，无法跳转">${n} · 已归档</span>`:`<button type="button" class="${i}" data-action="jump-session" data-sid="${r(t)}" title="${a}（点击跳转到该会话）：${r(t)}">${n}</button>`}function N(e,t=A){let n=e.sourceSessionId;return n?M({sid:n,label:`窗口 ${m(n)}`,cls:`dsh-pm-window`,kind:`立项来源窗口`,archived:j(n,t)}):``}function ee(e,t=A){for(let n=e.length-1;n>=0;n--){let r=e[n].executions;for(let e=r.length-1;e>=0;e--){let n=r[e].sessionId;if(n)return M({sid:n,label:`会话 ${n.slice(0,12)}…`,cls:`dsh-pm-session`,kind:`执行会话`,archived:j(n,t)})}}return``}function te(e){if(!e)return``;let t=e.replace(/\r\n?/g,`
		`).split(`
		`),n=[],i=[],a=!1,o=[],s=!1,c=()=>{if(o.length===0)return;let e=s?`ol`:`ul`;n.push(`<`+e+`>`+o.map(e=>`<li>`+e+`</li>`).join(``)+`</`+e+`>`),o=[]},l=e=>e.replace(/`([^`]+)`/g,`<code>$1</code>`).replace(/\*\*([^*]+)\*\*/g,`<strong>$1</strong>`).replace(/(^|[^*])\*([^*\n]+)\*/g,`$1<em>$2</em>`).replace(/\[([^\]]+)\]\(([^)\s]+)\)/g,`<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>`);for(let e of t){let t=e.trimEnd();if(t.trim().startsWith("```")){c(),a?(n.push(`<pre><code>`+i.join(`
		`)+`</code></pre>`),i=[],a=!1):a=!0;continue}if(a){i.push(r(t));continue}if(t.trim()===``){c();continue}let u=t.match(/^(#{1,6})\s+(.+)$/);if(u){c();let e=u[1].length;n.push(`<h`+e+`>`+l(r(u[2]))+`</h`+e+`>`);continue}let d=t.match(/^\s*[-*+]\s+(.+)$/);if(d){o.length>0&&s&&c(),s=!1,o.push(l(r(d[1])));continue}let f=t.match(/^\s*\d+[.)]\s+(.+)$/);if(f){o.length>0&&!s&&c(),s=!0,o.push(l(r(f[1])));continue}c(),n.push(`<p>`+l(r(t))+`</p>`)}return c(),a&&i.length>0&&n.push(`<pre><code>`+i.join(`
		`)+`</code></pre>`),n.join(`
		`)}const ne={requirement:{icon:`📄`,label:`需求文档`},ui:{icon:`🎨`,label:`UI 文档`},proposal:{icon:`📐`,label:`设计文档`},plan:{icon:`📝`,label:`实施计划`},verification:{icon:`✅`,label:`验收材料`},retro:{icon:`🔁`,label:`复盘`},notes:{icon:`📒`,label:`其他`}};function re(e){let t=[],n=new Set,r=(e,r)=>{let i=(r??``).trim();if(!i||n.has(i))return;n.add(i);let a=ne[e];t.push({icon:a?.icon??`📒`,label:a?.label??e,path:i})};e.docLinks?.requirement&&r(`requirement`,e.docLinks.requirement),e.docLinks?.ui&&r(`ui`,e.docLinks.ui),e.docLinks?.proposal&&r(`proposal`,e.docLinks.proposal),e.plan?.path&&r(`plan`,e.plan.path);for(let t of e.archive?.docs??[])r(t.kind,t.path);return t}function ie(e){let t=re(e);return t.length===0?`<div class="dsh-pm-empty">暂无文档记录。窗口 agent 可用 <code>reqboard_archive_submit</code> 提交文档清单，或通过需求更新接口填充 docLinks（requirement/ui/proposal）。</div>`:`<ul class="dsh-pm-doc-list">`+t.map(e=>`<li data-doc-path="`+r(e.path)+`"><span class="dsh-pm-doc-icon">`+e.icon+`</span><span class="dsh-pm-doc-label">`+r(e.label)+`</span><button type="button" class="dsh-pm-doc-path" data-action="open-doc" data-path="`+r(e.path)+`">`+r(e.path)+`</button></li>`).join(``)+`</ul>`}function ae(e,t,n=Date.now(),i=A){let a=t.filter(t=>t.requirementId===e.id),o=a.filter(e=>e.status===`done`).length,s=a.length,c=s>0?Math.round(o/s*100):0,u=P(a),d=se(a),f=F(e.comments),p=oe(e.status),m=s>0?`<div class="dsh-pm-req-progress">
		        <div class="dsh-pm-progress-bar"><div class="dsh-pm-progress-fill${c>=100?` full`:``}" style="width:${c}%"></div></div>
		        <span class="dsh-pm-progress-text"><b>${o}/${s}</b> 完成 <span class="dsh-pm-progress-pct">${c}%</span></span>
		      </div>`:`<div class="dsh-pm-req-progress"><span class="dsh-pm-progress-text">尚未拆分任务</span></div>`;return`
		    <div class="dsh-pm-detail" data-detail-req="${r(e.id)}">
		      <div class="dsh-pm-detail-head">
		        <button type="button" class="dsh-pm-btn" data-action="back" title="返回看板">← 看板</button>
		        <span class="dsh-pm-card-id">${r(e.id)}</span>
		        <span class="dsh-pm-status" data-status="${e.status}">${l[e.status]}</span>
		        ${e.blocked?`<span class="dsh-pm-flag blocked">阻塞</span>`:``}
		        ${N(e,i)}
		        <span class="dsh-pm-detail-updated">${h(e.updatedAt)}</span>
		      </div>
		      ${p}
		      <details class="dsh-pm-fold" open>
		        <summary>📄 需求描述</summary>
		        <div class="dsh-pm-fold-body">
		          <h2 class="dsh-pm-detail-title">${r(e.title)}</h2>
		          ${e.description?`<div class="dsh-pm-markdown">${te(e.description)}</div>`:`<div class="dsh-pm-empty">暂无描述</div>`}
		        </div>
		      </details>
		      <details class="dsh-pm-fold" open>
		        <summary>📁 文档记录</summary>
		        <div class="dsh-pm-fold-body">${ie(e)}</div>
		      </details>
		      <details class="dsh-pm-fold">
		        <summary>📅 时间线</summary>
		        <div class="dsh-pm-fold-body">${Te(e,n)}</div>
		      </details>
		      ${m}
		      <details class="dsh-pm-fold">
		        <summary>📋 任务看板<span class="dsh-pm-fold-count">${s} 个任务</span></summary>
		        <div class="dsh-pm-fold-body">
		          <div class="dsh-pm-section-head">
		            <button type="button" class="dsh-pm-btn sm" data-action="new-task" data-id="${r(e.id)}" title="人工建任务卡（窗口 agent 走 reqboard_decompose 批量拆分）">+ 任务</button>
		          </div>
		          ${d}
		        </div>
		      </details>
		      <details class="dsh-pm-fold">
		        <summary>🔀 任务 DAG</summary>
		        <div class="dsh-pm-fold-body">${u}</div>
		      </details>
		      <details class="dsh-pm-fold">
		        <summary>📝 实施计划（plan mode）</summary>
		        <div class="dsh-pm-fold-body">${Ie(e)}</div>
		      </details>
		      <details class="dsh-pm-fold">
		        <summary>✅ 验收（人工审核）</summary>
		        <div class="dsh-pm-fold-body">${ze(e)}</div>
		      </details>
		      <details class="dsh-pm-fold">
		        <summary>📦 归档（文档合并）</summary>
		        <div class="dsh-pm-fold-body">${Be(e)}</div>
		      </details>
		      <details class="dsh-pm-fold">
		        <summary>💬 评论<span class="dsh-pm-fold-count">${e.comments.length} 条</span></summary>
		        <div class="dsh-pm-fold-body">
		          ${f}
		          <div class="dsh-pm-comment-form">
		            <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
		            <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="req" data-id="${r(e.id)}">发送</button>
		          </div>
		        </div>
		      </details>
		    </div>`}function oe(e){return{draft:`<div class="dsh-pm-gate">已立项：窗口接手开工后自动进入评审 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="brainstorming">提交评审</button></div>`,brainstorming:`<div class="dsh-pm-gate">评审中：窗口 agent 会自行推进到拆分，人可在此加速 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">确认方案</button> <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="draft">退回立项</button></div>`,decomposing:`<div class="dsh-pm-gate">拆分中：任务落库/开工后系统自动推进到实施 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="implementing">确认拆分</button></div>`,planning:`<div class="dsh-pm-gate">写计划：计划提交后请点上面计划卡的「批准计划」——批准前拆分会被告代码级拒绝 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">落库拆分</button> <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="brainstorming">退回重谈</button></div>`,implementing:`<div class="dsh-pm-gate">执行中：任务全部完成时自动进入验收 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="accepting">提交验收</button></div>`,accepting:`<div class="dsh-pm-gate">验收中：窗口 agent 交付后可自行完成，人可在此确认 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="done">验收通过</button></div>`,done:`<div class="dsh-pm-gate">已完成：归档归集文档（仅人可操作）<button type="button" class="dsh-pm-btn" data-action="move-req" data-to="archived">归档</button></div>`}[e]??``}function P(e){if(e.length===0)return`<div class="dsh-pm-empty">暂无任务</div>`;let t=new Map,n=new Map(e.map(e=>[e.id,e])),i=(e,r)=>{if(t.has(e.id))return t.get(e.id);if(r.has(e.id))return 0;r.add(e.id);let a=e.dependsOn.filter(e=>n.has(e)),o=a.length===0?0:1+Math.max(...a.map(e=>i(n.get(e),r)));return t.set(e.id,o),o};e.forEach(e=>i(e,new Set));let a=Math.max(...t.values()),o=Array.from({length:a+1},()=>[]);return e.forEach(e=>o[t.get(e.id)].push(e)),`<div class="dsh-pm-dag">`+o.map((e,t)=>`
		    <div class="dsh-pm-dag-layer">
		      <span class="dsh-pm-dag-layer-label">L${t}</span>
		      ${e.map(e=>`
		        <span class="dsh-pm-dag-node" data-status="${e.status}" data-action="open-task" data-task="${r(e.id)}" title="${r(e.title)}">
		          ${r(e.id)} ${r(e.title.slice(0,20))}${e.title.length>20?`…`:``}
		        </span>`).join(``)}
		    </div>`).join(``)+`</div>`}function se(e){return e.length===0?`<div class="dsh-pm-empty">暂无任务</div>`:`<div class="dsh-pm-taskcols">`+[`todo`,`in_progress`,`integrating`,`testing`,`in_review`,`done`].map(t=>{let n=e.filter(e=>e.status===t);return`
		      <div class="dsh-pm-taskcol" data-col="${t}">
		        <div class="dsh-pm-taskcol-head">${u[t]} ${n.length}</div>
		        ${n.map(e=>`
		          <div class="dsh-pm-task" data-task="${r(e.id)}" data-action="open-task">
		            <div class="dsh-pm-task-title">${r(e.title)}</div>
		            <div class="dsh-pm-task-meta">
		              <span class="dsh-pm-phase">${d[e.phase]??e.phase}</span>
		              ${e.blocked?`<span class="dsh-pm-flag blocked">阻塞</span>`:``}
		            </div>
		          </div>`).join(``)}
		      </div>`}).join(``)+`</div>`}function F(e){return e.length===0?`<div class="dsh-pm-empty">暂无评论</div>`:`<div class="dsh-pm-comments">`+e.map(e=>`
		    <div class="dsh-pm-comment">
		      <span class="dsh-pm-comment-meta">${r(e.createdBy?.kind??`human`)} · ${h(e.createdAt)}</span>
		      <div class="dsh-pm-comment-body">${r(e.body)}</div>
		    </div>`).join(``)+`</div>`}function ce(e){let t=e.title.toLowerCase();if(t.includes(`拆分`)||t.includes(`decompose`))return`decompose`;if(e.status===`integrating`||t.includes(`集成`)||t.includes(`联调`))return`merge`;switch(e.phase){case`doc`:return`doc`;case`ui`:return`ui`;case`analysis`:return`analysis`;case`implement`:return`implement`;case`test`:return`test`;case`review`:return`review`;case`merge`:return`merge`;default:return`generic`}}const le={decompose:`🔀`,implement:`⚙️`,test:`🧪`,review:`👀`,merge:`🔀`,doc:`📝`,ui:`🎨`,analysis:`🔍`,generic:`📋`},ue={decompose:`拆分任务`,implement:`实施任务`,test:`测试任务`,review:`评审任务`,merge:`合并任务`,doc:`文档任务`,ui:`UI设计`,analysis:`分析任务`,generic:`任务`};function de(e,t,n=Date.now(),i=[],a=A){let o=ce(e),s=le[o],c=ue[o],l=fe(e,o,t,i),d=pe(e,n,a);return`
		    <div class="dsh-pm-taskdetail" data-detail-task="${r(e.id)}" data-node-type="${o}">
		      <div class="dsh-pm-detail-head">
		        <button type="button" class="dsh-pm-btn" data-action="back-req" data-req="${r(e.requirementId)}" title="返回需求">← ${r(e.requirementId)}</button>
		        <span class="dsh-pm-card-id">${r(e.id)}</span>
		        <span class="dsh-pm-status" data-status="${e.status}">${u[e.status]}</span>
		        <span class="dsh-pm-node-badge" title="${c}">${s} ${c}</span>
		      </div>
		      <h2 class="dsh-pm-detail-title">${r(e.title)}</h2>
		      ${e.description?`<div class="dsh-pm-detail-desc">${r(e.description)}</div>`:``}
		      ${l}
		      ${d}
		    </div>`}function fe(e,t,n,r){switch(t){case`decompose`:return me(e,n,r);case`implement`:return he(e);case`test`:return ge(e);case`review`:return _e(e);case`merge`:return ve(e);case`doc`:return ye(e);case`ui`:return be(e);case`analysis`:return xe(e);default:return``}}function pe(e,t,n=A){let i=e.executions.map(e=>`
		    <div class="dsh-pm-exec" data-outcome="${e.outcome}">
		      <span class="dsh-pm-exec-outcome">${e.outcome}</span>
		      <span>${h(e.startedAt)}</span>
		      ${e.sessionId?M({sid:e.sessionId,label:`会话 ${e.sessionId.slice(0,12)}…`,cls:`dsh-pm-session`,kind:`执行会话`,archived:n.has(e.sessionId)}):``}
		      ${e.error?`<div class="dsh-pm-exec-error">${r(e.error)}</div>`:``}
		      ${e.evidence&&e.evidence.length>0?`<div class="dsh-pm-exec-evidence">${e.evidence.map(e=>`<code>${r(e)}</code>`).join(` `)}</div>`:``}
		    </div>`).join(``);return`
		    <details class="dsh-pm-common-details">
		      <summary class="dsh-pm-common-summary">通用信息（属性、时间线、执行记录、评论）</summary>
		      <div class="dsh-pm-detail-section">
		        <h3>属性</h3>
		        <div class="dsh-pm-kv">
		          <span>阶段</span><span>${d[e.phase]??e.phase}</span>
		          <span>端侧</span><span>${e.side}</span>
		          <span>依赖</span><span>${e.dependsOn.length>0?e.dependsOn.map(r).join(`, `):`无`}</span>
		          <span>验收标准</span><span>${r(e.acceptance)}</span>
		        </div>
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>时间线</h3>
		        ${Ee(e,t)}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>执行记录（${e.executions.length}）</h3>
		        ${i||`<div class="dsh-pm-empty">暂无执行</div>`}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>评论（${e.comments.length}）</h3>
		        ${F(e.comments)}
		        <div class="dsh-pm-comment-form">
		          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
		          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="task" data-id="${r(e.id)}">发送</button>
		        </div>
		      </div>
		    </details>`}function me(e,t,n){if(!t)return`<div class="dsh-pm-detail-section"><div class="dsh-pm-empty">需求数据不可用</div></div>`;let i=n.filter(e=>e.requirementId===t.id),a=i.length,o=i.filter(e=>e.status===`done`).length,s={};return i.forEach(e=>{let t=e.side===`frontend`?`UI 轨道`:e.side===`backend`?`后端轨道`:e.side===`doc`?`文档轨道`:`全栈轨道`;s[t]||(s[t]=[]),s[t].push(e)}),`
		    <div class="dsh-pm-detail-section dsh-pm-specialized">
		      <h3>📊 拆分结果</h3>
		      <div class="dsh-pm-stats">
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">总计任务</span>
		          <span class="dsh-pm-stat-value">${a} 个</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">并行轨道</span>
		          <span class="dsh-pm-stat-value">${Object.keys(s).length} 个</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">预计工期</span>
		          <span class="dsh-pm-stat-value">${a>0?(a*.5).toFixed(1):`0`} 天</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">完成进度</span>
		          <span class="dsh-pm-stat-value">${o}/${a}</span>
		        </div>
		      </div>
		    </div>
		    <div class="dsh-pm-detail-section">
		      <h3>📋 拆分清单</h3>
		      ${Object.entries(s).map(([e,t])=>`
		    <div class="dsh-pm-track">
		      <div class="dsh-pm-track-head">${e} - ${t.length} 任务</div>
		      <ul class="dsh-pm-track-list">
		        ${t.map(e=>`<li><button type="button" class="dsh-pm-task-link" data-action="open-task" data-task="${r(e.id)}">${r(e.id)}</button> ${r(e.title)}</li>`).join(``)}
		      </ul>
		    </div>`).join(``)||`<div class="dsh-pm-empty">暂无任务</div>`}
		    </div>
		    <div class="dsh-pm-detail-section">
		      <h3>🌳 依赖关系 DAG</h3>
		      ${P(i)}
		    </div>`}function he(e){let t=[],n=e.executions[e.executions.length-1];n?.evidence&&n.evidence.forEach(e=>{let n=e.match(/^(.+?)\s*\(?\+(\d+)(?:,\s*-(\d+))?\)?$/);n&&t.push({path:n[1].trim(),added:parseInt(n[2],10),deleted:parseInt(n[3]||`0`,10)})});let i=t.reduce((e,t)=>e+t.added,0),a=t.reduce((e,t)=>e+t.deleted,0),o=t.length>0?t.map(e=>`
		    <div class="dsh-pm-file-change">
		      <code class="dsh-pm-file-path">${r(e.path)}</code>
		      <span class="dsh-pm-file-stats">
		        <span class="dsh-pm-stat-add">+${e.added}</span>
		        ${e.deleted>0?`<span class="dsh-pm-stat-del">-${e.deleted}</span>`:``}
		      </span>
		    </div>`).join(``):`<div class="dsh-pm-empty">暂无文件变更记录</div>`,s=`未知`;if(n?.evidence){let e=n.evidence.find(e=>e.includes(`coverage`)||e.includes(`覆盖率`));if(e){let t=e.match(/(\d+)%/);t&&(s=t[1]+`%`)}}let c=e.executions.map(e=>`<div class="dsh-pm-exec-brief">${e.outcome===`succeeded`?`✅`:e.outcome===`failed`?`❌`:e.outcome===`running`?`⏳`:`⚠️`} ${h(e.startedAt)} - ${e.outcome}</div>`).join(``);return`
		    <div class="dsh-pm-detail-section dsh-pm-specialized">
		      <h3>📁 修改文件</h3>
		      <div class="dsh-pm-file-summary">
		        <span>${t.length} 个文件</span>
		        <span class="dsh-pm-stat-add">+${i} 行</span>
		        ${a>0?`<span class="dsh-pm-stat-del">-${a} 行</span>`:``}
		      </div>
		      ${o}
		    </div>
		    <div class="dsh-pm-detail-section">
		      <h3>🔍 执行记录（${e.executions.length} 次）</h3>
		      ${c||`<div class="dsh-pm-empty">暂无执行</div>`}
		    </div>
		    <div class="dsh-pm-detail-section">
		      <h3>📊 质量指标</h3>
		      <div class="dsh-pm-kv">
		        <span>测试覆盖率</span><span>${s}</span>
		        <span>代码复杂度</span><span>未知</span>
		        <span>类型安全</span><span>通过</span>
		      </div>
		    </div>`}function ge(e){let t=0,n=0,i=0,a=0,o=[],s=e.executions[e.executions.length-1];s?.evidence&&s.evidence.forEach(e=>{let r=e.match(/(\d+)\s*passed.*?(\d+)\s*failed.*?(\d+)\s*skipped/i);r&&(n=parseInt(r[1],10),i=parseInt(r[2],10),a=parseInt(r[3],10),t=n+i+a)}),s?.error&&s.error.split(`
		`).forEach(e=>{let t=e.match(/(.+?):(\d+)\s*Expected:\s*(.+?)\s*Actual:\s*(.+)/);t&&o.push({name:`测试用例`,file:t[1]+`:`+t[2],expected:t[3],actual:t[4]})});let c=t>0?(n/t*100).toFixed(1):`0`,l=o.length>0?o.map(e=>`
		    <div class="dsh-pm-test-fail">
		      <div class="dsh-pm-test-fail-name">${r(e.name)}</div>
		      <div class="dsh-pm-test-fail-detail">
		        <span>预期：<code>${r(e.expected)}</code></span>
		        <span>实际：<code>${r(e.actual)}</code></span>
		        <span>文件：<code>${r(e.file)}</code></span>
		      </div>
		    </div>`).join(``):`<div class="dsh-pm-empty">所有测试通过</div>`,u=0,d=0,f=0,p=0;if(s?.evidence){let e=s.evidence.find(e=>e.includes(`coverage`));if(e){let t=e.match(/statements?:\s*(\d+)%/i),n=e.match(/branches?:\s*(\d+)%/i),r=e.match(/functions?:\s*(\d+)%/i),i=e.match(/lines?:\s*(\d+)%/i);t&&(u=parseInt(t[1],10)),n&&(d=parseInt(n[1],10)),r&&(f=parseInt(r[1],10)),i&&(p=parseInt(i[1],10))}}return`
		    <div class="dsh-pm-detail-section dsh-pm-specialized">
		      <h3>📊 测试概况</h3>
		      <div class="dsh-pm-stats">
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">总计</span>
		          <span class="dsh-pm-stat-value">${t} 个</span>
		        </div>
		        <div class="dsh-pm-stat dsh-pm-stat-success">
		          <span class="dsh-pm-stat-label">通过</span>
		          <span class="dsh-pm-stat-value">${n} 个 (${c}%)</span>
		        </div>
		        <div class="dsh-pm-stat dsh-pm-stat-error">
		          <span class="dsh-pm-stat-label">失败</span>
		          <span class="dsh-pm-stat-value">${i} 个</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">跳过</span>
		          <span class="dsh-pm-stat-value">${a} 个</span>
		        </div>
		      </div>
		    </div>
		    ${i>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>❌ 失败的测试</h3>
		      ${l}
		    </div>`:``}
		    ${u>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>📈 覆盖率报告</h3>
		      <div class="dsh-pm-coverage">
		        <div class="dsh-pm-coverage-bar">
		          <span class="dsh-pm-coverage-label">语句覆盖率</span>
		          <span class="dsh-pm-coverage-value">${u}%</span>
		          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${u}%"></div></div>
		        </div>
		        <div class="dsh-pm-coverage-bar">
		          <span class="dsh-pm-coverage-label">分支覆盖率</span>
		          <span class="dsh-pm-coverage-value">${d}%</span>
		          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${d}%"></div></div>
		        </div>
		        <div class="dsh-pm-coverage-bar">
		          <span class="dsh-pm-coverage-label">函数覆盖率</span>
		          <span class="dsh-pm-coverage-value">${f}%</span>
		          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${f}%"></div></div>
		        </div>
		        <div class="dsh-pm-coverage-bar">
		          <span class="dsh-pm-coverage-label">行覆盖率</span>
		          <span class="dsh-pm-coverage-value">${p}%</span>
		          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${p}%"></div></div>
		        </div>
		      </div>
		    </div>`:``}`}function _e(e){let t=e.comments.filter(e=>e.createdBy?.kind===`agent`||e.createdBy?.kind===`human`),n=e.executions[e.executions.length-1],i=!1,a=`待评审`,o=[],s=[];n?.evidence&&n.evidence.forEach(e=>{(e.toLowerCase().includes(`approved`)||e.toLowerCase().includes(`通过`))&&(i=!0,a=`已批准`),(e.toLowerCase().includes(`rejected`)||e.toLowerCase().includes(`退回`))&&(a=`已退回`),(e.startsWith(`✓`)||e.startsWith(`✅`))&&s.push(e.replace(/^[✓✅]\s*/,``));let t=e.match(/^(.+?):(\d+)\s*\[(\w+)\]\s*(.+)/);t&&o.push({file:t[1],line:t[2],severity:t[3],message:t[4],resolved:!1})});let c={low:`低`,medium:`中`,high:`高`},l={low:`#28a745`,medium:`#f0a020`,high:`#dc3545`},u=s.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>✅ 通过项</h3>
		      <ul class="dsh-pm-review-list">
		        ${s.map(e=>`<li class="dsh-pm-review-pass">${r(e)}</li>`).join(``)}
		      </ul>
		    </div>`:``,d=o.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>⚠️ 改进建议（${o.length} 项）</h3>
		      <div class="dsh-pm-suggestions">
		        ${o.map((e,t)=>`
		          <div class="dsh-pm-suggestion" data-severity="${e.severity}">
		            <div class="dsh-pm-suggestion-head">
		              <span class="dsh-pm-suggestion-num">${t+1}</span>
		              <code class="dsh-pm-file-path">${r(e.file)}:${e.line}</code>
		              <span class="dsh-pm-severity-badge" data-severity="${e.severity}" style="background: ${l[e.severity]}">
		                严重性：${c[e.severity]}
		              </span>
		            </div>
		            <div class="dsh-pm-suggestion-body">${r(e.message)}</div>
		          </div>`).join(``)}
		      </div>
		    </div>`:``,f=t.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>💬 评审讨论（${t.length} 条）</h3>
		      ${F(t)}
		    </div>`:``;return`
		    <div class="dsh-pm-detail-section dsh-pm-specialized">
		      <h3>📊 评审结果</h3>
		      <div class="dsh-pm-review-status" data-status="${i?`approved`:`pending`}">
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">状态</span>
		          <span class="dsh-pm-stat-value">${a}</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">通过项</span>
		          <span class="dsh-pm-stat-value">${s.length} 项</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">改进建议</span>
		          <span class="dsh-pm-stat-value">${o.length} 项</span>
		        </div>
		      </div>
		    </div>
		    ${u}
		    ${d}
		    ${f}`}function ve(e){let t=e.executions[e.executions.length-1],n=`未知`,i=`main`,a=0,o=0,s=0,c=0,l=`进行中`,u=[],d=[];t?.evidence&&t.evidence.forEach(e=>{let t=e.match(/(.+?)\s*(?:→|->|-)\s*(.+)/);t&&(n=t[1].trim(),i=t[2].trim());let r=e.match(/(\d+)\s*commits?/i);r&&(a=parseInt(r[1],10));let f=e.match(/(\d+)\s*files?\s*changed/i);f&&(o=parseInt(f[1],10));let p=e.match(/\+(\d+)\s*-(\d+)/);p&&(s=parseInt(p[1],10),c=parseInt(p[2],10)),(e.toLowerCase().includes(`merged`)||e.toLowerCase().includes(`合并成功`))&&(l=`✅ 合并成功`),e.toLowerCase().includes(`conflict`)&&(l=`⚠️ 存在冲突`);let m=e.match(/conflict:\s*(.+?)\s*-\s*(.+)/i);m&&u.push({file:m[1].trim(),description:m[2].trim(),resolution:`待解决`});let h=e.match(/^([✓✅❌⏳])\s*(.+?):\s*(.+)/);if(h){let e=h[1]===`✓`||h[1]===`✅`?`pass`:h[1]===`❌`?`fail`:`pending`;d.push({name:h[2].trim(),status:e,details:h[3].trim()})}});let f=u.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>⚠️ 冲突解决（${u.length} 个）</h3>
		      <div class="dsh-pm-conflicts">
		        ${u.map((e,t)=>`
		          <div class="dsh-pm-conflict">
		            <div class="dsh-pm-conflict-num">${t+1}</div>
		            <div class="dsh-pm-conflict-body">
		              <code class="dsh-pm-file-path">${r(e.file)}</code>
		              <div class="dsh-pm-conflict-desc">冲突：${r(e.description)}</div>
		              <div class="dsh-pm-conflict-resolution">解决：${r(e.resolution)}</div>
		            </div>
		          </div>`).join(``)}
		      </div>
		    </div>`:``,p=d.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>✅ CI/CD 检查</h3>
		      <div class="dsh-pm-ci-checks">
		        ${d.map(e=>{let t=e.status===`pass`?`✅`:e.status===`fail`?`❌`:`⏳`;return`
		            <div class="dsh-pm-ci-check" data-status="${e.status}">
		              <span class="dsh-pm-ci-icon">${t}</span>
		              <span class="dsh-pm-ci-name">${r(e.name)}</span>
		              <span class="dsh-pm-ci-details">${r(e.details||``)}</span>
		            </div>`}).join(``)}
		      </div>
		    </div>`:``;return`
		    <div class="dsh-pm-detail-section dsh-pm-specialized">
		      <h3>📊 合并状态</h3>
		      <div class="dsh-pm-merge-header">
		        <div class="dsh-pm-merge-branch">
		          <code>${r(n)}</code>
		          <span class="dsh-pm-merge-arrow">→</span>
		          <code>${r(i)}</code>
		        </div>
		        <div class="dsh-pm-merge-status">${l}</div>
		      </div>
		      <div class="dsh-pm-stats">
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">提交数</span>
		          <span class="dsh-pm-stat-value">${a} commits</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">变更文件</span>
		          <span class="dsh-pm-stat-value">${o} 个</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">代码变更</span>
		          <span class="dsh-pm-stat-value">
		            <span class="dsh-pm-stat-add">+${s}</span>
		            <span class="dsh-pm-stat-del">-${c}</span>
		          </span>
		        </div>
		      </div>
		    </div>
		    ${f}
		    ${p}`}function ye(e){let t=e.executions[e.executions.length-1],n=[],i=[],a={defined:0,total:0};if(t?.evidence&&t.evidence.forEach(e=>{e.match(/\.(md|txt|pdf|html)$/i)&&n.push(e),e.match(/^(GET|POST|PUT|DELETE|PATCH)\s+\//)&&i.push(e);let t=e.match(/(\d+)\/(\d+)\s*.*?completed/i);t&&(a.defined=parseInt(t[1],10),a.total=parseInt(t[2],10))}),i.length===0&&e.description){let t=e.description.match(/(GET|POST|PUT|DELETE|PATCH)\s+\/[^\s\n]+/g);t&&i.push(...t)}let o=a.total>0?Math.round(a.defined/a.total*100):0,s=n.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>📄 文档内容</h3>
		      <ul class="dsh-pm-doc-list">
		        ${n.map(e=>`<li><code>${r(e)}</code></li>`).join(``)}
		      </ul>
		    </div>`:``,c=i.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>🔗 关联接口（${i.length} 个）</h3>
		      <ul class="dsh-pm-api-list">
		        ${i.map(e=>{let[t,n]=e.split(/\s+/);return`<li><span class="dsh-pm-api-method" data-method="${t}">${t}</span> <code>${r(n)}</code></li>`}).join(``)}
		      </ul>
		    </div>`:``,l=a.total>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>📊 完成度</h3>
		      <div class="dsh-pm-completeness">
		        <div class="dsh-pm-completeness-bar">
		          <span class="dsh-pm-completeness-label">整体进度</span>
		          <span class="dsh-pm-completeness-value">${o}%</span>
		          <div class="dsh-pm-completeness-track">
		            <div class="dsh-pm-completeness-fill" style="width: ${o}%"></div>
		          </div>
		        </div>
		        <div class="dsh-pm-completeness-detail">
		          已完成 ${a.defined} / ${a.total} 部分
		        </div>
		      </div>
		    </div>`:``;return`
		    <div class="dsh-pm-detail-section dsh-pm-specialized">
		      <h3>📝 文档概览</h3>
		      <div class="dsh-pm-stats">
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">文档文件</span>
		          <span class="dsh-pm-stat-value">${n.length} 个</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">关联接口</span>
		          <span class="dsh-pm-stat-value">${i.length} 个</span>
		        </div>
		        ${a.total>0?`
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">完成度</span>
		          <span class="dsh-pm-stat-value">${o}%</span>
		        </div>`:``}
		      </div>
		    </div>
		    ${s}
		    ${c}
		    ${l}`}function be(e){let t=e.executions[e.executions.length-1],n=[],i=[],a={};if(t?.evidence&&t.evidence.forEach(e=>{if(e.match(/\.(fig|sketch|xd|png|jpg|svg)$/i)&&n.push(e),e.includes(`component`)||e.includes(`组件`)){let t=e.replace(/components?[:\s]*/i,``).split(/[,，]/).map(e=>e.trim());i.push(...t)}let t=e.match(/^(color|font|spacing|radius)[:\s]+(.+)/i);t&&(a[t[1].toLowerCase()]=t[2].trim())}),i.length===0&&e.description){let t=e.description.match(/组件[：:]\s*([^\n]+)/);if(t){let e=t[1].split(/[,，、]/).map(e=>e.trim());i.push(...e)}}let o=n.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>🖼️ 设计稿</h3>
		      <ul class="dsh-pm-design-list">
		        ${n.map(e=>`<li><code>${r(e)}</code></li>`).join(``)}
		      </ul>
		    </div>`:``,s=Object.keys(a).length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>🎯 设计规范</h3>
		      <div class="dsh-pm-kv">
		        ${Object.entries(a).map(([e,t])=>`
		          <span>${e===`color`?`主色调`:e===`font`?`字体`:e===`spacing`?`间距`:`圆角`}</span>
		          <span><code>${r(t)}</code></span>
		        `).join(``)}
		      </div>
		    </div>`:``,c=i.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>📱 组件清单</h3>
		      <ul class="dsh-pm-component-list">
		        ${i.map(e=>`<li>${r(e)}</li>`).join(``)}
		      </ul>
		    </div>`:``;return`
		    <div class="dsh-pm-detail-section dsh-pm-specialized">
		      <h3>🎨 UI 设计</h3>
		      <div class="dsh-pm-stats">
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">设计文件</span>
		          <span class="dsh-pm-stat-value">${n.length} 个</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">组件数量</span>
		          <span class="dsh-pm-stat-value">${i.length} 个</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">设计规范</span>
		          <span class="dsh-pm-stat-value">${Object.keys(a).length} 项</span>
		        </div>
		      </div>
		    </div>
		    ${o}
		    ${s}
		    ${c}`}function xe(e){let t=e.executions[e.executions.length-1],n=``,i=[],a=[],o=[];if(t?.evidence&&t.evidence.forEach(e=>{e.match(/^recommended?[:\s]+/i)&&(n=e.replace(/^recommended?[:\s]+/i,``).trim());let t=e.match(/^(.+?)[:：]\s*(?:(\d+)\/5|([⭐★]+))/);if(t){let e=t[1].trim(),n=t[2]?parseInt(t[2],10):t[3]?.length||0;i.push({name:e,score:n})}e.match(/^risk[:\s]+/i)&&a.push(e.replace(/^risk[:\s]+/i,``).trim()),e.match(/^https?:\/\//)&&o.push(e)}),!n&&e.description){let t=e.description.match(/推荐[方案]?[：:]\s*([^\n]+)/);t&&(n=t[1].trim())}let s=i.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>📊 方案对比</h3>
		      <div class="dsh-pm-options">
		        ${i.map(e=>{let t=`⭐`.repeat(e.score)+`☆`.repeat(5-e.score);return`
		            <div class="dsh-pm-option">
		              <span class="dsh-pm-option-name">${r(e.name)}</span>
		              <span class="dsh-pm-option-score">${t}</span>
		            </div>`}).join(``)}
		      </div>
		    </div>`:``,c=n?`
		    <div class="dsh-pm-detail-section">
		      <h3>✅ 推荐方案</h3>
		      <div class="dsh-pm-recommendation">
		        <div class="dsh-pm-recommendation-title">${r(n)}</div>
		      </div>
		    </div>`:``,l=a.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>⚠️ 风险点（${a.length} 项）</h3>
		      <ul class="dsh-pm-risk-list">
		        ${a.map(e=>`<li>${r(e)}</li>`).join(``)}
		      </ul>
		    </div>`:``,u=o.length>0?`
		    <div class="dsh-pm-detail-section">
		      <h3>📚 参考资料</h3>
		      <ul class="dsh-pm-reference-list">
		        ${o.map(e=>`<li><a href="${r(e)}" target="_blank" rel="noopener">${r(e)}</a></li>`).join(``)}
		      </ul>
		    </div>`:``;return`
		    <div class="dsh-pm-detail-section dsh-pm-specialized">
		      <h3>🔍 分析结果</h3>
		      <div class="dsh-pm-stats">
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">对比方案</span>
		          <span class="dsh-pm-stat-value">${i.length} 个</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">风险点</span>
		          <span class="dsh-pm-stat-value">${a.length} 项</span>
		        </div>
		        <div class="dsh-pm-stat">
		          <span class="dsh-pm-stat-label">参考资料</span>
		          <span class="dsh-pm-stat-value">${o.length} 个</span>
		        </div>
		      </div>
		    </div>
		    ${c}
		    ${s}
		    ${l}
		    ${u}`}function Se(e,t){let n=e.filter(e=>e.status===`pending`),i=t.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`),a=n.map(e=>{let t=e.suggestedAction===`create_req`&&!e.suggestedTargetId,n=e.suggestedTargetId?`${e.suggestedAction===`bind_req`?`绑定需求`:e.suggestedAction===`bind_task`?`绑定任务`:`新建需求`} ${r(e.suggestedTargetId)}`:e.suggestedAction===`create_req`?`新建需求${e.suggestedCategory?` · ${f[e.suggestedCategory]??e.suggestedCategory}`:``}`:``,i=t?`
		        <div class="dsh-pm-triage-edit">
		          <input type="text" class="dsh-pm-input" data-role="triage-title" value="${r(e.suggestedTitle??e.firstMessageText.slice(0,120))}" placeholder="需求名称（可编辑）" />
		          <select class="dsh-pm-input" data-role="triage-category">
		            ${Object.entries(f).map(([t,n])=>`<option value="${t}" ${t===(e.suggestedCategory??`feature`)?`selected`:``}>${n}</option>`).join(``)}
		          </select>
		        </div>`:``;return`
		      <div class="dsh-pm-triage" data-triage="${r(e.id)}">
		        <div class="dsh-pm-triage-head">
		          <span class="dsh-pm-session-id">${r(e.sessionId.slice(0,16))}…</span>
		          <span class="dsh-pm-triage-score">分 ${e.score}</span>
		          <span class="dsh-pm-triage-suggest">${n}</span>
		        </div>
		        <div class="dsh-pm-triage-text">${r(e.firstMessageText.slice(0,200))}${e.firstMessageText.length>200?`…`:``}</div>
		        ${i}
		        <div class="dsh-pm-triage-actions">
		          <button type="button" class="dsh-pm-btn primary" data-action="triage-confirm" data-triage="${r(e.id)}">确认</button>
		          ${t?``:`<button type="button" class="dsh-pm-btn" data-action="triage-rebind" data-triage="${r(e.id)}">改绑</button>`}
		          <button type="button" class="dsh-pm-btn" data-action="triage-reject" data-triage="${r(e.id)}">拒绝</button>
		        </div>
		      </div>`}).join(``);return`
		    <div class="dsh-pm-triage-panel">
		      <div class="dsh-pm-detail-head">
		        <span class="dsh-pm-title-sm">待归类（${n.length}）</span>
		        <span class="dsh-pm-hint">新会话自动捕获，确认后进入流水线</span>
		      </div>
		      ${a||`<div class="dsh-pm-empty">暂无待归类会话</div>`}
		      <div class="dsh-pm-rebind-host" style="display:none">
		        <select class="dsh-pm-input" data-role="rebind-select">
		          ${i.map(e=>`<option value="${r(e.id)}">${r(e.id)} ${r(e.title.slice(0,30))}</option>`).join(``)}
		        </select>
		        <button type="button" class="dsh-pm-btn primary" data-action="triage-rebind-confirm">确认改绑</button>
		      </div>
		    </div>`}function Ce(){return`<div class="dsh-pm-board"><div class="dsh-pm-empty">暂无数据 — 点击「+ 需求」创建第一个需求</div></div>`}function we(e){return`<div class="dsh-pm-board"><div class="dsh-pm-error">加载失败：${r(e)}</div></div>`}function I(e){let t=Math.floor(Math.max(0,e)/6e4);if(t<60)return t+` 分`;let n=Math.floor(t/60);return n<24?n+` 小时 `+t%60+` 分`:Math.floor(n/24)+` 天 `+n%24+` 小时`}function L(e){return e===`done`||e===`archived`||e===`canceled`}function R(e,t){let n=e.statusHistory;if(n!==void 0&&n.length>0)return n;let r=[{status:t,at:e.createdAt,by:{kind:`human`},reason:`创建`,inferred:!0}];return e.status!==void 0&&e.status!==t&&e.updatedAt!==void 0&&r.push({status:e.status,at:Math.max(e.updatedAt,e.createdAt),by:e.updatedBy??{kind:`human`},reason:`按 updatedAt 回填（当时无事件留痕）`,inferred:!0}),r}function z(e,t,n,i,a){let o=R(e,i),s=new Map;o.forEach((e,t)=>{s.has(e.status)||s.set(e.status,t)});let c=o.map((e,t)=>({e,i:t})).filter(e=>!t.includes(e.e.status)).map(e=>e.e.status),l=(e,t)=>{if(t===void 0)return`<div class="dsh-pm-tl-row pending" data-status="`+e+`"><span class="dsh-pm-tl-label">`+(n[e]??e)+`</span><span class="dsh-pm-tl-time">—</span><span class="dsh-pm-tl-dur"></span></div>`;let i=o[t],s=o[t+1],c=t===o.length-1,l=(s?.at??a)-i.at,u=c?L(i.status)?``:`已停留 `+I(l):`停留 `+I(l),d=i.by.kind+(i.by.sessionId===void 0?``:` `+m(i.by.sessionId));return`<div class="dsh-pm-tl-row`+(c?` current`:``)+`" data-status="`+r(i.status)+`"><span class="dsh-pm-tl-label">`+(n[e]??e)+`</span><span class="dsh-pm-tl-time">`+r(h(i.at))+`</span><span class="dsh-pm-tl-dur">`+r(u)+`</span><span class="dsh-pm-tl-by">`+r(d)+`</span>`+(i.inferred===!0?`<span class="dsh-pm-tl-inferred" title="历史回填：老记录无事件留痕，由创建时间与评论反推">回填</span>`:``)+`</div>`},u=t.map(e=>l(e,s.get(e))).join(``)+c.map(e=>l(e,s.get(e))).join(``),d=o[0].at,f=o[o.length-1],p=(L(f.status)?f.at:a)-d;return`<div class="dsh-pm-timeline">`+u+`<div class="dsh-pm-tl-total">创建 `+r(h(d))+(L(f.status)?` · 总耗时 `:` · 至今 `)+r(I(p))+`</div></div>`}function Te(e,t){return z(e,p.concat([`archived`]),l,`draft`,t)}function Ee(e,t){return z(e,B,u,`todo`,t)}function De(e){let t=R(e,`draft`),n=new Map;for(let e of t)n.has(e.status)||n.set(e.status,e);let i=[...n.values()].map(e=>`<span class="dsh-pm-strip-item" data-status="`+r(e.status)+`">`+(l[e.status]??e.status)+` <b>`+r(h(e.at))+`</b></span>`);return i.length===0?``:`<div class="dsh-pm-strip">`+i.join(`<span class="dsh-pm-strip-arrow">→</span>`)+`</div>`}const B=[`todo`,`in_progress`,`integrating`,`testing`,`in_review`,`done`],Oe=[`draft`,`brainstorming`,`decomposing`,`implementing`,`accepting`,`done`,`archived`];function ke(e,t){let n=R(e,`todo`),r=L(e.status);return n.map((i,a)=>{let o=n[a+1]?.at??(r?Math.max(e.updatedAt,i.at):t);return{status:i.status,from:i.at,to:o}})}function Ae(e,t){return e.length>t?e.slice(0,t)+`…`:e}function je(e,t,n){if(t.length===0)return`<div class="dsh-pm-empty">尚未拆分任务</div>`;let i=[...t].sort((e,t)=>e.createdAt-t.createdAt),a=[n];for(let e of i)for(let t of R(e,`todo`))a.push(t.at);for(let t of R(e,`draft`))a.push(t.at);let o=Math.min(...a),s=Math.max(...a),c=Math.max(s-o,36e5),d=e=>190+(e-o)/c*620,f=34+i.length*22+10,p=[];p.push(`<svg class="dsh-pm-gantt" viewBox="0 0 822 `+f+`" width="100%" height="`+f+`" preserveAspectRatio="xMinYMin meet" role="img" aria-label="任务甘特图">`);for(let e=0;e<=4;e++){let t=o+c*e/4,n=d(t).toFixed(1);p.push(`<line class="dsh-pm-gantt-grid" x1="`+n+`" y1="26" x2="`+n+`" y2="`+(f-10)+`" />`),p.push(`<text class="dsh-pm-gantt-axis" x="`+n+`" y="20" text-anchor="middle">`+r(h(t))+`</text>`)}for(let t of R(e,`draft`)){if(!Oe.includes(t.status))continue;let n=d(t.at).toFixed(1);p.push(`<line class="dsh-pm-gantt-mile" data-status="`+r(t.status)+`" x1="`+n+`" y1="28" x2="`+n+`" y2="`+(f-10)+`">`),p.push(`<title>`+r(e.id+` `+(l[t.status]??t.status)+` `+h(t.at))+`</title></line>`)}if(i.forEach((e,t)=>{let i=34+t*22;p.push(`<text class="dsh-pm-gantt-rowlabel" x="6" y="`+(i+13)+`">`+r(Ae(e.id+` `+e.title,24))+`</text>`),p.push(`<rect class="dsh-pm-gantt-track" x="190" y="`+(i+4)+`" width="620" height="13" rx="3" />`);for(let t of ke(e,n)){let n=d(t.from),a=Math.max(2,d(t.to)-n);p.push(`<rect class="dsh-pm-gantt-bar" data-status="`+r(t.status)+`" x="`+n.toFixed(1)+`" y="`+(i+4)+`" width="`+a.toFixed(1)+`" height="13" rx="3">`),p.push(`<title>`+r(e.id+` `+e.title+`｜`+(u[t.status]??t.status)+` `+h(t.from)+` → `+h(t.to)+`（`+I(t.to-t.from)+`）`)+`</title></rect>`)}}),n>=o&&n<=s){let e=d(n).toFixed(1);p.push(`<line class="dsh-pm-gantt-now" x1="`+e+`" y1="28" x2="`+e+`" y2="`+(f-10)+`"><title>现在</title></line>`)}p.push(`</svg>`);let m=`<div class="dsh-pm-gantt-legend">`+B.map(e=>`<span class="dsh-pm-gantt-legend-item"><i data-status="`+e+`"></i>`+u[e]+`</span>`).join(``)+`<span class="dsh-pm-gantt-legend-item"><i class="mile"></i>需求里程碑</span></div>`;return`<div class="dsh-pm-gantt-wrap">`+p.join(``)+`</div>`+m}function Me(e,t){return`<table class="dsh-pm-ttable"><thead><tr><th>任务</th><th>标题</th><th>状态</th><th>阶段</th><th>端侧</th><th>依赖</th><th>创建</th><th>耗时</th></tr></thead><tbody>`+[...e].sort((e,t)=>e.createdAt-t.createdAt).map(e=>{let n=R(e,`todo`),i=n[0].at,a=n[n.length-1],o=n.find(e=>e.status===`done`)?.at,s=L(e.status)?`共 `+I((o??a.at)-i):`已用 `+I(t-i);return`<tr class="dsh-pm-trow" data-task="`+r(e.id)+`" data-action="open-task"><td class="dsh-pm-tid">`+r(e.id)+`</td><td class="dsh-pm-ttitle">`+r(e.title)+`</td><td><span class="dsh-pm-status" data-status="`+r(e.status)+`">`+(u[e.status]??e.status)+`</span></td><td>`+r(d[e.phase]??e.phase)+`</td><td>`+r(e.side)+`</td><td class="dsh-pm-tdeps">`+(e.dependsOn.length>0?r(e.dependsOn.join(` `)):`—`)+`</td><td>`+r(h(i))+`</td><td>`+r(s)+`</td></tr>`}).join(``)+`</tbody></table>`}function Ne(e,t=Date.now()){let n=e.requirements.map(t=>({req:t,tasks:e.tasks.filter(e=>e.requirementId===t.id)})).filter(e=>e.tasks.length>0).sort((e,t)=>t.req.updatedAt-e.req.updatedAt),i=`<div class="dsh-pm-head"><button type="button" class="dsh-pm-btn" data-action="back" title="返回泳道看板">← 看板</button><h1 class="dsh-pm-title">任务</h1><span class="dsh-pm-rev">`+e.tasks.length+` 个任务 · `+n.length+` 个需求 · rev `+e.revision+`</span><button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button></div>`;if(n.length===0)return`<div class="dsh-pm-board">`+i+`<div class="dsh-pm-empty">还没有任务。两种来源：① 需求详情页点「+ 任务」人工建卡；② 窗口 agent 调用 reqboard_decompose 真拆分落库（推荐，含依赖 DAG）</div></div>`;let a=n.map(e=>{let n=e.tasks.filter(e=>e.status===`done`).length;return`<div class="dsh-pm-tasks-group"><div class="dsh-pm-tasks-group-head"><span class="dsh-pm-card-id">`+r(e.req.id)+`</span><span class="dsh-pm-status" data-status="`+r(e.req.status)+`">`+(l[e.req.status]??e.req.status)+`</span><span class="dsh-pm-tasks-group-title">`+r(e.req.title)+`</span><span class="dsh-pm-hint">`+n+`/`+e.tasks.length+` 完成</span><button type="button" class="dsh-pm-btn sm" data-action="open-req" data-req="`+r(e.req.id)+`">打开需求</button></div>`+De(e.req)+`<div class="dsh-pm-detail-section"><h3>甘特图</h3>`+je(e.req,e.tasks,t)+`</div><div class="dsh-pm-detail-section"><h3>任务清单</h3>`+Me(e.tasks,t)+`</div></div>`}).join(``);return`<div class="dsh-pm-board">`+i+`<div class="dsh-pm-tasks-page">`+a+`</div></div>`}function Pe(e,t){let n=R(e,`draft`),i=n[0],a=n[n.length-1],o=[`创建 `+h(i.at)];return a.status!==i.status&&o.push((l[a.status]??a.status)+` `+h(a.at)),L(a.status)||o.push(`已停留 `+I(t-a.at)),`<div class="dsh-pm-card-time">`+r(o.join(` · `))+`</div>`}function Fe(e){let t=e.plan;return t===void 0?``:t.approvedAt===void 0?t.rejectedAt===void 0?`<span class="dsh-pm-flag plan-pending" title="实施计划已提交，等待人批准后才能拆分">计划待批</span>`:`<span class="dsh-pm-flag plan-rejected" title="实施计划被退回，待重写">计划被退</span>`:`<span class="dsh-pm-flag plan-ok" title="实施计划已批准，可拆分落库">计划已批</span>`}function Ie(e){let t=e.plan;if(t===void 0)return`<div class="dsh-pm-plan is-empty">尚未提交实施计划。计划模式：窗口 agent 用 <code>reqboard_plan_submit</code> 先提交计划（文档路径 + 摘要 + 任务表），人在此处批准后才允许 <code>reqboard_decompose</code> 落库任务卡——拆分的粒度在人点头之前就已写死在计划里。</div>`;let n=t.approvedAt===void 0?t.rejectedAt===void 0?`<span class="dsh-pm-plan-status" data-state="pending">待批准</span>`:`<span class="dsh-pm-plan-status" data-state="rejected">已退回 `+r(h(t.rejectedAt))+`</span>`:`<span class="dsh-pm-plan-status" data-state="approved">已批准 `+r(h(t.approvedAt))+`</span>`,i=t.approvedAt===void 0?`<button type="button" class="dsh-pm-btn sm primary" data-action="plan-approve" data-id="`+r(e.id)+`">批准计划</button><button type="button" class="dsh-pm-btn sm" data-action="plan-reject" data-id="`+r(e.id)+`">退回计划</button>`:`<span class="dsh-pm-hint">拆分已解锁：窗口可用 reqboard_decompose 按此计划落库任务卡</span>`,a=t.tasks.map(e=>{let t=(e.dependsOn??[]).length>0?` · 依赖 `+r((e.dependsOn??[]).join(`,`)):``;return`<div class="dsh-pm-plan-task"><span class="dsh-pm-plan-key">`+r(e.key)+`</span><span class="dsh-pm-plan-title">`+r(e.title)+`</span><span class="dsh-pm-plan-meta">`+r(d[e.phase??`implement`]??e.phase??``)+` / `+r(e.side??``)+t+`</span>`+(e.acceptance!==void 0&&e.acceptance.length>0?`<span class="dsh-pm-plan-accept">验收：`+r(e.acceptance)+`</span>`:`<span class="dsh-pm-plan-accept missing">缺验收标准</span>`)+`</div>`}).join(``);return`<div class="dsh-pm-plan"><div class="dsh-pm-plan-head">`+n+`<code class="dsh-pm-plan-path">`+r(t.path)+`</code><span class="dsh-pm-hint">提交 `+r(h(t.submittedAt))+` · `+t.tasks.length+` 个任务</span>`+i+`</div><div class="dsh-pm-plan-summary">`+r(t.summary)+`</div>`+(t.rejectedReason===void 0?``:`<div class="dsh-pm-plan-reason">退回理由：`+r(t.rejectedReason)+`</div>`)+`<div class="dsh-pm-plan-tasks">`+a+`</div></div>`}function Le(e){return e.status===`accepting`?e.verification===void 0?`<span class="dsh-pm-flag verify-pending" title="验收态但还没提交验收材料">待验收材料</span>`:`<span class="dsh-pm-flag verify-pending" title="验收材料已提交，等人工审核">待人工审核</span>`:``}function Re(e){return e.status===`done`?e.archive===void 0?`<span class="dsh-pm-flag archive-pending" title="已完成，等窗口准备归档材料">待归档材料</span>`:`<span class="dsh-pm-flag archive-pending" title="归档材料已备，等人点归档">待归档</span>`:``}function ze(e){let t=e.verification;if(t===void 0)return`<div class="dsh-pm-block is-empty">`+(e.status===`implementing`||e.status===`accepting`?`窗口尚未提交验收材料。人工审核前需要证据：窗口用 <code>reqboard_verify_submit</code> 提交「做了什么 + 怎么验的 + 看到什么结果」。`:`尚未进入验收阶段。`)+`</div>`;let n=t.decision===`pass`?`<span class="dsh-pm-review" data-state="pass">人工审核通过 `+r(t.reviewedAt===void 0?``:h(t.reviewedAt))+`</span>`:t.decision===`rework`?`<span class="dsh-pm-review" data-state="rework">已退回返工 `+r(t.reviewedAt===void 0?``:h(t.reviewedAt))+`</span>`:`<span class="dsh-pm-review" data-state="pending">待人工审核</span>`,i=e.status===`accepting`?`<button type="button" class="dsh-pm-btn sm primary" data-action="verify-pass" data-id="`+r(e.id)+`">验收通过</button><button type="button" class="dsh-pm-btn sm" data-action="verify-rework" data-id="`+r(e.id)+`">退回返工</button>`:``,a=t.evidence.map(e=>`<li>`+r(e)+`</li>`).join(``);return`<div class="dsh-pm-block"><div class="dsh-pm-block-head">`+n+`<span class="dsh-pm-hint">提交 `+r(h(t.submittedAt))+`</span>`+i+`</div><div class="dsh-pm-block-summary">`+r(t.summary)+`</div><ul class="dsh-pm-evidence">`+a+`</ul>`+(t.reviewNote===void 0?``:`<div class="dsh-pm-block-note">审核意见：`+r(t.reviewNote)+`</div>`)+`</div>`}function Be(e){let t=e.archive;if(t===void 0)return`<div class="dsh-pm-block is-empty">`+(e.status===`done`?`窗口尚未准备归档材料。归档不是挪目录：窗口用 <code>reqboard_archive_submit</code> 提交需求目录、文档清单、合并去向（只允许既有规范目录：docs/ 或 agent-dh/docs/ 下的 adr|architecture|guides|rfcs|work-logs|strategy-research）与一句话索引条目，人再点归档；必填文档与合并去向按需求类型限定，规范见 agent-dh/docs/architecture/requirement-archive.md。`:`归档在需求完成（done）后进行；不同需求类型的必填文档与合并去向见 agent-dh/docs/architecture/requirement-archive.md。`)+`</div>`;let n=t.archivedAt===void 0?`<span class="dsh-pm-review" data-state="pending">待归档（材料已备）</span>`:`<span class="dsh-pm-review" data-state="pass">已归档 `+r(h(t.archivedAt))+`</span>`,i=e.status===`done`&&t.archivedAt===void 0?`<button type="button" class="dsh-pm-btn sm primary" data-action="archive-req" data-id="`+r(e.id)+`">归档</button>`:``,a=t.docs.map(e=>`<li><span class="dsh-pm-doc-kind">`+r(Ve[e.kind]??e.kind)+`</span> <code>`+r(e.path)+`</code></li>`).join(``),o=t.mergedInto.map(e=>`<li><code>`+r(e)+`</code></li>`).join(``);return`<div class="dsh-pm-block"><div class="dsh-pm-block-head">`+n+`<code class="dsh-pm-block-path">`+r(t.dir)+`</code><span class="dsh-pm-hint">材料提交 `+r(h(t.submittedAt))+`</span>`+i+`</div><div class="dsh-pm-block-summary">索引条目：`+r(t.indexEntry)+`</div><div class="dsh-pm-doc-group"><span class="dsh-pm-hint">需求目录内的文档</span><ul class="dsh-pm-doc-list">`+a+`</ul></div><div class="dsh-pm-doc-group"><span class="dsh-pm-hint">合并进的项目文档</span><ul class="dsh-pm-doc-list">`+o+`</ul></div>`+He(t)+`</div>`}const Ve={requirement:`需求说明`,plan:`实施计划`,verification:`验收材料`,retro:`复盘`,notes:`其他`};function He(e){let t=e.manualUpdates??[];return t.length===0?e.manualNote===void 0?``:`<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">项目说明书更新</span><div class="dsh-pm-block-summary">无（`+r(e.manualNote)+`）</div></div>`:`<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">项目说明书更新（金字塔向上生长）</span><ul class="dsh-pm-doc-list">`+t.map(e=>`<li><code>`+r(e.path)+`</code><span class="dsh-pm-doc-kind">`+r(e.section)+`</span><span>`+r(e.summary)+`</span></li>`).join(``)+`</ul></div>`}const V=8e3;var H=class extends Error{code;constructor(e,t){super(e),this.code=t}};async function U(e){let t=await e;if(!t.ok)throw new H(`HTTP `+t.status);let n=await t.json().catch(()=>({}));if(n.success!==!0)throw new H(n.error??`API 返回失败`,n.code);return n.data}const W=e=>U(fetch(e,{signal:AbortSignal.timeout(V)})),G=(e,t)=>U(fetch(e,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify(t),signal:AbortSignal.timeout(V)})),Ue=()=>W(`/dashboard/api/reqboard/`),We=()=>W(`/dashboard/api/reqboard/triage`);function Ge(e){return G(`/dashboard/api/reqboard/req/create`,e)}function Ke(e){return G(`/dashboard/api/reqboard/req/move`,e)}function qe(e){return G(`/dashboard/api/reqboard/req/plan/approve`,e)}function Je(e){return G(`/dashboard/api/reqboard/req/plan/reject`,e)}function Ye(e){return G(`/dashboard/api/reqboard/req/verify/pass`,e)}function Xe(e){return G(`/dashboard/api/reqboard/req/verify/rework`,e)}function Ze(e){return G(`/dashboard/api/reqboard/req/archive`,e)}function Qe(e){return G(`/dashboard/api/reqboard/task/create`,e)}function $e(e){return G(`/dashboard/api/reqboard/comment`,e)}function K(e){return G(`/dashboard/api/reqboard/triage/confirm`,e)}function et(e){return G(`/dashboard/api/reqboard/triage/rebind`,e)}function tt(e){return G(`/dashboard/api/reqboard/triage/reject`,e)}function nt(e){let t=new EventSource(`/dashboard/api/reqboard/events`);return t.onmessage=t=>{try{let n=JSON.parse(t.data);e(n.revision,n.kind)}catch{}},()=>t.close()}function q(){let e=()=>window;return{getSessions:()=>{try{let t=e().__dshPmSessions??e().__dshPmCtx?.sessions;if(t&&typeof t.open==`function`&&t.list)return t}catch{}},getWorkspaces:()=>{try{let t=e().__dshPmWorkspaces??e().__dshPmCtx?.workspaces;if(t&&t.list)return t}catch{}}}}function J(e=q()){try{let t=e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[];return new Set(t)}catch{return new Set}}async function Y(e,t){let n=e.getSessions();if(n===void 0)return`unavailable`;let r=e=>{try{return n.list.getSnapshot().byId[e]!==void 0}catch{return!1}};if(r(t))return(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`);try{await n.refresh()}catch{}return r(t)?(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`):`missing`}const X=`dsh-pmboard:view`;function rt(){try{return sessionStorage.getItem(X)===`list`?`list`:`lanes`}catch{return`lanes`}}function it(e){try{sessionStorage.setItem(X,e)}catch{}}const at=`dsh-pmboard:list`,ot=[`stage`,`progress`,`updated`,`created`,`title`];function st(){let e={sortKey:`stage`,sortDir:`asc`,pageSize:10};try{let t=sessionStorage.getItem(at);if(t===null)return e;let n=JSON.parse(t),r=typeof n.sortKey==`string`&&ot.includes(n.sortKey)?n.sortKey:e.sortKey;return{sortKey:r,sortDir:n.sortDir===`asc`||n.sortDir===`desc`?n.sortDir:b(r),pageSize:typeof n.pageSize==`number`&&y.includes(n.pageSize)?n.pageSize:10}}catch{return e}}function ct(){return{openBoard:()=>{},closeBoard:()=>{},toggleBoard:()=>{},getSnapshot:()=>({boardOpen:!1}),refresh:()=>{}}}function lt(e){let t,n=[],r={kind:`board`},a=rt(),s=st(),l=s.sortKey,u=s.sortDir,d=s.pageSize,f=1,p,m,h=()=>({sortKey:l,sortDir:u,page:f,pageSize:d}),g=()=>J(),_=()=>{try{sessionStorage.setItem(at,JSON.stringify({sortKey:l,sortDir:u,pageSize:d}))}catch{}},x=()=>{if(p!==void 0){if(t===void 0){p.innerHTML=Ce();return}switch(r.kind){case`board`:p.innerHTML=v(t,Date.now(),a,h(),g());break;case`req`:{let e=t.requirements.find(e=>e.id===r.reqId);p.innerHTML=e?ae(e,t.tasks,Date.now(),g()):v(t,Date.now(),a,h(),g()),e?D():r={kind:`board`};break}case`task`:{let e=t.tasks.find(e=>e.id===r.taskId),n=e?t.requirements.find(t=>t.id===e.requirementId):void 0;p.innerHTML=e?de(e,n,Date.now(),t.tasks,g()):v(t,Date.now(),a,h(),g()),e||(r={kind:`board`});break}case`tasks`:p.innerHTML=Ne(t);break;case`triage`:p.innerHTML=Se(n,t)}}},S=async()=>{try{let[e,r]=await Promise.all([Ue(),We()]);t=e,n=r.pending,x()}catch(e){p!==void 0&&(p.innerHTML=we(String(e)))}},C=()=>{m?.(),m=nt(()=>{S()})},w=e=>{let i=e.target,o=i.closest(`[data-pmpage]`);if(o!==null&&t!==void 0){let e=Number(o.dataset.pmpage);Number.isFinite(e)&&e>=1&&(f=e,x());return}let s=i.closest(`[data-action]`);if(s!==null&&t!==void 0)switch(s.dataset.action??``){case`refresh`:S();return;case`switch-view`:{let e=s.dataset.view;(e===`lanes`||e===`list`)&&(a=e,it(e),r={kind:`board`},x());return}case`list-sort`:{let e=s.dataset.key;if(e===void 0||!ot.includes(e))return;e===l?u=u===`asc`?`desc`:`asc`:(l=e,u=b(e)),f=1,_(),x();return}case`open-doc`:{let e=s.dataset.path;e&&E(e);return}case`new-req`:{let e=window.prompt(`需求标题`);e&&e.trim()&&Ge({title:e.trim()}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`open-req`:s.dataset.req&&(r={kind:`req`,reqId:s.dataset.req},x());return;case`open-task`:s.dataset.task&&(r={kind:`task`,taskId:s.dataset.task},x());return;case`open-tasks`:r={kind:`tasks`},x();return;case`new-task`:{let e=s.dataset.id;if(!e)return;let t=window.prompt(`任务标题`);t&&t.trim()&&Qe({requirementId:e,title:t.trim(),phase:`implement`,side:`fullstack`}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`back`:r={kind:`board`},x();return;case`back-req`:r={kind:`req`,reqId:s.dataset.req??``},x();return;case`move-req`:{let e=s.dataset.id??(r.kind===`req`?r.reqId:void 0),t=s.dataset.to;e&&t&&Ke({id:e,to:t,actor:`human`,reason:s.dataset.id?`看板泳道卡面操作`:`需求详情页操作`}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`add-comment`:{let e=(p?.querySelector(`[data-role="comment-input"]`))?.value.trim();e&&s.dataset.target&&s.dataset.id&&$e({target:s.dataset.target,id:s.dataset.id,body:e,actor:`human`}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`jump-session`:{let e=s.dataset.sid;e&&Y(q(),e).then(e=>{e===`archived`?window.alert(`该会话已归档（日志保留，侧栏不可见）`):e===`missing`?window.alert(`该会话不在当前列表（可能已删除）`):e===`unavailable`&&window.alert(`会话服务暂不可用`)});return}case`verify-pass`:{let e=s.dataset.id;e&&Ye({id:e}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`verify-rework`:{let e=s.dataset.id;if(!e)return;let t=window.prompt(`退回返工的意见（窗口会按它整改）`);if(t===null)return;Xe({id:e,note:t.trim()||`（未填意见）`}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`archive-req`:{let e=s.dataset.id;e&&Ze({id:e}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`plan-approve`:{let e=s.dataset.id;e&&qe({id:e}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`plan-reject`:{let e=s.dataset.id;if(!e)return;let t=window.prompt(`退回理由（窗口会按它重写计划）`);if(t===null)return;Je({id:e,reason:t.trim()||`（未填理由）`}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`triage-confirm`:{let e=s.dataset.triage;if(!e)return;let t=n.find(t=>t.id===e);if(t?.suggestedAction===`bind_req`&&t.suggestedTargetId)K({triageId:e,action:`bind_req`,targetId:t.suggestedTargetId}).then(()=>S()).catch(e=>window.alert(String(e)));else{let t=s.closest(`.dsh-pm-triage`),n=t?.querySelector(`[data-role="triage-title"]`)?.value.trim(),r=t?.querySelector(`[data-role="triage-category"]`)?.value;K({triageId:e,action:`create_req`,...n?{title:n}:{},...r?{category:r}:{}}).then(()=>S()).catch(e=>window.alert(String(e)))}return}case`triage-rebind`:{let e=p?.querySelector(`.dsh-pm-rebind-host`);e&&(e.style.display=`flex`,e.dataset.triage=s.dataset.triage??``);return}case`triage-rebind-confirm`:{let e=p?.querySelector(`.dsh-pm-rebind-host`),t=e?.dataset.triage,n=e?.querySelector(`[data-role="rebind-select"]`);t&&n?.value&&et({triageId:t,targetId:n.value}).then(()=>S()).catch(e=>window.alert(String(e)));return}case`triage-reject`:{let e=s.dataset.triage;e&&tt({triageId:e}).then(()=>S()).catch(e=>window.alert(String(e)));return}}},T=e=>{let t=e.target;if(t===null||typeof t.closest!=`function`)return;let n=t.closest(`[data-action="list-size"]`);if(n!==null){let e=Number(n.value);if(!y.includes(e))return;d=e,f=1,_(),x();return}},E=async e=>{let t=``,n=``;try{let r=await(await fetch(`/dashboard/api/reqboard/file?path=`+encodeURIComponent(e))).json();r.success===!0&&r.data?.content!==void 0?t=r.data.content:n=r.error??`文件打开失败`}catch(e){n=`文件打开失败：`+String(e)}let r=document.createElement(`div`);r.className=`dsh-pm-doc-modal-overlay`;let i=document.createElement(`div`);i.className=`dsh-pm-doc-modal`;let a=document.createElement(`div`);a.className=`dsh-pm-doc-modal-head`;let o=document.createElement(`span`);o.className=`dsh-pm-doc-modal-title`,o.textContent=e;let s=document.createElement(`button`);s.type=`button`,s.className=`dsh-pm-btn`,s.textContent=`关闭`,a.append(o,s);let c=document.createElement(`div`);if(c.className=`dsh-pm-doc-modal-body`,n)c.textContent=n;else{let e=document.createElement(`pre`);e.textContent=t,c.append(e)}i.append(a,c),r.append(i);let l=()=>{r.remove()};s.addEventListener(`click`,l),r.addEventListener(`click`,e=>{e.target===r&&l()}),document.addEventListener(`keydown`,e=>{e.key===`Escape`&&l()},{once:!0}),document.body.appendChild(r)},D=async()=>{if(p===void 0)return;let e=p.querySelectorAll(`[data-doc-path]`);await Promise.all(Array.from(e).map(async e=>{let t=e.dataset.docPath;if(!t)return;let n=!1;try{n=(await(await fetch(`/dashboard/api/reqboard/file?path=`+encodeURIComponent(t))).json()).success===!0}catch{n=!1}if(!n){e.classList.add(`is-missing`),e.setAttribute(`title`,`文件不存在（未落盘或路径错误）`);let t=e.querySelector(`[data-action="open-doc"]`);t&&(t.removeAttribute(`data-action`),t.classList.add(`dsh-pm-doc-missing`))}}))},O=i({prefix:`dsh-pm`,panelName:o,activeAttr:`data-dsh-pm-active`,otherActiveAttrs:c,pollMs:2e4,pauseOnHidden:!0,buildContainer:()=>{let e=document.createElement(`div`);return e.dataset.dshPmView=``,e.className=`dsh-pm-view`,e},onMount:e=>(p=e,e.addEventListener(`click`,w),e.addEventListener(`change`,T),S(),C(),()=>{e.removeEventListener(`click`,w),e.removeEventListener(`change`,T),m?.(),m=void 0,p=void 0}),onPoll:()=>{S()},onOpen:()=>{S()}}),k=e;return k.openBoard=O.open,k.closeBoard=O.close,k.toggleBoard=O.toggle,k.getSnapshot=()=>({boardOpen:O.isActive()}),k.refresh=()=>{S()},()=>{O.dispose()}}const ut=`dsh-pmboard/footer-action.css`,Z=`dsh-pmboard:open-board`,dt={draft:`立项`,brainstorming:`需求分析`,planning:`技术设计`,decomposing:`拆分`,implementing:`实施中`,accepting:`待验收`,done:`完成`},ft=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function pt(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${ut}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=ut,e.textContent=`
		.dsh-reqboard-foot {
		  display: flex; align-items: center; gap: 8px;
		  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
		  font: inherit; font-size: 13px; cursor: pointer;
		  -webkit-appearance: none; appearance: none;
		}
		.dsh-reqboard-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
		.dsh-reqboard-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
		.dsh-reqboard-foot.wide {
		  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
		  border-radius: 8px; justify-content: flex-start; text-align: left;
		}
		.dsh-reqboard-foot.rail {
		  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
		  justify-content: center; padding: 0;
		}
		.dsh-reqboard-foot-icon { display: inline-flex; flex: none; }
		.dsh-reqboard-foot.rail .dsh-reqboard-foot-label { display: none; }
		.dsh-reqboard-foot-icon svg { width: 16px; height: 16px; }
		
		/* ---- 悬停下拉：进行中需求速览 + 会话跳转 ---- */
		.dsh-reqboard-foot-wrap { position: relative; }
		.dsh-reqboard-drop {
		  position: absolute; bottom: calc(100% + 6px); left: 0; z-index: 2400;
		  width: 296px; max-height: 56vh; overflow-y: auto;
		  background: var(--dsw-bg, #fff); border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
		  border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,.20); padding: 6px;
		  display: flex; flex-direction: column; gap: 2px;
		}
		.dsh-reqboard-foot-wrap.rail .dsh-reqboard-drop { left: calc(100% + 6px); bottom: 0; }
		.dsh-reqboard-drop-head {
		  display: flex; align-items: center; gap: 6px; padding: 6px 8px 8px;
		  font-size: 11px; color: var(--dsw-text-secondary, #999); font-weight: 600;
		}
		.dsh-reqboard-drop-head .n { margin-left: auto; font-weight: 400; }
		.dsh-reqboard-item {
		  display: flex; flex-direction: column; gap: 5px; width: 100%; text-align: left;
		  border: none; background: transparent; color: inherit; font: inherit;
		  padding: 8px; border-radius: 7px; cursor: pointer;
		}
		.dsh-reqboard-item:hover { background: var(--dsw-hover, rgba(128,128,128,.10)); }
		.dsh-reqboard-item-top { display: flex; align-items: center; gap: 6px; }
		.dsh-reqboard-item-title {
		  font-size: 12px; font-weight: 600; color: var(--dsw-text-primary, #222);
		  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
		}
		.dsh-reqboard-badge {
		  flex: none; font-size: 10px; padding: 1px 7px; border-radius: 9px;
		  background: rgba(128,128,128,.16); color: var(--dsw-text-primary, #444); font-weight: 600;
		}
		.dsh-reqboard-badge[data-status="implementing"] { background: rgba(74,125,255,.18); color: #2f5fd0; }
		.dsh-reqboard-badge[data-status="planning"] { background: rgba(240,160,32,.20); color: #a86a00; }
		.dsh-reqboard-badge[data-status="brainstorming"] { background: rgba(142,68,173,.18); color: #6f2f8c; }
		.dsh-reqboard-badge[data-status="accepting"] { background: rgba(23,162,184,.18); color: #0e7c8f; }
		.dsh-reqboard-badge[data-status="done"] { background: rgba(40,167,69,.18); color: #1e7e34; }
		.dsh-reqboard-item-meta {
		  display: flex; align-items: center; gap: 6px; font-size: 10px;
		  color: var(--dsw-text-secondary, #999);
		}
		.dsh-reqboard-win {
		  font-family: ui-monospace, monospace; padding: 0 4px; border-radius: 4px;
		  background: rgba(128,128,128,.14);
		}
		.dsh-reqboard-jump { margin-left: auto; color: #4a7dff; font-weight: 600; }
		/* 来源会话已归档：整条压暗、窗口码划掉、右侧写「已归档」（点击只打开看板） */
		.dsh-reqboard-item.is-archived .dsh-reqboard-item-title { color: var(--dsw-text-secondary, #888); }
		.dsh-reqboard-item.is-archived .dsh-reqboard-badge { opacity: .6; }
		.dsh-reqboard-win.is-archived {
		  text-decoration: line-through; opacity: .65; background: transparent;
		  border: 1px dashed var(--dsw-border, rgba(128,128,128,.35));
		}
		.dsh-reqboard-jump.is-archived { color: var(--dsw-text-secondary, #999); font-weight: 400; }
		.dsh-reqboard-bar { display: flex; align-items: center; gap: 7px; }
		.dsh-reqboard-bar-track {
		  flex: 1; height: 4px; border-radius: 2px; overflow: hidden; background: rgba(128,128,128,.20);
		}
		.dsh-reqboard-bar-fill { display: block; height: 100%; background: linear-gradient(90deg,#4a7dff,#8e44ad); }
		.dsh-reqboard-bar-num { font-size: 10px; color: var(--dsw-text-secondary, #999); font-variant-numeric: tabular-nums; }
		.dsh-reqboard-empty { padding: 18px 8px; text-align: center; font-size: 12px; color: var(--dsw-text-secondary, #999); }
		.dsh-reqboard-drop-foot {
		  margin-top: 2px; padding: 7px 8px 3px; border-top: 1px solid var(--dsw-border, rgba(128,128,128,.16));
		  display: flex; justify-content: space-between; align-items: center;
		  font-size: 11px; color: var(--dsw-text-secondary, #999);
		}
		.dsh-reqboard-drop-foot button {
		  border: none; background: transparent; color: #4a7dff; font: inherit; font-size: 11px;
		  cursor: pointer; padding: 2px 4px; border-radius: 4px;
		}
		.dsh-reqboard-drop-foot button:hover { background: rgba(74,125,255,.12); }
		`,document.head.appendChild(e)}function mt(t){let{wide:n}=t,r=s,[i,a]=(0,e.useState)(!1),[o,c]=(0,e.useState)(null),[l,u]=(0,e.useState)(null),d=(0,e.useRef)(0),f=(0,e.useRef)(null),p=(0,e.useRef)(null),m=(0,e.useRef)(new Set),h=(0,e.useCallback)(async e=>{if(!(!e&&d.current>0&&Date.now()-d.current<15e3))try{let e=await(await fetch(`/dashboard/api/reqboard/requirements/summary`,{signal:AbortSignal.timeout(8e3)})).json().catch(()=>({}));e.success===!0?(m.current=J(),c(e.data?.requirements??[]),u(null),d.current=Date.now()):u(e.error??`加载失败`)}catch(e){u(String(e))}},[]),g=(0,e.useCallback)(()=>{p.current!==null&&(window.clearTimeout(p.current),p.current=null),!i&&(f.current=window.setTimeout(()=>{a(!0),h(!1)},120))},[i,h]),_=(0,e.useCallback)(()=>{f.current!==null&&(window.clearTimeout(f.current),f.current=null),p.current=window.setTimeout(()=>a(!1),200)},[]),v=(0,e.useCallback)(e=>{let t=e.sourceSessionId;if(t===null||t.length===0||m.current.has(t)){window.dispatchEvent(new CustomEvent(Z,{detail:{open:!0}}));return}Y(q(),t).then(e=>{e===`archived`?window.alert(`该会话已归档（日志保留，侧栏不可见）`):e===`missing`?window.alert(`该会话不在当前列表（可能已删除）`):e===`unavailable`&&window.alert(`会话服务暂不可用，已打开项目看板`),e!==`opened`&&window.dispatchEvent(new CustomEvent(Z,{detail:{open:!0}}))})},[]),y=(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-reqboard-foot wide`:`dsh-reqboard-foot rail`,title:`${r}（悬停查看进行中需求）`,"aria-label":r,onClick:()=>{window.dispatchEvent(new CustomEvent(Z,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},ft),(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-label`,key:`l`},r)]:(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},ft));if(!i)return(0,e.createElement)(`div`,{className:`dsh-reqboard-foot-wrap${n?``:` rail`}`,onMouseEnter:g,onMouseLeave:_},y);let b=o===null?(0,e.createElement)(`div`,{className:`dsh-reqboard-empty`},l===null?`加载中…`:`加载失败：${l}`):o.length===0?(0,e.createElement)(`div`,{className:`dsh-reqboard-empty`},`暂无进行中的需求`):o.map(t=>{let n=Number.isFinite(t.percentage)?t.percentage:0,r=t.sourceSessionId,i=r!==null&&r.length>0,a=i&&m.current.has(r);return(0,e.createElement)(`button`,{key:t.id,type:`button`,className:`dsh-reqboard-item${a?` is-archived`:``}`,title:a?`${t.id}《${t.title}》— 来源会话 ${r} 已归档，无法跳转（点击打开看板）`:i?`${t.id}《${t.title}》— 点击跳转到会话 ${r}`:`${t.id}《${t.title}》— 人工建卡，无来源会话（点击打开看板）`,onClick:()=>v(t)},(0,e.createElement)(`div`,{className:`dsh-reqboard-item-top`,key:`top`},[(0,e.createElement)(`span`,{className:`dsh-reqboard-item-title`,key:`t`},`${t.id} ${t.title}`),(0,e.createElement)(`span`,{className:`dsh-reqboard-badge`,"data-status":t.status,key:`b`},dt[t.status]??t.status)]),(0,e.createElement)(`div`,{className:`dsh-reqboard-item-meta`,key:`meta`},[t.windowCode===null?(0,e.createElement)(`span`,{key:`w`},`人工建卡`):(0,e.createElement)(`span`,{className:`dsh-reqboard-win${a?` is-archived`:``}`,key:`w`,title:a?`该会话已归档`:void 0},t.windowCode),(0,e.createElement)(`span`,{key:`s`},t.tasksTotal>0?`${t.tasksTotal} 任务${t.tasksActive>0?` · ${t.tasksActive} 进行中`:``}`:`未拆分`),(0,e.createElement)(`span`,{className:`dsh-reqboard-jump${a?` is-archived`:``}`,key:`j`},a?`已归档`:i?`跳转 →`:`看板 →`)]),(0,e.createElement)(`div`,{className:`dsh-reqboard-bar`,key:`bar`},[(0,e.createElement)(`span`,{className:`dsh-reqboard-bar-track`,key:`tr`},(0,e.createElement)(`i`,{className:`dsh-reqboard-bar-fill`,style:{width:`${n}%`}})),(0,e.createElement)(`span`,{className:`dsh-reqboard-bar-num`,key:`n`},`${t.tasksDone}/${t.tasksTotal}`)]))}),x=(0,e.createElement)(`div`,{className:`dsh-reqboard-drop`,onMouseEnter:g,onMouseLeave:_},[(0,e.createElement)(`div`,{className:`dsh-reqboard-drop-head`,key:`h`},[(0,e.createElement)(`span`,{key:`a`},`进行中需求`),(0,e.createElement)(`span`,{className:`n`,key:`b`},o===null?``:String(o.length))]),b,(0,e.createElement)(`div`,{className:`dsh-reqboard-drop-foot`,key:`f`},[(0,e.createElement)(`span`,{key:`l`},`点击条目跳转会话`),(0,e.createElement)(`button`,{key:`r`,type:`button`,onClick:()=>{h(!0)}},`刷新`)])]);return(0,e.createElement)(`div`,{className:`dsh-reqboard-foot-wrap${n?``:` rail`}`,onMouseEnter:g,onMouseLeave:_},[y,x])}const Q=[{key:`draft`,label:`立项`},{key:`brainstorming`,label:`需求分析`},{key:`planning`,label:`技术设计`},{key:`decomposing`,label:`拆分`},{key:`implementing`,label:`实施`},{key:`accepting`,label:`验收`},{key:`done`,label:`完成`}],$={draft:`立项`,brainstorming:`需求分析`,planning:`技术设计`,decomposing:`拆分`,implementing:`实施中`,accepting:`待验收`,done:`完成`,archived:`归档`,canceled:`已取消`},ht={todo:`○`,in_progress:`◐`,integrating:`⇄`,testing:`⚗`,in_review:`👁`,done:`✓`,canceled:`✕`},gt={todo:`待办`,in_progress:`开发中`,integrating:`联调中`,testing:`测试中`,in_review:`待评审`,done:`已完成`,canceled:`已取消`};function _t(e){if(typeof e==`string`&&e.length>0)return e;try{let e=window,t=(e.__dshPmSessions??e.__dshPmCtx?.sessions)?.list?.getSnapshot?.(),n=t?.current??t?.currentSessionId;if(typeof n==`string`&&n.length>0)return n}catch{}}function vt(e){if(!Number.isFinite(e)||e<=0)return``;let t=Math.floor(e/6e4);return t<60?`${t}m`:`${Math.floor(t/60)}h${t%60>0?String(t%60).padStart(2,`0`):``}`}function yt(e){if(typeof e!=`number`||!Number.isFinite(e))return``;let t=new Date(e),n=e=>String(e).padStart(2,`0`);return`${n(t.getMonth()+1)}-${n(t.getDate())} ${n(t.getHours())}:${n(t.getMinutes())}`}function bt(e){if(e===void 0)return``;if(e.kind===`human`)return`人`;if(e.kind===`system`)return`系统`;let t=e.sessionId;return typeof t==`string`&&t.length>0?`w-${t.replace(/^session-/,``).slice(0,8)}`:`窗口`}function xt(e,t){return t<0?`pending`:e<t?`done`:e===t?`current`:`pending`}function St(t){let n=t?.sessionId,[r,i]=(0,e.useState)(null),[a,o]=(0,e.useState)(!1),[s,c]=(0,e.useState)(null),l=(0,e.useRef)(null),u=(0,e.useRef)(void 0);(0,e.useEffect)(()=>{let e=!0,t=async()=>{let t=_t(n);if(t===void 0){e&&(u.current=void 0,i(null));return}t!==u.current&&(u.current=t,e&&i(null));try{let n=await fetch(`/dashboard/api/reqboard/session/${encodeURIComponent(t)}/progress`,{signal:AbortSignal.timeout(8e3)});if(!n.ok)return;let r=await n.json();if(!e)return;i(r.success===!0?r.data??null:null)}catch{}};t();let r=window.setInterval(()=>{t()},15e3);return()=>{e=!1,window.clearInterval(r)}},[n]),(0,e.useEffect)(()=>{if(!a)return;let e=e=>{let t=l.current;t!==null&&!t.contains(e.target)&&o(!1)};return document.addEventListener(`mousedown`,e),()=>document.removeEventListener(`mousedown`,e)},[a]);let d=r?.requirement;if(r===null||r.hasRequirement!==!0||d==null)return null;r.progress?.percentage;let f=r.progress?.done??0,p=r.progress?.total??0,m=d.status??`draft`,h=Q.findIndex(e=>e.key===m),g=d.title??`（未命名需求）`,_=r.closed===!0,v=[];Q.forEach((t,n)=>{let r=xt(n,h),i=s===t.key;v.push((0,e.createElement)(`div`,{key:`n-${t.key}`,className:`dsh-pm-flow-node`,"data-state":r,"data-selected":i?`true`:void 0,onClick:e=>{e.stopPropagation(),c(t.key),o(!0)}},[(0,e.createElement)(`span`,{key:`d`,className:`dsh-pm-flow-dot`},r===`done`?`✓`:r===`current`?`●`:n+1),(0,e.createElement)(`span`,{key:`l`,className:`dsh-pm-flow-label`},t.label)])),n<Q.length-1&&v.push((0,e.createElement)(`div`,{key:`l-${t.key}`,className:`dsh-pm-flow-link`,"data-state":n<h?`done`:`pending`}))});let y=(0,e.createElement)(`div`,{key:`flow`,className:`dsh-pm-cprog-inline${_?` is-closed`:``}`,title:`${d.id??``}《${g}》${$[m]??m}${_?`（本会话最近完成）`:``} · 点击节点查看详情`,"aria-expanded":a},[(0,e.createElement)(`div`,{key:`f`,className:`dsh-pm-flow`},v),(0,e.createElement)(`span`,{key:`c`,className:`dsh-pm-cprog-inline-count`},p>0?`${f}/${p}`:$[m]??m)]);if(!a)return(0,e.createElement)(`div`,{className:`dsh-pm-cprog`,ref:l},y);let b=r.tasks??[],x=Q.find(e=>e.key===s)?.label??`详情`,S={draft:b.filter(e=>e.phase===`draft`||e.status===`todo`),brainstorming:b.filter(e=>e.phase===`brainstorming`||e.phase===`analysis`),planning:b.filter(e=>e.phase===`planning`||e.phase===`design`),decomposing:b.filter(e=>e.phase===`decomposing`||e.phase===`breakdown`),implementing:b.filter(e=>e.status===`in_progress`||e.status===`integrating`||e.phase===`implement`),accepting:b.filter(e=>e.status===`testing`||e.status===`in_review`||e.phase===`review`||e.phase===`test`),done:b.filter(e=>e.status===`done`)},C=s?S[s]??b:b,w=C.length===0?[(0,e.createElement)(`div`,{key:`empty`,className:`dsh-pm-cprog-empty`},s?`${x}阶段暂无任务`:`尚未拆分任务`)]:C.map((t,n)=>(0,e.createElement)(`div`,{key:t.id??`t${n}`,className:`dsh-pm-cprog-task`,"data-status":t.status??`todo`},[(0,e.createElement)(`span`,{key:`i`,className:`dsh-pm-cprog-task-ico`},ht[t.status??`todo`]??`○`),(0,e.createElement)(`div`,{key:`b`,className:`dsh-pm-cprog-task-body`},[(0,e.createElement)(`div`,{key:`t`,className:`dsh-pm-cprog-task-title`},t.title??t.id??``),(0,e.createElement)(`div`,{key:`m`,className:`dsh-pm-cprog-task-meta`},[gt[t.status??``]??t.status??``,t.side!==void 0&&t.side.length>0?`· ${t.side}`:``,(()=>{let e=vt(t.durationMs??0);return e.length>0?`· 已投入 ${e}`:``})()].filter(e=>e.length>0).join(` `))])])),T=(r.timeline??[]).slice(-8).reverse(),E=s?T.filter(e=>e.status===s):T,D=E.length===0?[(0,e.createElement)(`div`,{key:`empty`,className:`dsh-pm-cprog-empty`},s?`${x}阶段暂无状态记录`:`暂无状态记录`)]:E.map((t,n)=>(0,e.createElement)(`div`,{key:`tl${n}`,className:`dsh-pm-cprog-tl-row`},[(0,e.createElement)(`span`,{key:`t`,className:`dsh-pm-cprog-tl-time`},yt(t.at)),(0,e.createElement)(`span`,{key:`x`,className:`dsh-pm-cprog-tl-text`},`${$[t.status??``]??t.status??``}${bt(t.by).length>0?` by ${bt(t.by)}`:``}${typeof t.reason==`string`&&t.reason.length>0?` — ${t.reason}`:``}${t.inferred===!0?`（回填）`:``}`)])),O=(0,e.createElement)(`div`,{key:`panel`,className:`dsh-pm-cprog-detail-panel`},[(0,e.createElement)(`div`,{key:`h`,className:`dsh-pm-cprog-panel-head`},[(0,e.createElement)(`span`,{key:`t`,className:`dsh-pm-cprog-panel-title`},s?`${x} · ${d.id??``}`:`${d.id??``} · ${g}`),(0,e.createElement)(`span`,{key:`s`,className:`dsh-pm-status-badge`,"data-status":s??m},s?x:$[m]??m)]),_?(0,e.createElement)(`div`,{key:`closed`,className:`dsh-pm-cprog-panel-note`},`本会话已无进行中需求 —— 以上是最近关联的需求（已完成/已归档），可作为「这个会话做了什么」的回顾。`):null,typeof d.description==`string`&&d.description.length>0&&!s?(0,e.createElement)(`div`,{key:`d`,className:`dsh-pm-cprog-panel-sub`},d.description):null,(0,e.createElement)(`div`,{key:`p`,className:`dsh-pm-cprog-sec`},[(0,e.createElement)(`b`,{key:`b`},s?`${x}阶段任务（${C.filter(e=>e.status===`done`).length}/${C.length} 完成）`:`任务（${f}/${p} 完成，${r.progress?.active??0} 进行中）`),...w]),(0,e.createElement)(`div`,{key:`tl`,className:`dsh-pm-cprog-sec`},[(0,e.createElement)(`b`,{key:`b`},s?`${x}阶段时间线`:`状态时间线（最近 8 条）`),...D]),(0,e.createElement)(`div`,{key:`ft`,className:`dsh-pm-cprog-foot`},[s?(0,e.createElement)(`button`,{key:`back`,type:`button`,className:`dsh-pm-btn sm`,onClick:()=>{c(null)}},`← 返回全部`):null,(0,e.createElement)(`button`,{key:`open`,type:`button`,className:`dsh-pm-btn sm`,onClick:()=>{window.dispatchEvent(new CustomEvent(Z,{detail:{open:!0}}))}},`打开项目看板`),(0,e.createElement)(`button`,{key:`rf`,type:`button`,className:`dsh-pm-btn sm`,onClick:()=>{o(!1),c(null)}},`收起`)])]);return(0,e.createElement)(`div`,{className:`dsh-pm-cprog`,ref:l},[y,O])}const Ct=`dsh-pmboard/styles.css`;function wt(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${Ct}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=Ct,e.textContent=`
		/* ---- 侧栏入口（footer-action 同款，保留原类名以兼容既有注入） ---- */
		.dsh-reqboard-foot {
		  display: flex; align-items: center; gap: 8px;
		  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
		  font: inherit; font-size: 13px; cursor: pointer;
		  -webkit-appearance: none; appearance: none;
		}
		.dsh-reqboard-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
		.dsh-reqboard-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
		.dsh-reqboard-foot.wide {
		  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
		  border-radius: 8px; justify-content: flex-start; text-align: left;
		}
		.dsh-reqboard-foot.rail {
		  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
		  justify-content: center; padding: 0;
		}
		.dsh-reqboard-foot-icon { display: inline-flex; flex: none; }
		.dsh-reqboard-foot.rail .dsh-reqboard-foot-label { display: none; }
		.dsh-reqboard-foot-icon svg { width: 16px; height: 16px; }
		
		/* ---- 看板容器：激活时隐藏中心列其他子元素（对齐 taskboard 模式） ---- */
		html[data-dsh-pm-active] [data-pane="conversation"] > *:not([data-dsh-pm-view]),
		html[data-dsh-pm-active] [class*="centerCol"] > *:not([data-dsh-pm-view]),
		html[data-dsh-pm-active] .dshDesktopConversationSurface > *:not([data-dsh-pm-view]) { display: none !important; }
		
		.dsh-pm-view {
		  display: none;
		  flex-direction: column;
		  height: 100%; overflow: hidden;
		}
		html[data-dsh-pm-active] .dsh-pm-view { display: flex; }
		
		/* ---- 通用 ---- */
		.dsh-pm-board { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
		.dsh-pm-head {
		  display: flex; align-items: center; gap: 12px;
		  padding: 12px 20px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.15));
		  flex: none;
		}
		.dsh-pm-title { margin: 0; font-size: 18px; font-weight: 600; color: var(--dsw-text-primary, #222); }
		.dsh-pm-title-sm { font-size: 15px; font-weight: 600; }
		.dsh-pm-rev { font-size: 12px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-hint { font-size: 12px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-btn {
		  padding: 5px 12px; border-radius: 6px; border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
		  background: transparent; color: var(--dsw-text-primary, #333);
		  font-size: 13px; cursor: pointer;
		}
		.dsh-pm-btn:hover { background: var(--dsw-hover, rgba(128,128,128,.1)); }
		.dsh-pm-btn.primary {
		  background: var(--dsw-accent, #4a7dff); color: #fff; border-color: transparent;
		}
		.dsh-pm-btn.primary:hover { opacity: .88; }
		/* 卡片内紧凑尺寸（同色系/同圆角，只缩尺寸） */
		.dsh-pm-btn.sm { padding: 3px 10px; font-size: 12px; border-radius: 6px; }
		.dsh-pm-input {
		  padding: 5px 10px; border-radius: 6px; border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
		  font-size: 13px; background: var(--dsw-bg-primary, #fff); color: inherit;
		}
		.dsh-pm-empty { padding: 32px; text-align: center; color: var(--dsw-text-secondary, #999); font-size: 13px; }
		.dsh-pm-error { padding: 32px; text-align: center; color: #d33; font-size: 13px; }
		
		/* ---- 泳道 ---- */
		.dsh-pm-lanes {
		  display: flex; gap: 12px; padding: 16px 20px;
		  flex: 1; overflow-x: auto; align-items: flex-start;
		}
		.dsh-pm-lane {
		  flex: 1; min-width: 200px; max-width: 280px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.06));
		  border-radius: 10px; padding: 10px;
		  display: flex; flex-direction: column; gap: 8px;
		}
		.dsh-pm-lane-head { display: flex; align-items: center; gap: 6px; padding: 2px 4px 6px; }
		.dsh-pm-lane-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
		.dsh-pm-lane-dot[data-status="draft"] { background: #9aa4b2; }
		.dsh-pm-lane-dot[data-status="brainstorming"] { background: #f0a020; }
		.dsh-pm-lane-dot[data-status="planning"] { background: #c2255c; }
		.dsh-pm-lane-dot[data-status="decomposing"] { background: #8e44ad; }
		.dsh-pm-lane-dot[data-status="implementing"] { background: #4a7dff; }
		.dsh-pm-lane-dot[data-status="accepting"] { background: #17a2b8; }
		.dsh-pm-lane-dot[data-status="done"] { background: #28a745; }
		.dsh-pm-lane-title { font-size: 13px; font-weight: 600; color: var(--dsw-text-primary, #333); }
		.dsh-pm-lane-count { font-size: 12px; color: var(--dsw-text-secondary, #999); margin-left: auto; }
		.dsh-pm-lane-cards { display: flex; flex-direction: column; gap: 8px; min-height: 40px; }
		
		/* ---- 需求卡片 ---- */
		.dsh-pm-card {
		  background: var(--dsw-bg-primary, #fff);
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.15));
		  border-radius: 8px; padding: 10px 12px;
		  cursor: pointer; display: flex; flex-direction: column; gap: 6px;
		}
		.dsh-pm-card:hover { border-color: var(--dsw-accent, #4a7dff); }
		.dsh-pm-card.is-blocked { border-left: 3px solid #d33; }
		.dsh-pm-card-top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
		.dsh-pm-card-id { font-size: 11px; font-family: ui-monospace, monospace; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-cat {
		  font-size: 10px; padding: 1px 6px; border-radius: 4px;
		  background: rgba(74,125,255,.12); color: #4a7dff;
		}
		.dsh-pm-cat[data-cat="bug"] { background: rgba(220,53,69,.12); color: #dc3545; }
		.dsh-pm-cat[data-cat="doc"] { background: rgba(23,162,184,.12); color: #17a2b8; }
		.dsh-pm-flag { font-size: 10px; padding: 1px 6px; border-radius: 4px; }
		.dsh-pm-flag.blocked { background: rgba(220,53,69,.12); color: #dc3545; }
		.dsh-pm-flag.paused { background: rgba(240,160,32,.15); color: #b07800; }
		.dsh-pm-flag.ready { background: rgba(40,167,69,.12); color: #28a745; }
		.dsh-pm-card-title { font-size: 13px; font-weight: 500; color: var(--dsw-text-primary, #222); }
		.dsh-pm-card-progress { display: flex; align-items: center; gap: 8px; }
		.dsh-pm-card-bar { flex: 1; height: 4px; border-radius: 2px; background: rgba(128,128,128,.15); overflow: hidden; }
		.dsh-pm-card-bar-fill { height: 100%; background: var(--dsw-accent, #4a7dff); border-radius: 2px; }
		.dsh-pm-card-pct { font-size: 11px; color: var(--dsw-text-secondary, #999); flex: none; }
		/* 卡面操作行：按钮复用全站 .dsh-pm-btn 体系（与页头「刷新/+需求」、详情页闸门同款），
		   只加紧凑尺寸变体，避免看板内出现第二套按钮视觉。 */
		.dsh-pm-card-actions { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
		
		.dsh-pm-window {
		  display: inline-flex; align-items: center; gap: 3px; padding: 1px 6px; border-radius: 9px;
		  border: 1px solid rgba(74,125,255,.35); background: rgba(74,125,255,.08);
		  color: var(--dsw-accent, #4a7dff); font-size: 11px; cursor: pointer;
		  font-family: ui-monospace, monospace;
		}
		.dsh-pm-window:hover { background: rgba(74,125,255,.16); }
		
		.dsh-pm-session {
		  font-size: 11px; padding: 2px 8px; border-radius: 4px;
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
		  background: transparent; color: var(--dsw-accent, #4a7dff);
		  cursor: pointer; align-self: flex-start;
		}
		.dsh-pm-session:hover { background: rgba(74,125,255,.08); }
		
		/* ---- 归档条 ---- */
		.dsh-pm-archived-bar {
		  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
		  padding: 8px 20px; border-top: 1px solid var(--dsw-border, rgba(128,128,128,.15));
		  flex: none;
		}
		.dsh-pm-archived-label { font-size: 12px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-archived-chip {
		  font-size: 11px; padding: 2px 8px; border-radius: 4px;
		  background: rgba(128,128,128,.1); color: var(--dsw-text-secondary, #777);
		}
		.dsh-pm-archived-chip[data-status="canceled"] { text-decoration: line-through; }
		
		/* ---- 详情 ---- */
		.dsh-pm-detail { display: flex; flex-direction: column; height: 100%; overflow-y: auto; padding: 16px 24px; gap: 16px; }
		.dsh-pm-detail-head { display: flex; align-items: center; gap: 10px; flex: none; flex-wrap: wrap; }
		.dsh-pm-status {
		  font-size: 11px; padding: 2px 10px; border-radius: 10px;
		  background: rgba(128,128,128,.12); color: var(--dsw-text-primary, #444);
		}
		.dsh-pm-status[data-status="implementing"] { background: rgba(74,125,255,.15); color: #4a7dff; }
		.dsh-pm-status[data-status="done"] { background: rgba(40,167,69,.15); color: #28a745; }
		.dsh-pm-status[data-status="accepting"] { background: rgba(23,162,184,.15); color: #17a2b8; }
		.dsh-pm-detail-updated { font-size: 12px; color: var(--dsw-text-secondary, #999); margin-left: auto; }
		.dsh-pm-detail-title { margin: 0; font-size: 20px; font-weight: 600; }
		.dsh-pm-detail-desc { font-size: 14px; color: var(--dsw-text-secondary, #555); white-space: pre-wrap; }
		.dsh-pm-detail-section { display: flex; flex-direction: column; gap: 8px; }
		.dsh-pm-detail-section h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--dsw-text-primary, #333); }
		.dsh-pm-gate {
		  display: flex; align-items: center; gap: 10px;
		  padding: 10px 14px; border-radius: 8px;
		  background: rgba(240,160,32,.1); border: 1px solid rgba(240,160,32,.3);
		  font-size: 13px; color: #8a5a00;
		}
		
		/* ---- DAG ---- */
		.dsh-pm-dag { display: flex; flex-direction: column; gap: 6px; }
		.dsh-pm-dag-layer { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
		.dsh-pm-dag-layer-label { font-size: 11px; color: var(--dsw-text-secondary, #999); width: 24px; flex: none; }
		.dsh-pm-dag-node {
		  font-size: 12px; padding: 4px 10px; border-radius: 6px;
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
		  background: var(--dsw-bg-primary, #fff);
		  cursor: pointer; color: var(--dsw-text-primary, #333);
		}
		.dsh-pm-dag-node:hover { border-color: var(--dsw-accent, #4a7dff); }
		.dsh-pm-dag-node[data-status="done"] { background: rgba(40,167,69,.1); border-color: rgba(40,167,69,.4); }
		.dsh-pm-dag-node[data-status="in_progress"] { background: rgba(74,125,255,.1); border-color: rgba(74,125,255,.4); }
		.dsh-pm-dag-node[data-status="canceled"] { opacity: .5; text-decoration: line-through; }
		
		/* ---- 任务列 ---- */
		.dsh-pm-taskcols { display: flex; gap: 10px; overflow-x: auto; padding-bottom: 8px; }
		.dsh-pm-taskcol {
		  flex: 1; min-width: 160px; max-width: 220px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.06));
		  border-radius: 8px; padding: 8px;
		  display: flex; flex-direction: column; gap: 6px;
		}
		.dsh-pm-taskcol-head { font-size: 12px; font-weight: 600; color: var(--dsw-text-secondary, #666); padding: 2px 4px 4px; }
		.dsh-pm-task {
		  background: var(--dsw-bg-primary, #fff);
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.15));
		  border-radius: 6px; padding: 8px 10px;
		  cursor: pointer; display: flex; flex-direction: column; gap: 4px;
		}
		.dsh-pm-task:hover { border-color: var(--dsw-accent, #4a7dff); }
		.dsh-pm-task-title { font-size: 12px; color: var(--dsw-text-primary, #333); }
		.dsh-pm-task-meta { display: flex; align-items: center; gap: 6px; }
		.dsh-pm-phase { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: rgba(128,128,128,.1); color: var(--dsw-text-secondary, #777); }
		
		/* ---- 任务详情 ---- */
		.dsh-pm-taskdetail { display: flex; flex-direction: column; height: 100%; overflow-y: auto; padding: 16px 24px; gap: 16px; }
		.dsh-pm-kv {
		  display: grid; grid-template-columns: 90px 1fr; gap: 6px 12px;
		  font-size: 13px;
		}
		.dsh-pm-kv > span:nth-child(odd) { color: var(--dsw-text-secondary, #888); }
		.dsh-pm-exec {
		  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
		  padding: 8px 12px; border-radius: 6px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.06));
		  font-size: 12px;
		}
		.dsh-pm-exec-outcome { font-weight: 600; }
		.dsh-pm-exec[data-outcome="succeeded"] .dsh-pm-exec-outcome { color: #28a745; }
		.dsh-pm-exec[data-outcome="failed"] .dsh-pm-exec-outcome { color: #dc3545; }
		.dsh-pm-exec[data-outcome="running"] .dsh-pm-exec-outcome { color: #4a7dff; }
		.dsh-pm-exec-error { width: 100%; color: #dc3545; font-family: ui-monospace, monospace; font-size: 11px; }
		.dsh-pm-exec-evidence { width: 100%; display: flex; gap: 6px; flex-wrap: wrap; }
		.dsh-pm-exec-evidence code {
		  font-size: 11px; padding: 2px 6px; border-radius: 4px;
		  background: rgba(128,128,128,.1); color: var(--dsw-text-secondary, #666);
		}
		
		/* ---- 评论 ---- */
		.dsh-pm-comments { display: flex; flex-direction: column; gap: 8px; }
		.dsh-pm-comment { padding: 8px 12px; border-radius: 6px; background: var(--dsw-bg-secondary, rgba(128,128,128,.05)); }
		.dsh-pm-comment-meta { font-size: 11px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-comment-body { font-size: 13px; color: var(--dsw-text-primary, #333); margin-top: 4px; white-space: pre-wrap; }
		.dsh-pm-comment-form { display: flex; gap: 8px; margin-top: 8px; }
		.dsh-pm-comment-form .dsh-pm-input { flex: 1; }
		
		/* ---- 待归类 ---- */
		.dsh-pm-triage-panel { display: flex; flex-direction: column; gap: 10px; padding: 16px 24px; height: 100%; overflow-y: auto; }
		.dsh-pm-triage {
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.15));
		  border-radius: 8px; padding: 12px 14px;
		  display: flex; flex-direction: column; gap: 8px;
		}
		.dsh-pm-triage-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
		.dsh-pm-session-id { font-size: 11px; font-family: ui-monospace, monospace; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-triage-score { font-size: 11px; padding: 1px 8px; border-radius: 4px; background: rgba(74,125,255,.12); color: #4a7dff; }
		.dsh-pm-triage-suggest { font-size: 12px; color: var(--dsw-text-primary, #444); }
		.dsh-pm-triage-text { font-size: 13px; color: var(--dsw-text-secondary, #555); white-space: pre-wrap; }
		.dsh-pm-triage-edit { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 6px; }
		.dsh-pm-triage-edit .dsh-pm-input[data-role="triage-title"] { flex: 1 1 220px; }
		.dsh-pm-triage-edit .dsh-pm-input[data-role="triage-category"] { flex: 0 0 auto; }
		.dsh-pm-triage-actions { display: flex; gap: 8px; }
		.dsh-pm-rebind-host { display: flex; gap: 8px; margin-top: 8px; }
		
		/* ---- 验收 / 归档区块 ---- */
		.dsh-pm-block {
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.15)); border-radius: 8px;
		  padding: 12px 14px; display: flex; flex-direction: column; gap: 8px;
		}
		.dsh-pm-block.is-empty {
		  font-size: 13px; line-height: 1.6; color: var(--dsw-text-secondary, #888);
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.05)); border-style: dashed;
		}
		.dsh-pm-block.is-empty code {
		  font-family: ui-monospace, monospace; font-size: 12px; padding: 1px 4px;
		  border-radius: 3px; background: rgba(128,128,128,.12);
		}
		.dsh-pm-block-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
		.dsh-pm-block-path {
		  font-family: ui-monospace, monospace; font-size: 12px; color: var(--dsw-text-primary, #444);
		  background: rgba(128,128,128,.1); padding: 2px 6px; border-radius: 4px;
		}
		.dsh-pm-block-summary { font-size: 13px; color: var(--dsw-text-primary, #333); line-height: 1.6; }
		.dsh-pm-block-note { font-size: 12px; color: #dc3545; }
		.dsh-pm-review {
		  font-size: 11px; padding: 2px 10px; border-radius: 10px;
		  background: rgba(128,128,128,.12); color: var(--dsw-text-primary, #444);
		}
		.dsh-pm-review[data-state="pending"] { background: rgba(240,160,32,.15); color: #b07800; }
		.dsh-pm-review[data-state="pass"] { background: rgba(40,167,69,.15); color: #28a745; }
		.dsh-pm-review[data-state="rework"] { background: rgba(220,53,69,.12); color: #dc3545; }
		.dsh-pm-evidence { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
		.dsh-pm-evidence li {
		  font-family: ui-monospace, monospace; font-size: 11px; color: var(--dsw-text-primary, #444);
		  background: rgba(128,128,128,.08); padding: 4px 8px; border-radius: 4px; white-space: pre-wrap;
		}
		.dsh-pm-doc-group { display: flex; flex-direction: column; gap: 4px; }
		.dsh-pm-doc-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
		.dsh-pm-doc-list li { font-size: 12px; display: flex; align-items: center; gap: 8px; }
		.dsh-pm-doc-list code {
		  font-family: ui-monospace, monospace; font-size: 11px; padding: 2px 6px;
		  border-radius: 4px; background: rgba(128,128,128,.1); color: var(--dsw-text-secondary, #666);
		}
		.dsh-pm-doc-kind { font-size: 11px; color: var(--dsw-text-secondary, #888); min-width: 56px; }
		.dsh-pm-flag.verify-pending { background: rgba(23,162,184,.15); color: #17a2b8; }
		.dsh-pm-flag.archive-pending { background: rgba(108,117,125,.15); color: #6c757d; }
		
		/* ---- 实施计划（plan mode） ---- */
		.dsh-pm-plan {
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.15)); border-radius: 8px;
		  padding: 12px 14px; display: flex; flex-direction: column; gap: 10px;
		}
		.dsh-pm-plan.is-empty {
		  font-size: 13px; color: var(--dsw-text-secondary, #888);
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.05));
		  border-style: dashed; line-height: 1.6;
		}
		.dsh-pm-plan.is-empty code {
		  font-family: ui-monospace, monospace; font-size: 12px; padding: 1px 4px;
		  border-radius: 3px; background: rgba(128,128,128,.12);
		}
		.dsh-pm-plan-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
		.dsh-pm-plan-status {
		  font-size: 11px; padding: 2px 10px; border-radius: 10px;
		  background: rgba(128,128,128,.12); color: var(--dsw-text-primary, #444);
		}
		.dsh-pm-plan-status[data-state="pending"] { background: rgba(240,160,32,.15); color: #b07800; }
		.dsh-pm-plan-status[data-state="approved"] { background: rgba(40,167,69,.15); color: #28a745; }
		.dsh-pm-plan-status[data-state="rejected"] { background: rgba(220,53,69,.12); color: #dc3545; }
		.dsh-pm-plan-path {
		  font-family: ui-monospace, monospace; font-size: 12px; color: var(--dsw-text-primary, #444);
		  background: rgba(128,128,128,.1); padding: 2px 6px; border-radius: 4px;
		}
		.dsh-pm-plan-summary { font-size: 13px; color: var(--dsw-text-primary, #333); white-space: pre-wrap; line-height: 1.6; }
		.dsh-pm-plan-reason { font-size: 12px; color: #dc3545; }
		.dsh-pm-plan-tasks { display: flex; flex-direction: column; gap: 4px; }
		.dsh-pm-plan-task {
		  display: grid; grid-template-columns: 52px 1fr auto; gap: 8px; align-items: center;
		  padding: 4px 8px; border-radius: 6px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.05)); font-size: 12px;
		}
		.dsh-pm-plan-key { font-family: ui-monospace, monospace; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-plan-title { color: var(--dsw-text-primary, #333); }
		.dsh-pm-plan-meta { font-size: 11px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-plan-accept { grid-column: 2 / 4; font-size: 11px; color: var(--dsw-text-secondary, #888); }
		.dsh-pm-plan-accept.missing { color: #b07800; }
		.dsh-pm-flag.plan-pending { background: rgba(240,160,32,.15); color: #b07800; }
		.dsh-pm-flag.plan-ok { background: rgba(40,167,69,.12); color: #28a745; }
		.dsh-pm-flag.plan-rejected { background: rgba(220,53,69,.12); color: #dc3545; }
		
		/* ---- 时间线（需求/任务状态事件） ---- */
		.dsh-pm-card-time { font-size: 11px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-timeline { display: flex; flex-direction: column; gap: 4px; }
		.dsh-pm-tl-row {
		  display: grid; grid-template-columns: 60px 92px 108px 96px auto; align-items: center; gap: 10px;
		  padding: 4px 10px; border-radius: 6px; font-size: 12px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.05));
		  border-left: 3px solid transparent;
		}
		.dsh-pm-tl-row.pending { opacity: .45; }
		.dsh-pm-tl-row.current { background: rgba(74,125,255,.08); }
		.dsh-pm-tl-label { font-weight: 600; color: var(--dsw-text-primary, #333); }
		.dsh-pm-tl-time { font-family: ui-monospace, monospace; color: var(--dsw-text-primary, #444); }
		.dsh-pm-tl-dur { color: var(--dsw-text-secondary, #888); }
		.dsh-pm-tl-by { color: var(--dsw-text-secondary, #999); font-size: 11px; }
		.dsh-pm-tl-inferred {
		  font-size: 10px; padding: 1px 6px; border-radius: 4px;
		  background: rgba(240,160,32,.15); color: #b07800; justify-self: start;
		}
		.dsh-pm-tl-total { font-size: 11px; color: var(--dsw-text-secondary, #999); padding-left: 10px; }
		.dsh-pm-tl-row[data-status="draft"], .dsh-pm-tl-row[data-status="todo"] { border-left-color: #9aa4b2; }
		.dsh-pm-tl-row[data-status="brainstorming"], .dsh-pm-tl-row[data-status="testing"] { border-left-color: #f0a020; }
		.dsh-pm-tl-row[data-status="planning"] { border-left-color: #c2255c; }
		.dsh-pm-tl-row[data-status="decomposing"], .dsh-pm-tl-row[data-status="integrating"] { border-left-color: #8e44ad; }
		.dsh-pm-tl-row[data-status="implementing"], .dsh-pm-tl-row[data-status="in_progress"] { border-left-color: #4a7dff; }
		.dsh-pm-tl-row[data-status="accepting"], .dsh-pm-tl-row[data-status="in_review"] { border-left-color: #17a2b8; }
		.dsh-pm-tl-row[data-status="done"] { border-left-color: #28a745; }
		.dsh-pm-tl-row[data-status="archived"] { border-left-color: #6c757d; }
		.dsh-pm-tl-row[data-status="canceled"] { border-left-color: #dc3545; }
		
		/* ---- 甘特图 ---- */
		.dsh-pm-gantt-wrap { width: 100%; overflow-x: auto; }
		.dsh-pm-gantt { display: block; min-width: 620px; }
		.dsh-pm-gantt-grid { stroke: var(--dsw-border, rgba(128,128,128,.15)); stroke-width: 1; }
		.dsh-pm-gantt-axis { font-size: 10px; fill: var(--dsw-text-secondary, #999); }
		.dsh-pm-gantt-mile { stroke: rgba(240,160,32,.55); stroke-width: 1; stroke-dasharray: 3 3; }
		.dsh-pm-gantt-mile[data-status="implementing"] { stroke: rgba(74,125,255,.55); }
		.dsh-pm-gantt-mile[data-status="done"] { stroke: rgba(40,167,69,.55); }
		.dsh-pm-gantt-now { stroke: #dc3545; stroke-width: 1.2; }
		.dsh-pm-gantt-rowlabel { font-size: 11px; fill: var(--dsw-text-primary, #444); }
		.dsh-pm-gantt-track { fill: rgba(128,128,128,.08); }
		.dsh-pm-gantt-bar { fill: #9aa4b2; }
		.dsh-pm-gantt-bar[data-status="todo"] { fill: #9aa4b2; }
		.dsh-pm-gantt-bar[data-status="in_progress"] { fill: #4a7dff; }
		.dsh-pm-gantt-bar[data-status="integrating"] { fill: #8e44ad; }
		.dsh-pm-gantt-bar[data-status="testing"] { fill: #f0a020; }
		.dsh-pm-gantt-bar[data-status="in_review"] { fill: #17a2b8; }
		.dsh-pm-gantt-bar[data-status="done"] { fill: #28a745; }
		.dsh-pm-gantt-bar[data-status="canceled"] { fill: #dc3545; }
		.dsh-pm-gantt-legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; color: var(--dsw-text-secondary, #999); padding-top: 4px; }
		.dsh-pm-gantt-legend-item { display: inline-flex; align-items: center; gap: 4px; }
		.dsh-pm-gantt-legend-item i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; background: #9aa4b2; }
		.dsh-pm-gantt-legend-item i[data-status="in_progress"] { background: #4a7dff; }
		.dsh-pm-gantt-legend-item i[data-status="integrating"] { background: #8e44ad; }
		.dsh-pm-gantt-legend-item i[data-status="testing"] { background: #f0a020; }
		.dsh-pm-gantt-legend-item i[data-status="in_review"] { background: #17a2b8; }
		.dsh-pm-gantt-legend-item i[data-status="done"] { background: #28a745; }
		.dsh-pm-gantt-legend-item i.mile { background: transparent; width: 12px; height: 0; border-top: 2px dashed #f0a020; border-radius: 0; }
		
		/* ---- 任务页 ---- */
		.dsh-pm-tasks-page { padding: 16px 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 18px; }
		.dsh-pm-tasks-group {
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.15)); border-radius: 10px;
		  padding: 12px 14px; display: flex; flex-direction: column; gap: 10px;
		}
		.dsh-pm-tasks-group-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
		.dsh-pm-tasks-group-title { font-size: 14px; font-weight: 600; color: var(--dsw-text-primary, #222); }
		.dsh-pm-section-head { display: flex; align-items: center; gap: 10px; }
		.dsh-pm-strip { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 11px; color: var(--dsw-text-secondary, #888); }
		.dsh-pm-strip-item b { font-family: ui-monospace, monospace; color: var(--dsw-text-primary, #444); font-weight: 500; }
		.dsh-pm-strip-arrow { color: var(--dsw-text-secondary, #bbb); }
		.dsh-pm-ttable { width: 100%; border-collapse: collapse; font-size: 12px; }
		.dsh-pm-ttable th {
		  text-align: left; font-weight: 600; color: var(--dsw-text-secondary, #888);
		  padding: 4px 8px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.15));
		}
		.dsh-pm-ttable td {
		  padding: 5px 8px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		  color: var(--dsw-text-primary, #333);
		}
		.dsh-pm-trow { cursor: pointer; }
		.dsh-pm-trow:hover { background: var(--dsw-hover, rgba(128,128,128,.08)); }
		.dsh-pm-tid { font-family: ui-monospace, monospace; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-tdeps { font-family: ui-monospace, monospace; font-size: 11px; color: var(--dsw-text-secondary, #999); }
		
		/* ---- 节点差异化展示 ---- */
		.dsh-pm-node-badge {
		  display: inline-flex; align-items: center; gap: 4px;
		  padding: 3px 8px; border-radius: 4px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.1));
		  font-size: 12px; color: var(--dsw-text-secondary, #666);
		}
		
		/* 专属内容区域 */
		.dsh-pm-specialized { background: var(--dsw-bg-secondary, rgba(128,128,128,.04)); border-radius: 8px; }
		
		/* 通用信息折叠区 */
		.dsh-pm-common-details { margin-top: 20px; border-top: 1px solid var(--dsw-border, rgba(128,128,128,.15)); padding-top: 16px; }
		.dsh-pm-common-summary {
		  cursor: pointer; font-size: 13px; font-weight: 500;
		  color: var(--dsw-text-secondary, #666);
		  padding: 8px 12px; border-radius: 6px;
		  list-style: none; user-select: none;
		}
		.dsh-pm-common-summary::-webkit-details-marker { display: none; }
		.dsh-pm-common-summary:hover { background: var(--dsw-hover, rgba(128,128,128,.08)); }
		
		/* 统计卡片网格 */
		.dsh-pm-stats {
		  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		  gap: 12px; padding: 12px;
		}
		.dsh-pm-stat {
		  display: flex; flex-direction: column; gap: 4px;
		  padding: 12px; border-radius: 6px;
		  background: var(--dsw-bg-primary, #fff);
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.1));
		}
		.dsh-pm-stat-label { font-size: 11px; color: var(--dsw-text-secondary, #999); text-transform: uppercase; }
		.dsh-pm-stat-value { font-size: 18px; font-weight: 600; color: var(--dsw-text-primary, #222); }
		.dsh-pm-stat-success { border-color: #28a745; }
		.dsh-pm-stat-success .dsh-pm-stat-value { color: #28a745; }
		.dsh-pm-stat-error { border-color: #dc3545; }
		.dsh-pm-stat-error .dsh-pm-stat-value { color: #dc3545; }
		
		/* 拆分节点 - 轨道列表 */
		.dsh-pm-track { margin-bottom: 12px; }
		.dsh-pm-track-head {
		  font-size: 13px; font-weight: 600; color: var(--dsw-text-primary, #333);
		  padding: 8px 12px; background: var(--dsw-bg-secondary, rgba(128,128,128,.08));
		  border-radius: 6px; margin-bottom: 6px;
		}
		.dsh-pm-track-list { list-style: none; padding: 0; margin: 0; }
		.dsh-pm-track-list li {
		  padding: 6px 12px; font-size: 13px; color: var(--dsw-text-primary, #333);
		  border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		}
		.dsh-pm-track-list li:last-child { border-bottom: none; }
		.dsh-pm-task-link {
		  background: none; border: none; color: var(--dsw-accent, #4a7dff);
		  font-family: ui-monospace, monospace; font-size: 12px;
		  cursor: pointer; padding: 0; text-decoration: underline;
		}
		.dsh-pm-task-link:hover { opacity: .8; }
		
		/* 实施节点 - 文件变更 */
		.dsh-pm-file-summary {
		  display: flex; gap: 12px; align-items: center;
		  padding: 8px 12px; margin-bottom: 8px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.06));
		  border-radius: 6px; font-size: 12px;
		}
		.dsh-pm-file-change {
		  display: flex; justify-content: space-between; align-items: center;
		  padding: 6px 12px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		}
		.dsh-pm-file-change:last-child { border-bottom: none; }
		.dsh-pm-file-path {
		  font-family: ui-monospace, monospace; font-size: 12px;
		  color: var(--dsw-text-primary, #333);
		}
		.dsh-pm-file-stats { display: flex; gap: 8px; font-size: 11px; font-weight: 600; }
		.dsh-pm-stat-add { color: #28a745; }
		.dsh-pm-stat-del { color: #dc3545; }
		
		/* 执行记录简报 */
		.dsh-pm-exec-brief {
		  padding: 6px 12px; font-size: 12px;
		  border-left: 3px solid var(--dsw-border, rgba(128,128,128,.2));
		  margin-bottom: 4px;
		}
		
		/* 测试节点 - 失败用例 */
		.dsh-pm-test-fail {
		  padding: 12px; margin-bottom: 8px;
		  border: 1px solid #dc3545; border-radius: 6px;
		  background: rgba(220, 53, 69, .05);
		}
		.dsh-pm-test-fail-name {
		  font-size: 13px; font-weight: 600; color: #dc3545;
		  margin-bottom: 6px;
		}
		.dsh-pm-test-fail-detail {
		  display: flex; flex-direction: column; gap: 4px;
		  font-size: 12px; color: var(--dsw-text-primary, #333);
		}
		.dsh-pm-test-fail-detail code {
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.1));
		  padding: 2px 6px; border-radius: 3px;
		  font-family: ui-monospace, monospace; font-size: 11px;
		}
		
		/* 测试节点 - 覆盖率 */
		.dsh-pm-coverage { display: flex; flex-direction: column; gap: 12px; }
		.dsh-pm-coverage-bar { display: flex; flex-direction: column; gap: 4px; }
		.dsh-pm-coverage-label {
		  font-size: 12px; color: var(--dsw-text-secondary, #666);
		  display: inline-block; min-width: 100px;
		}
		.dsh-pm-coverage-value {
		  font-size: 14px; font-weight: 600; color: var(--dsw-text-primary, #333);
		  margin-left: auto;
		}
		.dsh-pm-coverage-track {
		  height: 8px; background: var(--dsw-bg-secondary, rgba(128,128,128,.15));
		  border-radius: 4px; overflow: hidden; position: relative;
		}
		.dsh-pm-coverage-fill {
		  height: 100%; background: linear-gradient(90deg, #28a745, #20c997);
		  transition: width .3s ease;
		}
		
		/* 评审节点 - 评审结果 */
		.dsh-pm-review-status { display: flex; gap: 12px; padding: 12px; }
		.dsh-pm-review-status[data-status="approved"] {
		  background: rgba(40, 167, 69, .1); border: 1px solid #28a745; border-radius: 6px;
		}
		.dsh-pm-review-status[data-status="pending"] {
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.06));
		}
		.dsh-pm-review-list {
		  list-style: none; padding: 0; margin: 0;
		}
		.dsh-pm-review-list li {
		  padding: 8px 12px; font-size: 13px;
		  border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		}
		.dsh-pm-review-list li:last-child { border-bottom: none; }
		.dsh-pm-review-pass {
		  color: #28a745; display: flex; align-items: center; gap: 6px;
		}
		.dsh-pm-review-pass::before { content: '✓'; font-weight: bold; }
		
		/* 评审节点 - 改进建议 */
		.dsh-pm-suggestions { display: flex; flex-direction: column; gap: 12px; }
		.dsh-pm-suggestion {
		  padding: 12px; border-radius: 6px;
		  border-left: 4px solid var(--dsw-border, rgba(128,128,128,.3));
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.04));
		}
		.dsh-pm-suggestion[data-severity="high"] { border-left-color: #dc3545; background: rgba(220, 53, 69, .05); }
		.dsh-pm-suggestion[data-severity="medium"] { border-left-color: #f0a020; background: rgba(240, 160, 32, .05); }
		.dsh-pm-suggestion[data-severity="low"] { border-left-color: #17a2b8; background: rgba(23, 162, 184, .05); }
		.dsh-pm-suggestion-head {
		  display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
		}
		.dsh-pm-suggestion-num {
		  width: 24px; height: 24px; border-radius: 50%;
		  background: var(--dsw-accent, #4a7dff); color: #fff;
		  display: flex; align-items: center; justify-content: center;
		  font-size: 11px; font-weight: 600; flex: none;
		}
		.dsh-pm-severity-badge {
		  padding: 2px 8px; border-radius: 12px;
		  font-size: 11px; color: #fff; font-weight: 500;
		  margin-left: auto;
		}
		.dsh-pm-suggestion-body {
		  font-size: 13px; color: var(--dsw-text-primary, #333);
		  padding-left: 32px;
		}
		
		/* 合并节点 - 合并状态 */
		.dsh-pm-merge-header {
		  display: flex; justify-content: space-between; align-items: center;
		  padding: 12px; margin-bottom: 12px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.06));
		  border-radius: 6px;
		}
		.dsh-pm-merge-branch {
		  display: flex; align-items: center; gap: 8px;
		  font-family: ui-monospace, monospace; font-size: 13px;
		}
		.dsh-pm-merge-branch code {
		  background: var(--dsw-bg-primary, #fff);
		  padding: 4px 8px; border-radius: 4px;
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.2));
		}
		.dsh-pm-merge-arrow { color: var(--dsw-text-secondary, #999); font-weight: bold; }
		.dsh-pm-merge-status {
		  font-size: 14px; font-weight: 600;
		  padding: 4px 12px; border-radius: 6px;
		  background: var(--dsw-bg-primary, #fff);
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.2));
		}
		
		/* 合并节点 - 冲突列表 */
		.dsh-pm-conflicts { display: flex; flex-direction: column; gap: 12px; }
		.dsh-pm-conflict {
		  display: flex; gap: 12px; padding: 12px;
		  border: 1px solid #f0a020; border-radius: 6px;
		  background: rgba(240, 160, 32, .05);
		}
		.dsh-pm-conflict-num {
		  width: 24px; height: 24px; border-radius: 50%;
		  background: #f0a020; color: #fff;
		  display: flex; align-items: center; justify-content: center;
		  font-size: 12px; font-weight: 600; flex: none;
		}
		.dsh-pm-conflict-body { flex: 1; display: flex; flex-direction: column; gap: 4px; }
		.dsh-pm-conflict-desc { font-size: 13px; color: var(--dsw-text-primary, #333); }
		.dsh-pm-conflict-resolution {
		  font-size: 12px; color: var(--dsw-text-secondary, #666);
		  font-style: italic;
		}
		
		/* 合并节点 - CI 检查 */
		.dsh-pm-ci-checks { display: flex; flex-direction: column; gap: 8px; }
		.dsh-pm-ci-check {
		  display: flex; align-items: center; gap: 8px;
		  padding: 8px 12px; border-radius: 6px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.04));
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.15));
		}
		.dsh-pm-ci-check[data-status="pass"] { border-color: #28a745; background: rgba(40, 167, 69, .05); }
		.dsh-pm-ci-check[data-status="fail"] { border-color: #dc3545; background: rgba(220, 53, 69, .05); }
		.dsh-pm-ci-icon { font-size: 16px; flex: none; }
		.dsh-pm-ci-name {
		  font-size: 13px; font-weight: 500; color: var(--dsw-text-primary, #333);
		  flex: none; min-width: 120px;
		}
		.dsh-pm-ci-details {
		  font-size: 12px; color: var(--dsw-text-secondary, #666);
		  font-family: ui-monospace, monospace;
		}
		
		/* 文档节点 - 文档列表 */
		.dsh-pm-doc-list {
		  list-style: none; padding: 0; margin: 0;
		}
		.dsh-pm-doc-list li {
		  padding: 8px 12px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		}
		.dsh-pm-doc-list li:last-child { border-bottom: none; }
		
		/* 文档节点 - API 列表 */
		.dsh-pm-api-list {
		  list-style: none; padding: 0; margin: 0;
		}
		.dsh-pm-api-list li {
		  padding: 8px 12px; display: flex; align-items: center; gap: 8px;
		  border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		}
		.dsh-pm-api-list li:last-child { border-bottom: none; }
		.dsh-pm-api-method {
		  padding: 2px 6px; border-radius: 4px;
		  font-size: 11px; font-weight: 600; color: #fff;
		  font-family: ui-monospace, monospace;
		}
		.dsh-pm-api-method[data-method="GET"] { background: #28a745; }
		.dsh-pm-api-method[data-method="POST"] { background: #4a7dff; }
		.dsh-pm-api-method[data-method="PUT"] { background: #f0a020; }
		.dsh-pm-api-method[data-method="DELETE"] { background: #dc3545; }
		.dsh-pm-api-method[data-method="PATCH"] { background: #8e44ad; }
		
		/* 文档节点 - 完成度 */
		.dsh-pm-completeness { display: flex; flex-direction: column; gap: 8px; }
		.dsh-pm-completeness-bar { display: flex; flex-direction: column; gap: 4px; }
		.dsh-pm-completeness-label {
		  font-size: 12px; color: var(--dsw-text-secondary, #666);
		}
		.dsh-pm-completeness-value {
		  font-size: 16px; font-weight: 600; color: var(--dsw-text-primary, #333);
		}
		.dsh-pm-completeness-track {
		  height: 10px; background: var(--dsw-bg-secondary, rgba(128,128,128,.15));
		  border-radius: 5px; overflow: hidden;
		}
		.dsh-pm-completeness-fill {
		  height: 100%; background: linear-gradient(90deg, #4a7dff, #17a2b8);
		  transition: width .3s ease;
		}
		.dsh-pm-completeness-detail {
		  font-size: 12px; color: var(--dsw-text-secondary, #666);
		  text-align: center;
		}
		
		/* UI 节点 - 设计列表 */
		.dsh-pm-design-list {
		  list-style: none; padding: 0; margin: 0;
		}
		.dsh-pm-design-list li {
		  padding: 8px 12px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		}
		.dsh-pm-design-list li:last-child { border-bottom: none; }
		
		/* UI 节点 - 组件列表 */
		.dsh-pm-component-list {
		  list-style: none; padding: 0; margin: 0;
		  display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
		  gap: 8px;
		}
		.dsh-pm-component-list li {
		  padding: 8px 12px; background: var(--dsw-bg-secondary, rgba(128,128,128,.06));
		  border-radius: 6px; font-size: 13px; text-align: center;
		}
		
		/* 分析节点 - 方案对比 */
		.dsh-pm-options { display: flex; flex-direction: column; gap: 8px; }
		.dsh-pm-option {
		  display: flex; justify-content: space-between; align-items: center;
		  padding: 10px 12px; background: var(--dsw-bg-secondary, rgba(128,128,128,.06));
		  border-radius: 6px;
		}
		.dsh-pm-option-name {
		  font-size: 14px; font-weight: 500; color: var(--dsw-text-primary, #333);
		}
		.dsh-pm-option-score {
		  font-size: 16px; color: #f0a020;
		}
		
		/* 分析节点 - 推荐方案 */
		.dsh-pm-recommendation {
		  padding: 16px; background: rgba(40, 167, 69, .1);
		  border: 2px solid #28a745; border-radius: 8px;
		}
		.dsh-pm-recommendation-title {
		  font-size: 16px; font-weight: 600; color: #28a745;
		}
		
		/* 分析节点 - 风险列表 */
		.dsh-pm-risk-list {
		  list-style: none; padding: 0; margin: 0;
		}
		.dsh-pm-risk-list li {
		  padding: 10px 12px; border-left: 4px solid #f0a020;
		  background: rgba(240, 160, 32, .05); margin-bottom: 8px;
		  border-radius: 4px; font-size: 13px;
		}
		.dsh-pm-risk-list li::before {
		  content: '⚠️ '; margin-right: 4px;
		}
		
		/* 分析节点 - 参考资料 */
		.dsh-pm-reference-list {
		  list-style: none; padding: 0; margin: 0;
		}
		.dsh-pm-reference-list li {
		  padding: 8px 12px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		}
		.dsh-pm-reference-list li:last-child { border-bottom: none; }
		.dsh-pm-reference-list a {
		  color: var(--dsw-accent, #4a7dff); text-decoration: none;
		  font-family: ui-monospace, monospace; font-size: 12px;
		}
		.dsh-pm-reference-list a:hover {
		  text-decoration: underline;
		}
		
		/* ---- 需求详情：进度条 + 可折叠 section（监控优先） ---- */
		.dsh-pm-req-progress {
		  display: flex; align-items: center; gap: 12px;
		  padding: 12px 16px; border-radius: 8px;
		  background: var(--dsw-bg-secondary, #f7f8fa);
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.12));
		}
		.dsh-pm-progress-bar {
		  flex: 1; height: 10px; border-radius: 5px; overflow: hidden;
		  background: rgba(128,128,128,.15);
		}
		.dsh-pm-progress-fill {
		  height: 100%; border-radius: 5px;
		  background: linear-gradient(90deg, #4a7dff 0%, #2563eb 100%);
		  transition: width .3s ease;
		}
		.dsh-pm-progress-fill.full { background: linear-gradient(90deg, #28a745 0%, #20c997 100%); }
		.dsh-pm-progress-text {
		  font-size: 13px; color: var(--dsw-text-secondary, #777); white-space: nowrap;
		  display: flex; align-items: baseline; gap: 6px;
		}
		.dsh-pm-progress-text b { font-size: 15px; font-weight: 600; color: var(--dsw-text-primary, #333); }
		.dsh-pm-progress-text .dsh-pm-progress-pct { font-weight: 600; color: #4a7dff; }
		
		/* details 折叠 section（勿给 <details> 设 display:flex，会破坏原生折叠机制） */
		.dsh-pm-detail details.dsh-pm-fold {
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.12));
		  border-radius: 8px;
		  background: var(--dsw-bg-primary, #fff);
		}
		.dsh-pm-detail details.dsh-pm-fold summary {
		  list-style: none; cursor: pointer; user-select: none;
		  display: flex; align-items: center; gap: 8px;
		  padding: 11px 14px; font-size: 14px; font-weight: 600;
		  color: var(--dsw-text-primary, #333);
		  background: var(--dsw-bg-secondary, #f7f8fa);
		  transition: background .15s ease;
		  border-radius: 8px;
		}
		.dsh-pm-detail details.dsh-pm-fold summary::-webkit-details-marker { display: none; }
		.dsh-pm-detail details.dsh-pm-fold summary::before {
		  content: '▸'; font-size: 12px; color: var(--dsw-text-secondary, #999);
		  transition: transform .15s ease;
		}
		.dsh-pm-detail details.dsh-pm-fold[open] summary::before { transform: rotate(90deg); }
		.dsh-pm-detail details.dsh-pm-fold[open] summary { border-radius: 8px 8px 0 0; }
		.dsh-pm-detail details.dsh-pm-fold summary:hover { background: var(--dsw-hover, #eef1f5); }
		.dsh-pm-detail details.dsh-pm-fold .dsh-pm-fold-body {
		  padding: 12px 14px;
		  border-top: 1px solid var(--dsw-border, rgba(128,128,128,.08));
		}
		
		.dsh-pm-detail details.dsh-pm-fold .dsh-pm-fold-count {
		  font-size: 12px; font-weight: 500; color: var(--dsw-text-secondary, #999);
		  margin-left: auto;
		}
		
		/* ---- Markdown 内容 ---- */
		.dsh-pm-markdown { font-size: 14px; line-height: 1.65; color: var(--dsw-text-secondary, #555); word-break: break-word; }
		.dsh-pm-markdown p { margin: 0 0 8px; }
		.dsh-pm-markdown p:last-child { margin-bottom: 0; }
		.dsh-pm-markdown h1, .dsh-pm-markdown h2, .dsh-pm-markdown h3,
		.dsh-pm-markdown h4, .dsh-pm-markdown h5, .dsh-pm-markdown h6 {
		  margin: 14px 0 6px; color: var(--dsw-text-primary, #333); font-weight: 600; line-height: 1.3;
		}
		.dsh-pm-markdown h1 { font-size: 19px; }
		.dsh-pm-markdown h2 { font-size: 17px; }
		.dsh-pm-markdown h3 { font-size: 15px; }
		.dsh-pm-markdown h4, .dsh-pm-markdown h5, .dsh-pm-markdown h6 { font-size: 14px; }
		.dsh-pm-markdown ul, .dsh-pm-markdown ol { margin: 0 0 8px; padding-left: 22px; }
		.dsh-pm-markdown li { margin: 3px 0; }
		.dsh-pm-markdown li::marker { color: var(--dsw-text-secondary, #999); }
		.dsh-pm-markdown code {
		  background: rgba(128,128,128,.12); padding: 1px 6px; border-radius: 3px;
		  font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12.5px;
		  color: #c7254e;
		}
		.dsh-pm-markdown pre {
		  background: rgba(128,128,128,.07); padding: 10px 12px; border-radius: 6px;
		  overflow-x: auto; margin: 8px 0; line-height: 1.5;
		}
		.dsh-pm-markdown pre code { background: none; padding: 0; color: var(--dsw-text-primary, #333); font-size: 12.5px; }
		.dsh-pm-markdown a { color: var(--dsw-accent, #4a7dff); text-decoration: none; }
		.dsh-pm-markdown a:hover { text-decoration: underline; }
		.dsh-pm-markdown strong { font-weight: 600; color: var(--dsw-text-primary, #333); }
		.dsh-pm-markdown em { font-style: italic; }
		.dsh-pm-markdown blockquote {
		  margin: 8px 0; padding: 4px 12px; border-left: 3px solid var(--dsw-border, rgba(128,128,128,.3));
		  color: var(--dsw-text-secondary, #777);
		}
		.dsh-pm-markdown hr { border: none; border-top: 1px solid var(--dsw-border, rgba(128,128,128,.15)); margin: 12px 0; }
		.dsh-pm-detail-title { margin: 0 0 8px; font-size: 18px; font-weight: 600; color: var(--dsw-text-primary, #333); }
		
		/* ---- 需求详情：文档记录区块 ---- */
		.dsh-pm-doc-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
		.dsh-pm-doc-list li { display: flex; align-items: center; gap: 8px; font-size: 13px; line-height: 1.5; }
		.dsh-pm-doc-icon { font-size: 14px; flex: none; }
		.dsh-pm-doc-label { font-size: 12px; color: var(--dsw-text-secondary, #777); min-width: 64px; flex: none; }
		.dsh-pm-doc-path {
		  font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px;
		  padding: 2px 6px; border-radius: 4px; background: rgba(128,128,128,.1);
		  color: var(--dsw-accent, #4a7dff); text-decoration: none; word-break: break-all;
		  transition: background .15s ease;
		  border: none; cursor: pointer; text-align: left;
		}
		.dsh-pm-doc-path:hover { background: rgba(74,125,255,.12); text-decoration: underline; }
		
		/* ---- 文档查看弹窗 ---- */
		.dsh-pm-doc-modal-overlay {
		  position: fixed; inset: 0; z-index: 9999;
		  background: rgba(0,0,0,.3);
		}
		.dsh-pm-doc-modal {
		  position: absolute; top: 0; right: 0; bottom: 0;
		  width: min(720px, 82vw); height: 100%;
		  border-radius: 0;
		  background: var(--dsw-bg-primary, #fff);
		  box-shadow: -6px 0 32px rgba(0,0,0,.18);
		  display: flex; flex-direction: column; overflow: hidden;
		}
		.dsh-pm-doc-modal-head {
		  display: flex; align-items: center; justify-content: space-between; gap: 12px;
		  padding: 12px 16px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.12));
		}
		.dsh-pm-doc-modal-title {
		  font-family: ui-monospace, monospace; font-size: 13px;
		  color: var(--dsw-text-primary, #333); word-break: break-all;
		}
		.dsh-pm-doc-modal-body {
		  padding: 16px; overflow: auto; flex: 1;
		}
		.dsh-pm-doc-modal-body pre {
		  margin: 0; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 13px;
		  line-height: 1.6; white-space: pre-wrap; word-break: break-word;
		  color: var(--dsw-text-primary, #333);
		}
		
		/* ---- 文档缺失标注（未落盘/路径错误） ---- */
		.dsh-pm-doc-list li.is-missing .dsh-pm-doc-icon,
		.dsh-pm-doc-list li.is-missing .dsh-pm-doc-label { opacity: .5; }
		.dsh-pm-doc-list li.is-missing .dsh-pm-doc-path {
		  color: var(--dsw-text-secondary, #999);
		  text-decoration: line-through;
		  cursor: not-allowed;
		  background: rgba(128,128,128,.05);
		}
		.dsh-pm-doc-list li.is-missing .dsh-pm-doc-path:hover { background: rgba(128,128,128,.05); text-decoration: line-through; }
		
		/* ---- 视图切换（泳道 / 列表）---- */
		.dsh-pm-viewswitch {
		  display: inline-flex; margin-left: auto; border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
		  border-radius: 8px; overflow: hidden;
		}
		.dsh-pm-viewbtn {
		  border: none; background: transparent; color: var(--dsw-text-secondary, #888);
		  font: inherit; font-size: 12px; padding: 5px 14px; cursor: pointer;
		}
		.dsh-pm-viewbtn + .dsh-pm-viewbtn { border-left: 1px solid var(--dsw-border, rgba(128,128,128,.2)); }
		.dsh-pm-viewbtn:hover { background: var(--dsw-hover, rgba(128,128,128,.1)); color: var(--dsw-text-primary, #333); }
		.dsh-pm-viewbtn.active { background: var(--dsw-text-primary, #333); color: var(--dsw-bg, #fff); }
		
		/* ---- 列表视图 ---- */
		.dsh-pm-list {
		  padding: 14px 20px 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px;
		}
		.dsh-pm-list-empty { padding: 48px 0; text-align: center; color: var(--dsw-text-secondary, #999); font-size: 13px; }
		.dsh-pm-list-card {
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.18)); border-radius: 10px;
		  padding: 12px 14px; display: flex; flex-direction: column; gap: 8px;
		  background: var(--dsw-bg, transparent); transition: border-color .15s, box-shadow .15s;
		}
		.dsh-pm-list-card:hover { border-color: rgba(74,125,255,.45); box-shadow: 0 2px 10px rgba(74,125,255,.10); }
		.dsh-pm-list-card.is-blocked { border-left: 3px solid #dc3545; }
		.dsh-pm-list-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
		.dsh-pm-list-when { margin-left: auto; font-size: 11px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-status-badge {
		  font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600;
		  background: rgba(128,128,128,.15); color: var(--dsw-text-primary, #444);
		}
		.dsh-pm-status-badge[data-status="implementing"] { background: rgba(74,125,255,.18); color: #2f5fd0; }
		.dsh-pm-status-badge[data-status="accepting"] { background: rgba(23,162,184,.18); color: #0e7c8f; }
		.dsh-pm-status-badge[data-status="done"] { background: rgba(40,167,69,.18); color: #1e7e34; }
		.dsh-pm-status-badge[data-status="planning"] { background: rgba(240,160,32,.20); color: #a86a00; }
		.dsh-pm-status-badge[data-status="brainstorming"] { background: rgba(142,68,173,.18); color: #6f2f8c; }
		.dsh-pm-list-title {
		  font-size: 14px; font-weight: 600; color: var(--dsw-text-primary, #222);
		  cursor: pointer; line-height: 1.4;
		}
		.dsh-pm-list-title:hover { text-decoration: underline; }
		.dsh-pm-list-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 11px; color: var(--dsw-text-secondary, #888); }
		.dsh-pm-list-window-label { opacity: .75; }
		.dsh-pm-list-seps { opacity: .4; }
		.dsh-pm-list-nowindow { opacity: .7; }
		.dsh-pm-list-strip { display: inline-flex; gap: 4px; flex-wrap: wrap; }
		.dsh-pm-list-seg {
		  padding: 1px 6px; border-radius: 4px; background: rgba(128,128,128,.12); font-size: 10px;
		}
		.dsh-pm-list-seg[data-status="in_progress"] { background: rgba(74,125,255,.16); color: #2f5fd0; }
		.dsh-pm-list-seg[data-status="integrating"] { background: rgba(142,68,173,.16); color: #6f2f8c; }
		.dsh-pm-list-seg[data-status="testing"] { background: rgba(240,160,32,.18); color: #a86a00; }
		.dsh-pm-list-seg[data-status="in_review"] { background: rgba(23,162,184,.16); color: #0e7c8f; }
		.dsh-pm-list-seg[data-status="done"] { background: rgba(40,167,69,.16); color: #1e7e34; }
		.dsh-pm-list-strip-empty { opacity: .7; }
		.dsh-pm-list-progress { display: flex; align-items: center; gap: 10px; }
		.dsh-pm-list-progress .dsh-pm-card-bar { flex: 1; }
		.dsh-pm-list-pct { font-size: 11px; color: var(--dsw-text-secondary, #888); white-space: nowrap; }
		.dsh-pm-list-actions { display: flex; gap: 8px; }
		
		/* ---- 列表工具条（排序 / 每页 / 计数）---- */
		.dsh-pm-list-toolbar {
		  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
		  padding: 2px 0 6px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.14));
		}
		.dsh-pm-list-toolbar-label { font-size: 11px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-list-toolbar-gap { flex: 1; }
		.dsh-pm-sortbtn {
		  border: 1px solid transparent; background: transparent;
		  color: var(--dsw-text-secondary, #888); font: inherit; font-size: 12px;
		  padding: 3px 9px; border-radius: 999px; cursor: pointer; white-space: nowrap;
		}
		.dsh-pm-sortbtn:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, #333); }
		.dsh-pm-sortbtn.active {
		  background: rgba(74,125,255,.14); color: #2f5fd0;
		  border-color: rgba(74,125,255,.35); font-weight: 600;
		}
		.dsh-pm-pagesize {
		  font: inherit; font-size: 12px; padding: 2px 6px; border-radius: 6px;
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.28));
		  background: var(--dsw-bg, transparent); color: var(--dsw-text-primary, #333); cursor: pointer;
		}
		.dsh-pm-list-count { font-size: 11px; color: var(--dsw-text-secondary, #999); font-variant-numeric: tabular-nums; }
		
		/* 分组标题：进行中 / 已完成（已完成恒在下方） */
		.dsh-pm-list-grouphead {
		  font-size: 11px; font-weight: 600; color: var(--dsw-text-secondary, #999);
		  padding: 6px 2px 0; letter-spacing: .3px;
		}
		.dsh-pm-list-grouphead[data-group="done"] {
		  margin-top: 8px; padding-top: 10px;
		  border-top: 1px dashed var(--dsw-border, rgba(128,128,128,.22));
		}
		
		/* ---- 分页（page-kit renderPagination 的 tpg-* 类）---- */
		.dsh-pm-pager {
		  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
		  padding: 14px 2px 4px;
		}
		.dsh-pm-pager .tpg-arr, .dsh-pm-pager .tpg-num {
		  min-width: 30px; height: 28px; padding: 0 9px; border-radius: 6px;
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.28));
		  background: transparent; color: var(--dsw-text-primary, #444);
		  font: inherit; font-size: 12px; cursor: pointer;
		}
		.dsh-pm-pager .tpg-arr:hover:not(:disabled), .dsh-pm-pager .tpg-num:hover {
		  border-color: #4a7dff; color: #4a7dff;
		}
		.dsh-pm-pager .tpg-arr:disabled { opacity: .45; cursor: not-allowed; }
		.dsh-pm-pager .tpg-num.act { background: #4a7dff; border-color: #4a7dff; color: #fff; font-weight: 600; }
		.dsh-pm-pager .tpg-nums { display: inline-flex; gap: 4px; align-items: center; }
		.dsh-pm-pager .tpg-gap { color: var(--dsw-text-secondary, #aaa); padding: 0 2px; }
		.dsh-pm-pager .tpg-cnt {
		  margin-left: auto; font-size: 11px; color: var(--dsw-text-secondary, #999);
		  white-space: nowrap; font-variant-numeric: tabular-nums;
		}
		
		/* ---- 会话顶部需求进度（conversation.session.header.utilities 槽位）---- */
		.dsh-pm-cprog { position: relative; display: inline-flex; align-items: center; flex-direction: column; gap: 8px; }
		
		/* 内联流程图（始终可见，位于模式选择器后） */
		.dsh-pm-cprog-inline {
		  display: inline-flex; align-items: center; gap: 10px;
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.25)); border-radius: 12px;
		  background: var(--dsw-bg-secondary, rgba(128,128,128,.05));
		  padding: 6px 12px; cursor: pointer; transition: all .2s ease;
		}
		.dsh-pm-cprog-inline:hover {
		  background: var(--dsw-hover, rgba(128,128,128,.12));
		  border-color: rgba(74,125,255,.4);
		  box-shadow: 0 2px 8px rgba(74,125,255,.1);
		}
		.dsh-pm-cprog-inline-count {
		  font-size: 11px; color: var(--dsw-text-secondary, #666);
		  font-variant-numeric: tabular-nums; font-weight: 500;
		  padding-left: 6px; border-left: 1px solid var(--dsw-border, rgba(128,128,128,.2));
		}
		.dsh-pm-cprog-inline.is-closed { opacity: .75; }
		
		/* 详情面板（点击流程图展开） */
		.dsh-pm-cprog-detail-panel {
		  position: absolute; top: calc(100% + 8px); right: 0; z-index: 60;
		  width: 420px; max-height: 68vh; overflow-y: auto;
		  background: var(--dsw-bg, #fff); border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
		  border-radius: 10px; box-shadow: 0 8px 28px rgba(0,0,0,.18); padding: 12px 14px;
		  display: flex; flex-direction: column; gap: 10px; text-align: left;
		}
		
		.dsh-pm-cprog-trigger {
		  display: inline-flex; align-items: center; gap: 8px; max-width: 340px;
		  border: 1px solid var(--dsw-border, rgba(128,128,128,.25)); border-radius: 999px;
		  background: transparent; color: var(--dsw-text-secondary, #666); font: inherit; font-size: 12px;
		  padding: 3px 10px; cursor: pointer; white-space: nowrap;
		}
		.dsh-pm-cprog-trigger:hover { background: var(--dsw-hover, rgba(128,128,128,.1)); color: var(--dsw-text-primary, #333); }
		.dsh-pm-cprog-ico { font-size: 11px; opacity: .85; }
		.dsh-pm-cprog-name { max-width: 150px; overflow: hidden; text-overflow: ellipsis; }
		.dsh-pm-cprog-mini {
		  width: 46px; height: 5px; border-radius: 3px; overflow: hidden;
		  background: rgba(128,128,128,.22); flex: none;
		}
		.dsh-pm-cprog-mini > i { display: block; height: 100%; background: linear-gradient(90deg,#4a7dff,#8e44ad); }
		.dsh-pm-cprog-count { font-size: 11px; opacity: .85; font-variant-numeric: tabular-nums; }
		/* 已归档会话的窗口按钮：置灰、不可点（.is-archived 不带 data-action） */
		.dsh-pm-window.is-archived,
		.dsh-pm-session.is-archived {
		  opacity: .5; cursor: default;
		  background: var(--dsw-hover, rgba(128,128,128,.10));
		  color: var(--dsw-text-secondary, #999);
		}
		.dsh-pm-window.is-archived:hover,
		.dsh-pm-session.is-archived:hover {
		  background: var(--dsw-hover, rgba(128,128,128,.10));
		  color: var(--dsw-text-secondary, #999);
		}
		.dsh-pm-cprog-trigger.is-closed { opacity: .78; }
		.dsh-pm-cprog-trigger.is-closed .dsh-pm-cprog-name { font-weight: 400; }
		.dsh-pm-cprog-panel-note {
		  font-size: 11px; line-height: 1.5; color: var(--dsw-text-secondary, #888);
		  background: rgba(128,128,128,.10); border-radius: 6px; padding: 6px 8px;
		}
		
		.dsh-pm-cprog-panel {
		  position: absolute; top: calc(100% + 8px); right: 0; z-index: 60;
		  width: 380px; max-height: 62vh; overflow-y: auto;
		  background: var(--dsw-bg, #fff); border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
		  border-radius: 10px; box-shadow: 0 8px 28px rgba(0,0,0,.18); padding: 12px 14px;
		  display: flex; flex-direction: column; gap: 10px; text-align: left;
		}
		.dsh-pm-cprog-panel-head { display: flex; align-items: center; gap: 8px; }
		.dsh-pm-cprog-panel-title { font-size: 13px; font-weight: 600; color: var(--dsw-text-primary, #222); }
		.dsh-pm-cprog-panel-sub { font-size: 11px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-cprog-sec { display: flex; flex-direction: column; gap: 6px; }
		.dsh-pm-cprog-sec > b { font-size: 11px; color: var(--dsw-text-secondary, #888); font-weight: 600; }
		
		/* 流程图（纵向时间线）*/
		.dsh-pm-flow { display: flex; align-items: stretch; gap: 0; overflow-x: auto; padding: 2px 0; }
		.dsh-pm-flow-node { display: flex; flex-direction: column; align-items: center; gap: 3px; min-width: 56px; cursor: pointer; transition: all .2s ease; }
		.dsh-pm-flow-node:hover { transform: translateY(-2px); }
		.dsh-pm-flow-node[data-selected="true"] .dsh-pm-flow-dot {
		  box-shadow: 0 0 0 3px rgba(74,125,255,.3);
		  transform: scale(1.1);
		}
		.dsh-pm-flow-node[data-selected="true"] .dsh-pm-flow-label {
		  font-weight: 700;
		  color: #2f5fd0;
		}
		.dsh-pm-flow-dot {
		  width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
		  font-size: 11px; background: rgba(128,128,128,.18); color: var(--dsw-text-secondary, #888); border: none;
		  transition: all .2s ease;
		}
		.dsh-pm-flow-node[data-state="done"] .dsh-pm-flow-dot { background: rgba(40,167,69,.9); color: #fff; }
		.dsh-pm-flow-node[data-state="current"] .dsh-pm-flow-dot { background: #4a7dff; color: #fff; box-shadow: 0 0 0 3px rgba(74,125,255,.25); }
		.dsh-pm-flow-label { font-size: 10px; color: var(--dsw-text-secondary, #999); white-space: nowrap; transition: all .2s ease; }
		.dsh-pm-flow-node[data-state="done"] .dsh-pm-flow-label { color: #1e7e34; }
		.dsh-pm-flow-node[data-state="current"] .dsh-pm-flow-label { color: #2f5fd0; font-weight: 600; }
		.dsh-pm-flow-link { width: 14px; height: 2px; background: rgba(128,128,128,.22); margin-top: 9px; flex: none; }
		.dsh-pm-flow-link[data-state="done"] { background: rgba(40,167,69,.55); }
		
		.dsh-pm-cprog-task { display: flex; align-items: flex-start; gap: 7px; font-size: 12px; line-height: 1.45; }
		.dsh-pm-cprog-task-ico { flex: none; }
		.dsh-pm-cprog-task-body { min-width: 0; }
		.dsh-pm-cprog-task-title { color: var(--dsw-text-primary, #333); }
		.dsh-pm-cprog-task[data-status="done"] .dsh-pm-cprog-task-title { color: var(--dsw-text-secondary, #999); text-decoration: line-through; }
		.dsh-pm-cprog-task-meta { font-size: 10px; color: var(--dsw-text-secondary, #aaa); }
		.dsh-pm-cprog-tl { display: flex; flex-direction: column; gap: 5px; font-size: 11px; }
		.dsh-pm-cprog-tl-row { display: flex; gap: 8px; align-items: baseline; }
		.dsh-pm-cprog-tl-time { color: var(--dsw-text-secondary, #aaa); font-variant-numeric: tabular-nums; flex: none; }
		.dsh-pm-cprog-tl-text { color: var(--dsw-text-primary, #444); }
		.dsh-pm-cprog-empty { font-size: 12px; color: var(--dsw-text-secondary, #999); }
		.dsh-pm-cprog-foot { display: flex; gap: 8px; }
		`,document.head.appendChild(e)}const Tt=[`slots`,`sessions`,`workspaces`];function Et(e){try{pt(),wt(),window.__dshReqboardClient?.dispose(),window.__dshPmCtx=e,window.__dshPmSessions=e.sessions,window.__dshPmWorkspaces=e.workspaces;let t=ct(),n=lt(t),r=e=>{e.detail?.open===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(Z,r),window.__dshReqboardClient={dispose:()=>{window.removeEventListener(Z,r),n(),t.closeBoard(),delete window.__dshPmCtx,delete window.__dshPmSessions,delete window.__dshPmWorkspaces}};let i=e.slots;i?(i.inject(`sidebar.footer.action`,()=>i.register({name:`sidebar.footer.action`,id:o,order:110,label:s},mt)),i.inject(`conversation.session.header.utilities`,()=>i.register({name:`conversation.session.header.utilities`,id:`dsh-pmboard:progress`,order:5,inject:e=>({sessionId:e})},St))):console.warn(`[dsh-pmboard] ctx.slots unavailable`)}catch(e){console.error(`[dsh-pmboard] client half failed to start:`,e)}}exports.apply=Et,exports.inject=Tt,exports.name=`dsh-pmboard/client`;
			return module.exports;
		}
	});

