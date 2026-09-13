window.__ModuleLoader__.load({
		id: "dsh-pmboard",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");const t=`dsh-panel-activate`;function n(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}function r(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}function i(e){let{panelName:r,activeAttr:i,otherActiveAttrs:a,pollMs:o=3e4,pauseOnHidden:s=!1,dispatchTarget:c=`window`,listenTarget:l=`window`,buildContainer:u,onMount:d,onPoll:f,onOpen:p,onClose:m}=e,h=!1,g,_,v,y=!1,b=()=>{if(g!==void 0||y)return;let e=n();if(e===void 0)return;let t=u();e.appendChild(t),g=t,v=d(t)??void 0},x=new MutationObserver(()=>{b()});x.observe(document.body,{childList:!0,subtree:!0}),b();let S=()=>{if(!(h||y)){h=!0,b();for(let e of a)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(i,``),(c===`document`?document:window).dispatchEvent(new CustomEvent(t,{detail:r})),D(),p?.()}},C=()=>{!h||y||(h=!1,document.documentElement.removeAttribute(i),O(),m?.())},w=()=>{h?C():S()},T=()=>h,E=()=>{h&&f()},D=()=>{O(),_=window.setInterval(E,o)},O=()=>{_!==void 0&&(clearInterval(_),_=void 0)},k=()=>{document.hidden?O():h&&D()};s&&document.addEventListener(`visibilitychange`,k);let A=t=>{if(!h)return;let n=t.target;if(n===null||g!==void 0&&(g===n||g.contains(n)))return;let r=`[data-`+e.prefix+`-entry]`;n.closest(r)===null&&C()};document.addEventListener(`click`,A,!0);let j=e=>{let t=e.detail;t!==void 0&&t!==r&&h&&C()},M=l===`document`?document:window;return M.addEventListener(t,j),{open:S,close:C,toggle:w,isActive:T,dispose:()=>{y||(y=!0,O(),s&&document.removeEventListener(`visibilitychange`,k),document.removeEventListener(`click`,A,!0),M.removeEventListener(t,j),x.disconnect(),v?.(),g?.remove(),g=void 0)}}}const a=`dsh-pmboard`,o=`项目看板`,s=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`,`data-dsh-bbd-active`,`data-dsh-gen-active`,`data-dsh-exec-active`],c={draft:`立项`,brainstorming:`头脑风暴`,planning:`写计划`,decomposing:`拆分`,implementing:`执行`,accepting:`验收`,done:`完成`,archived:`归档`,canceled:`取消`},l={todo:`待办`,in_progress:`进行中`,integrating:`联调`,testing:`测试`,in_review:`验收`,done:`完成`,canceled:`取消`},u={doc:`文档`,ui:`UI`,analysis:`分析`,implement:`实施`,test:`测试`,review:`评审`,merge:`合并`},d={feature:`功能`,bug:`缺陷`,doc:`文档`,refactor:`重构`,spike:`调研`,chore:`杂项`},f=[`draft`,`brainstorming`,`planning`,`decomposing`,`implementing`,`accepting`,`done`];function p(e){let t=e.startsWith(`session-`)?e.slice(8):e;return`w-${(t.split(`-`)[0]??t).slice(0,8)}`}const m=e=>{let t=new Date(e),n=e=>String(e).padStart(2,`0`);return`${n(t.getMonth()+1)}-${n(t.getDate())} ${n(t.getHours())}:${n(t.getMinutes())}`};function h(e,t){return t===0?`0/0`:`${e}/${t}`}function g(e){return e.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`).map(t=>{let n=e.tasks.filter(e=>e.requirementId===t.id);return{req:t,tasks:n,doneCount:n.filter(e=>e.status===`done`).length,totalCount:n.length,readyIds:e.ready[t.id]??[],blocked:t.blocked||n.some(e=>e.blocked)}})}function _(e,t=Date.now()){let n=g(e),i=f.map(e=>{let r=n.filter(t=>t.req.status===e),i=r.map(e=>v(e,t)).join(``);return`
		      <div class="dsh-pm-lane" data-lane="${e}">
		        <div class="dsh-pm-lane-head">
		          <span class="dsh-pm-lane-dot" data-status="${e}"></span>
		          <span class="dsh-pm-lane-title">${c[e]}</span>
		          <span class="dsh-pm-lane-count">${r.length}</span>
		        </div>
		        <div class="dsh-pm-lane-cards">${i}</div>
		      </div>`}).join(``),a=e.requirements.filter(e=>e.status===`archived`||e.status===`canceled`),o=a.length>0?`<div class="dsh-pm-archived-bar">
		         <span class="dsh-pm-archived-label">归档/取消 ${a.length}</span>
		         ${a.map(e=>`<span class="dsh-pm-archived-chip" data-status="${e.status}">${r(e.id)} ${r(e.title)}</span>`).join(``)}
		       </div>`:``;return`
		    <div class="dsh-pm-board">
		      <div class="dsh-pm-head">
		        <h1 class="dsh-pm-title">项目看板</h1>
		        <span class="dsh-pm-rev">rev ${e.revision}</span>
		        <button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button>
		        <button type="button" class="dsh-pm-btn" data-action="open-tasks" title="任务总览与甘特图">任务</button>
		        <button type="button" class="dsh-pm-btn primary" data-action="new-req" title="新建需求">+ 需求</button>
		      </div>
		      <div class="dsh-pm-lanes">${i}</div>
		      ${o}
		    </div>`}function v(e,t){let{req:n,tasks:i,doneCount:a,totalCount:o,readyIds:s,blocked:c}=e,l=o>0?Math.round(a/o*100):0,u=n.category?`<span class="dsh-pm-cat" data-cat="${n.category}">${d[n.category]??n.category}</span>`:``,f=se(n)+le(n)+z(n),p=c?`<span class="dsh-pm-flag blocked">阻塞</span>`:``,m=n.paused?`<span class="dsh-pm-flag paused">暂停</span>`:``,g=s.length>0?`<span class="dsh-pm-flag ready">${s.length} ready</span>`:``,_=oe(n,t),v=b(n)+x(i),S=y(n);return`
		    <div class="dsh-pm-card${c?` is-blocked`:``}" data-req="${r(n.id)}" data-action="open-req">
		      <div class="dsh-pm-card-top">
		        <span class="dsh-pm-card-id">${r(n.id)}</span>
		        ${u}${f}${p}${m}${g}
		      </div>
		      <div class="dsh-pm-card-title">${r(n.title)}</div>
		      <div class="dsh-pm-card-progress">
		        <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${l}%"></div></div>
		        <span class="dsh-pm-card-pct">${h(a,o)}</span>
		      </div>
		      ${_}
		      ${v}
		      ${S}
		    </div>`}function y(e){let t=(t,n,i)=>{let a=i?.primary===!0?`dsh-pm-btn sm primary`:`dsh-pm-btn sm`,o=i?.title===void 0?``:` title="${r(i.title)}"`;return`<button type="button" class="${a}" data-action="move-req" data-to="${t}" data-id="${r(e.id)}"${o}>${n}</button>`},n=``;switch(e.status){case`draft`:n=t(`brainstorming`,`开始头脑风暴`,{primary:!0,title:`进入头脑风暴；窗口接手开工时会自动进入`})+t(`canceled`,`取消`,{title:`取消该需求（仅人可操作）`});break;case`brainstorming`:n=t(`planning`,`写计划`,{primary:!0,title:`方案谈定 → 进入写计划阶段（计划在此阶段提交待人批准）`})+t(`draft`,`退回`,{title:`退回立项`});break;case`planning`:n=t(`decomposing`,`落库拆分`,{primary:!0,title:`计划获批后落库任务卡；未获批会被代码级拒绝`})+t(`brainstorming`,`退回重谈`,{title:`方案要改 → 退回头脑风暴`});break;case`decomposing`:n=t(`implementing`,`开始执行`,{primary:!0,title:`进入执行；任务开工时系统会自动推进`});break;case`implementing`:n=t(`accepting`,`提交验收`,{primary:!0,title:`进入验收；任务全部完成时系统会自动推进`});break;case`accepting`:n=t(`done`,`验收通过`,{primary:!0,title:`完成该需求；窗口 agent 交付后也可自行完成`});break;case`done`:n=t(`archived`,`归档`,{title:`归档归集文档（仅人可操作）`});break;default:n=``}return n.length===0?``:`<div class="dsh-pm-card-actions">${n}</div>`}function b(e){let t=e.sourceSessionId;if(!t)return``;let n=p(t);return`<button type="button" class="dsh-pm-window" data-action="jump-session" data-sid="${r(t)}" title="立项来源窗口（点击跳转到该会话）：${r(t)}">窗口 ${r(n)}</button>`}function x(e){for(let t=e.length-1;t>=0;t--){let n=e[t].executions;for(let e=n.length-1;e>=0;e--){let t=n[e].sessionId;if(t)return`<button type="button" class="dsh-pm-session" data-action="jump-session" data-sid="${r(t)}" title="跳转到执行会话">会话 ${r(t.slice(0,12))}…</button>`}}return``}function S(e,t,n=Date.now()){let i=t.filter(t=>t.requirementId===e.id),a=w(i),o=T(i),s=E(e.comments),l=C(e.status);return`
		    <div class="dsh-pm-detail" data-detail-req="${r(e.id)}">
		      <div class="dsh-pm-detail-head">
		        <button type="button" class="dsh-pm-btn" data-action="back" title="返回看板">← 看板</button>
		        <span class="dsh-pm-card-id">${r(e.id)}</span>
		        <span class="dsh-pm-status" data-status="${e.status}">${c[e.status]}</span>
		        ${e.blocked?`<span class="dsh-pm-flag blocked">阻塞</span>`:``}
		        ${b(e)}
		        <span class="dsh-pm-detail-updated">${m(e.updatedAt)}</span>
		      </div>
		      <h2 class="dsh-pm-detail-title">${r(e.title)}</h2>
		      ${e.description?`<div class="dsh-pm-detail-desc">${r(e.description)}</div>`:``}
		      ${l}
		      <div class="dsh-pm-detail-section">
		        <h3>实施计划（plan mode）</h3>
		        ${ce(e)}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>时间线</h3>
		        ${F(e,n)}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>任务 DAG</h3>
		        ${a}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <div class="dsh-pm-section-head">
		          <h3>任务（${i.length}）</h3>
		          <button type="button" class="dsh-pm-btn sm" data-action="new-task" data-id="${r(e.id)}" title="人工建任务卡（窗口 agent 走 reqboard_decompose 批量拆分）">+ 任务</button>
		        </div>
		        ${o}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>甘特图</h3>
		        ${R(e,i,n)}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>验收（人工审核）</h3>
		        ${B(e)}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>归档（文档合并）</h3>
		        ${V(e)}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>评论（${e.comments.length}）</h3>
		        ${s}
		        <div class="dsh-pm-comment-form">
		          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
		          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="req" data-id="${r(e.id)}">发送</button>
		        </div>
		      </div>
		    </div>`}function C(e){return{draft:`<div class="dsh-pm-gate">已立项：窗口接手开工后自动进入评审 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="brainstorming">提交评审</button></div>`,brainstorming:`<div class="dsh-pm-gate">评审中：窗口 agent 会自行推进到拆分，人可在此加速 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">确认方案</button> <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="draft">退回立项</button></div>`,decomposing:`<div class="dsh-pm-gate">拆分中：任务落库/开工后系统自动推进到实施 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="implementing">确认拆分</button></div>`,planning:`<div class="dsh-pm-gate">写计划：计划提交后请点上面计划卡的「批准计划」——批准前拆分会被告代码级拒绝 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">落库拆分</button> <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="brainstorming">退回重谈</button></div>`,implementing:`<div class="dsh-pm-gate">执行中：任务全部完成时自动进入验收 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="accepting">提交验收</button></div>`,accepting:`<div class="dsh-pm-gate">验收中：窗口 agent 交付后可自行完成，人可在此确认 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="done">验收通过</button></div>`,done:`<div class="dsh-pm-gate">已完成：归档归集文档（仅人可操作）<button type="button" class="dsh-pm-btn" data-action="move-req" data-to="archived">归档</button></div>`}[e]??``}function w(e){if(e.length===0)return`<div class="dsh-pm-empty">暂无任务</div>`;let t=new Map,n=new Map(e.map(e=>[e.id,e])),i=(e,r)=>{if(t.has(e.id))return t.get(e.id);if(r.has(e.id))return 0;r.add(e.id);let a=e.dependsOn.filter(e=>n.has(e)),o=a.length===0?0:1+Math.max(...a.map(e=>i(n.get(e),r)));return t.set(e.id,o),o};e.forEach(e=>i(e,new Set));let a=Math.max(...t.values()),o=Array.from({length:a+1},()=>[]);return e.forEach(e=>o[t.get(e.id)].push(e)),`<div class="dsh-pm-dag">`+o.map((e,t)=>`
		    <div class="dsh-pm-dag-layer">
		      <span class="dsh-pm-dag-layer-label">L${t}</span>
		      ${e.map(e=>`
		        <span class="dsh-pm-dag-node" data-status="${e.status}" data-action="open-task" data-task="${r(e.id)}" title="${r(e.title)}">
		          ${r(e.id)} ${r(e.title.slice(0,20))}${e.title.length>20?`…`:``}
		        </span>`).join(``)}
		    </div>`).join(``)+`</div>`}function T(e){return e.length===0?`<div class="dsh-pm-empty">暂无任务</div>`:`<div class="dsh-pm-taskcols">`+[`todo`,`in_progress`,`integrating`,`testing`,`in_review`,`done`].map(t=>{let n=e.filter(e=>e.status===t);return`
		      <div class="dsh-pm-taskcol" data-col="${t}">
		        <div class="dsh-pm-taskcol-head">${l[t]} ${n.length}</div>
		        ${n.map(e=>`
		          <div class="dsh-pm-task" data-task="${r(e.id)}" data-action="open-task">
		            <div class="dsh-pm-task-title">${r(e.title)}</div>
		            <div class="dsh-pm-task-meta">
		              <span class="dsh-pm-phase">${u[e.phase]??e.phase}</span>
		              ${e.blocked?`<span class="dsh-pm-flag blocked">阻塞</span>`:``}
		            </div>
		          </div>`).join(``)}
		      </div>`}).join(``)+`</div>`}function E(e){return e.length===0?`<div class="dsh-pm-empty">暂无评论</div>`:`<div class="dsh-pm-comments">`+e.map(e=>`
		    <div class="dsh-pm-comment">
		      <span class="dsh-pm-comment-meta">${r(e.createdBy?.kind??`human`)} · ${m(e.createdAt)}</span>
		      <div class="dsh-pm-comment-body">${r(e.body)}</div>
		    </div>`).join(``)+`</div>`}function D(e,t,n=Date.now()){let i=e.executions.map(e=>`
		    <div class="dsh-pm-exec" data-outcome="${e.outcome}">
		      <span class="dsh-pm-exec-outcome">${e.outcome}</span>
		      <span>${m(e.startedAt)}</span>
		      ${e.sessionId?`<button type="button" class="dsh-pm-session" data-action="jump-session" data-sid="${r(e.sessionId)}">会话 ${r(e.sessionId.slice(0,12))}…</button>`:``}
		      ${e.error?`<div class="dsh-pm-exec-error">${r(e.error)}</div>`:``}
		      ${e.evidence&&e.evidence.length>0?`<div class="dsh-pm-exec-evidence">${e.evidence.map(e=>`<code>${r(e)}</code>`).join(` `)}</div>`:``}
		    </div>`).join(``);return`
		    <div class="dsh-pm-taskdetail" data-detail-task="${r(e.id)}">
		      <div class="dsh-pm-detail-head">
		        <button type="button" class="dsh-pm-btn" data-action="back-req" data-req="${r(e.requirementId)}" title="返回需求">← ${r(e.requirementId)}</button>
		        <span class="dsh-pm-card-id">${r(e.id)}</span>
		        <span class="dsh-pm-status" data-status="${e.status}">${l[e.status]}</span>
		      </div>
		      <h2 class="dsh-pm-detail-title">${r(e.title)}</h2>
		      ${e.description?`<div class="dsh-pm-detail-desc">${r(e.description)}</div>`:``}
		      <div class="dsh-pm-detail-section">
		        <h3>属性</h3>
		        <div class="dsh-pm-kv">
		          <span>阶段</span><span>${u[e.phase]??e.phase}</span>
		          <span>端侧</span><span>${e.side}</span>
		          <span>依赖</span><span>${e.dependsOn.length>0?e.dependsOn.map(r).join(`, `):`无`}</span>
		          <span>验收标准</span><span>${r(e.acceptance)}</span>
		        </div>
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>时间线</h3>
		        ${ee(e,n)}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>执行记录（${e.executions.length}）</h3>
		        ${i||`<div class="dsh-pm-empty">暂无执行</div>`}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>评论（${e.comments.length}）</h3>
		        ${E(e.comments)}
		        <div class="dsh-pm-comment-form">
		          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
		          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="task" data-id="${r(e.id)}">发送</button>
		        </div>
		      </div>
		    </div>`}function O(e,t){let n=e.filter(e=>e.status===`pending`),i=t.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`),a=n.map(e=>{let t=e.suggestedAction===`create_req`&&!e.suggestedTargetId,n=e.suggestedTargetId?`${e.suggestedAction===`bind_req`?`绑定需求`:e.suggestedAction===`bind_task`?`绑定任务`:`新建需求`} ${r(e.suggestedTargetId)}`:e.suggestedAction===`create_req`?`新建需求${e.suggestedCategory?` · ${d[e.suggestedCategory]??e.suggestedCategory}`:``}`:``,i=t?`
		        <div class="dsh-pm-triage-edit">
		          <input type="text" class="dsh-pm-input" data-role="triage-title" value="${r(e.suggestedTitle??e.firstMessageText.slice(0,120))}" placeholder="需求名称（可编辑）" />
		          <select class="dsh-pm-input" data-role="triage-category">
		            ${Object.entries(d).map(([t,n])=>`<option value="${t}" ${t===(e.suggestedCategory??`feature`)?`selected`:``}>${n}</option>`).join(``)}
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
		    </div>`}function k(){return`<div class="dsh-pm-board"><div class="dsh-pm-empty">暂无数据 — 点击「+ 需求」创建第一个需求</div></div>`}function A(e){return`<div class="dsh-pm-board"><div class="dsh-pm-error">加载失败：${r(e)}</div></div>`}function j(e){let t=Math.floor(Math.max(0,e)/6e4);if(t<60)return t+` 分`;let n=Math.floor(t/60);return n<24?n+` 小时 `+t%60+` 分`:Math.floor(n/24)+` 天 `+n%24+` 小时`}function M(e){return e===`done`||e===`archived`||e===`canceled`}function N(e,t){let n=e.statusHistory;if(n!==void 0&&n.length>0)return n;let r=[{status:t,at:e.createdAt,by:{kind:`human`},reason:`创建`,inferred:!0}];return e.status!==void 0&&e.status!==t&&e.updatedAt!==void 0&&r.push({status:e.status,at:Math.max(e.updatedAt,e.createdAt),by:e.updatedBy??{kind:`human`},reason:`按 updatedAt 回填（当时无事件留痕）`,inferred:!0}),r}function P(e,t,n,i,a){let o=N(e,i),s=new Map;o.forEach((e,t)=>{s.has(e.status)||s.set(e.status,t)});let c=o.map((e,t)=>({e,i:t})).filter(e=>!t.includes(e.e.status)).map(e=>e.e.status),l=(e,t)=>{if(t===void 0)return`<div class="dsh-pm-tl-row pending" data-status="`+e+`"><span class="dsh-pm-tl-label">`+(n[e]??e)+`</span><span class="dsh-pm-tl-time">—</span><span class="dsh-pm-tl-dur"></span></div>`;let i=o[t],s=o[t+1],c=t===o.length-1,l=(s?.at??a)-i.at,u=c?M(i.status)?``:`已停留 `+j(l):`停留 `+j(l),d=i.by.kind+(i.by.sessionId===void 0?``:` `+p(i.by.sessionId));return`<div class="dsh-pm-tl-row`+(c?` current`:``)+`" data-status="`+r(i.status)+`"><span class="dsh-pm-tl-label">`+(n[e]??e)+`</span><span class="dsh-pm-tl-time">`+r(m(i.at))+`</span><span class="dsh-pm-tl-dur">`+r(u)+`</span><span class="dsh-pm-tl-by">`+r(d)+`</span>`+(i.inferred===!0?`<span class="dsh-pm-tl-inferred" title="历史回填：老记录无事件留痕，由创建时间与评论反推">回填</span>`:``)+`</div>`},u=t.map(e=>l(e,s.get(e))).join(``)+c.map(e=>l(e,s.get(e))).join(``),d=o[0].at,f=o[o.length-1],h=(M(f.status)?f.at:a)-d;return`<div class="dsh-pm-timeline">`+u+`<div class="dsh-pm-tl-total">创建 `+r(m(d))+(M(f.status)?` · 总耗时 `:` · 至今 `)+r(j(h))+`</div></div>`}function F(e,t){return P(e,f.concat([`archived`]),c,`draft`,t)}function ee(e,t){return P(e,L,l,`todo`,t)}function I(e){let t=N(e,`draft`),n=new Map;for(let e of t)n.has(e.status)||n.set(e.status,e);let i=[...n.values()].map(e=>`<span class="dsh-pm-strip-item" data-status="`+r(e.status)+`">`+(c[e.status]??e.status)+` <b>`+r(m(e.at))+`</b></span>`);return i.length===0?``:`<div class="dsh-pm-strip">`+i.join(`<span class="dsh-pm-strip-arrow">→</span>`)+`</div>`}const L=[`todo`,`in_progress`,`integrating`,`testing`,`in_review`,`done`],te=[`draft`,`brainstorming`,`decomposing`,`implementing`,`accepting`,`done`,`archived`];function ne(e,t){let n=N(e,`todo`),r=M(e.status);return n.map((i,a)=>{let o=n[a+1]?.at??(r?Math.max(e.updatedAt,i.at):t);return{status:i.status,from:i.at,to:o}})}function re(e,t){return e.length>t?e.slice(0,t)+`…`:e}function R(e,t,n){if(t.length===0)return`<div class="dsh-pm-empty">尚未拆分任务</div>`;let i=[...t].sort((e,t)=>e.createdAt-t.createdAt),a=[n];for(let e of i)for(let t of N(e,`todo`))a.push(t.at);for(let t of N(e,`draft`))a.push(t.at);let o=Math.min(...a),s=Math.max(...a),u=Math.max(s-o,36e5),d=e=>190+(e-o)/u*620,f=34+i.length*22+10,p=[];p.push(`<svg class="dsh-pm-gantt" viewBox="0 0 822 `+f+`" width="100%" height="`+f+`" preserveAspectRatio="xMinYMin meet" role="img" aria-label="任务甘特图">`);for(let e=0;e<=4;e++){let t=o+u*e/4,n=d(t).toFixed(1);p.push(`<line class="dsh-pm-gantt-grid" x1="`+n+`" y1="26" x2="`+n+`" y2="`+(f-10)+`" />`),p.push(`<text class="dsh-pm-gantt-axis" x="`+n+`" y="20" text-anchor="middle">`+r(m(t))+`</text>`)}for(let t of N(e,`draft`)){if(!te.includes(t.status))continue;let n=d(t.at).toFixed(1);p.push(`<line class="dsh-pm-gantt-mile" data-status="`+r(t.status)+`" x1="`+n+`" y1="28" x2="`+n+`" y2="`+(f-10)+`">`),p.push(`<title>`+r(e.id+` `+(c[t.status]??t.status)+` `+m(t.at))+`</title></line>`)}if(i.forEach((e,t)=>{let i=34+t*22;p.push(`<text class="dsh-pm-gantt-rowlabel" x="6" y="`+(i+13)+`">`+r(re(e.id+` `+e.title,24))+`</text>`),p.push(`<rect class="dsh-pm-gantt-track" x="190" y="`+(i+4)+`" width="620" height="13" rx="3" />`);for(let t of ne(e,n)){let n=d(t.from),a=Math.max(2,d(t.to)-n);p.push(`<rect class="dsh-pm-gantt-bar" data-status="`+r(t.status)+`" x="`+n.toFixed(1)+`" y="`+(i+4)+`" width="`+a.toFixed(1)+`" height="13" rx="3">`),p.push(`<title>`+r(e.id+` `+e.title+`｜`+(l[t.status]??t.status)+` `+m(t.from)+` → `+m(t.to)+`（`+j(t.to-t.from)+`）`)+`</title></rect>`)}}),n>=o&&n<=s){let e=d(n).toFixed(1);p.push(`<line class="dsh-pm-gantt-now" x1="`+e+`" y1="28" x2="`+e+`" y2="`+(f-10)+`"><title>现在</title></line>`)}p.push(`</svg>`);let h=`<div class="dsh-pm-gantt-legend">`+L.map(e=>`<span class="dsh-pm-gantt-legend-item"><i data-status="`+e+`"></i>`+l[e]+`</span>`).join(``)+`<span class="dsh-pm-gantt-legend-item"><i class="mile"></i>需求里程碑</span></div>`;return`<div class="dsh-pm-gantt-wrap">`+p.join(``)+`</div>`+h}function ie(e,t){return`<table class="dsh-pm-ttable"><thead><tr><th>任务</th><th>标题</th><th>状态</th><th>阶段</th><th>端侧</th><th>依赖</th><th>创建</th><th>耗时</th></tr></thead><tbody>`+[...e].sort((e,t)=>e.createdAt-t.createdAt).map(e=>{let n=N(e,`todo`),i=n[0].at,a=n[n.length-1],o=n.find(e=>e.status===`done`)?.at,s=M(e.status)?`共 `+j((o??a.at)-i):`已用 `+j(t-i);return`<tr class="dsh-pm-trow" data-task="`+r(e.id)+`" data-action="open-task"><td class="dsh-pm-tid">`+r(e.id)+`</td><td class="dsh-pm-ttitle">`+r(e.title)+`</td><td><span class="dsh-pm-status" data-status="`+r(e.status)+`">`+(l[e.status]??e.status)+`</span></td><td>`+r(u[e.phase]??e.phase)+`</td><td>`+r(e.side)+`</td><td class="dsh-pm-tdeps">`+(e.dependsOn.length>0?r(e.dependsOn.join(` `)):`—`)+`</td><td>`+r(m(i))+`</td><td>`+r(s)+`</td></tr>`}).join(``)+`</tbody></table>`}function ae(e,t=Date.now()){let n=e.requirements.map(t=>({req:t,tasks:e.tasks.filter(e=>e.requirementId===t.id)})).filter(e=>e.tasks.length>0).sort((e,t)=>t.req.updatedAt-e.req.updatedAt),i=`<div class="dsh-pm-head"><button type="button" class="dsh-pm-btn" data-action="back" title="返回泳道看板">← 看板</button><h1 class="dsh-pm-title">任务</h1><span class="dsh-pm-rev">`+e.tasks.length+` 个任务 · `+n.length+` 个需求 · rev `+e.revision+`</span><button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button></div>`;if(n.length===0)return`<div class="dsh-pm-board">`+i+`<div class="dsh-pm-empty">还没有任务。两种来源：① 需求详情页点「+ 任务」人工建卡；② 窗口 agent 调用 reqboard_decompose 真拆分落库（推荐，含依赖 DAG）</div></div>`;let a=n.map(e=>{let n=e.tasks.filter(e=>e.status===`done`).length;return`<div class="dsh-pm-tasks-group"><div class="dsh-pm-tasks-group-head"><span class="dsh-pm-card-id">`+r(e.req.id)+`</span><span class="dsh-pm-status" data-status="`+r(e.req.status)+`">`+(c[e.req.status]??e.req.status)+`</span><span class="dsh-pm-tasks-group-title">`+r(e.req.title)+`</span><span class="dsh-pm-hint">`+n+`/`+e.tasks.length+` 完成</span><button type="button" class="dsh-pm-btn sm" data-action="open-req" data-req="`+r(e.req.id)+`">打开需求</button></div>`+I(e.req)+`<div class="dsh-pm-detail-section"><h3>甘特图</h3>`+R(e.req,e.tasks,t)+`</div><div class="dsh-pm-detail-section"><h3>任务清单</h3>`+ie(e.tasks,t)+`</div></div>`}).join(``);return`<div class="dsh-pm-board">`+i+`<div class="dsh-pm-tasks-page">`+a+`</div></div>`}function oe(e,t){let n=N(e,`draft`),i=n[0],a=n[n.length-1],o=[`创建 `+m(i.at)];return a.status!==i.status&&o.push((c[a.status]??a.status)+` `+m(a.at)),M(a.status)||o.push(`已停留 `+j(t-a.at)),`<div class="dsh-pm-card-time">`+r(o.join(` · `))+`</div>`}function se(e){let t=e.plan;return t===void 0?``:t.approvedAt===void 0?t.rejectedAt===void 0?`<span class="dsh-pm-flag plan-pending" title="实施计划已提交，等待人批准后才能拆分">计划待批</span>`:`<span class="dsh-pm-flag plan-rejected" title="实施计划被退回，待重写">计划被退</span>`:`<span class="dsh-pm-flag plan-ok" title="实施计划已批准，可拆分落库">计划已批</span>`}function ce(e){let t=e.plan;if(t===void 0)return`<div class="dsh-pm-plan is-empty">尚未提交实施计划。计划模式：窗口 agent 用 <code>reqboard_plan_submit</code> 先提交计划（文档路径 + 摘要 + 任务表），人在此处批准后才允许 <code>reqboard_decompose</code> 落库任务卡——拆分的粒度在人点头之前就已写死在计划里。</div>`;let n=t.approvedAt===void 0?t.rejectedAt===void 0?`<span class="dsh-pm-plan-status" data-state="pending">待批准</span>`:`<span class="dsh-pm-plan-status" data-state="rejected">已退回 `+r(m(t.rejectedAt))+`</span>`:`<span class="dsh-pm-plan-status" data-state="approved">已批准 `+r(m(t.approvedAt))+`</span>`,i=t.approvedAt===void 0?`<button type="button" class="dsh-pm-btn sm primary" data-action="plan-approve" data-id="`+r(e.id)+`">批准计划</button><button type="button" class="dsh-pm-btn sm" data-action="plan-reject" data-id="`+r(e.id)+`">退回计划</button>`:`<span class="dsh-pm-hint">拆分已解锁：窗口可用 reqboard_decompose 按此计划落库任务卡</span>`,a=t.tasks.map(e=>{let t=(e.dependsOn??[]).length>0?` · 依赖 `+r((e.dependsOn??[]).join(`,`)):``;return`<div class="dsh-pm-plan-task"><span class="dsh-pm-plan-key">`+r(e.key)+`</span><span class="dsh-pm-plan-title">`+r(e.title)+`</span><span class="dsh-pm-plan-meta">`+r(u[e.phase??`implement`]??e.phase??``)+` / `+r(e.side??``)+t+`</span>`+(e.acceptance!==void 0&&e.acceptance.length>0?`<span class="dsh-pm-plan-accept">验收：`+r(e.acceptance)+`</span>`:`<span class="dsh-pm-plan-accept missing">缺验收标准</span>`)+`</div>`}).join(``);return`<div class="dsh-pm-plan"><div class="dsh-pm-plan-head">`+n+`<code class="dsh-pm-plan-path">`+r(t.path)+`</code><span class="dsh-pm-hint">提交 `+r(m(t.submittedAt))+` · `+t.tasks.length+` 个任务</span>`+i+`</div><div class="dsh-pm-plan-summary">`+r(t.summary)+`</div>`+(t.rejectedReason===void 0?``:`<div class="dsh-pm-plan-reason">退回理由：`+r(t.rejectedReason)+`</div>`)+`<div class="dsh-pm-plan-tasks">`+a+`</div></div>`}function le(e){return e.status===`accepting`?e.verification===void 0?`<span class="dsh-pm-flag verify-pending" title="验收态但还没提交验收材料">待验收材料</span>`:`<span class="dsh-pm-flag verify-pending" title="验收材料已提交，等人工审核">待人工审核</span>`:``}function z(e){return e.status===`done`?e.archive===void 0?`<span class="dsh-pm-flag archive-pending" title="已完成，等窗口准备归档材料">待归档材料</span>`:`<span class="dsh-pm-flag archive-pending" title="归档材料已备，等人点归档">待归档</span>`:``}function B(e){let t=e.verification;if(t===void 0)return`<div class="dsh-pm-block is-empty">`+(e.status===`implementing`||e.status===`accepting`?`窗口尚未提交验收材料。人工审核前需要证据：窗口用 <code>reqboard_verify_submit</code> 提交「做了什么 + 怎么验的 + 看到什么结果」。`:`尚未进入验收阶段。`)+`</div>`;let n=t.decision===`pass`?`<span class="dsh-pm-review" data-state="pass">人工审核通过 `+r(t.reviewedAt===void 0?``:m(t.reviewedAt))+`</span>`:t.decision===`rework`?`<span class="dsh-pm-review" data-state="rework">已退回返工 `+r(t.reviewedAt===void 0?``:m(t.reviewedAt))+`</span>`:`<span class="dsh-pm-review" data-state="pending">待人工审核</span>`,i=e.status===`accepting`?`<button type="button" class="dsh-pm-btn sm primary" data-action="verify-pass" data-id="`+r(e.id)+`">验收通过</button><button type="button" class="dsh-pm-btn sm" data-action="verify-rework" data-id="`+r(e.id)+`">退回返工</button>`:``,a=t.evidence.map(e=>`<li>`+r(e)+`</li>`).join(``);return`<div class="dsh-pm-block"><div class="dsh-pm-block-head">`+n+`<span class="dsh-pm-hint">提交 `+r(m(t.submittedAt))+`</span>`+i+`</div><div class="dsh-pm-block-summary">`+r(t.summary)+`</div><ul class="dsh-pm-evidence">`+a+`</ul>`+(t.reviewNote===void 0?``:`<div class="dsh-pm-block-note">审核意见：`+r(t.reviewNote)+`</div>`)+`</div>`}function V(e){let t=e.archive;if(t===void 0)return`<div class="dsh-pm-block is-empty">`+(e.status===`done`?`窗口尚未准备归档材料。归档不是挪目录：窗口用 <code>reqboard_archive_submit</code> 提交需求目录、文档清单、合并去向（只允许既有规范目录：docs/ 或 agent-dh/docs/ 下的 adr|architecture|guides|rfcs|work-logs|strategy-research）与一句话索引条目，人再点归档；必填文档与合并去向按需求类型限定，规范见 agent-dh/docs/architecture/requirement-archive.md。`:`归档在需求完成（done）后进行；不同需求类型的必填文档与合并去向见 agent-dh/docs/architecture/requirement-archive.md。`)+`</div>`;let n=t.archivedAt===void 0?`<span class="dsh-pm-review" data-state="pending">待归档（材料已备）</span>`:`<span class="dsh-pm-review" data-state="pass">已归档 `+r(m(t.archivedAt))+`</span>`,i=e.status===`done`&&t.archivedAt===void 0?`<button type="button" class="dsh-pm-btn sm primary" data-action="archive-req" data-id="`+r(e.id)+`">归档</button>`:``,a=t.docs.map(e=>`<li><span class="dsh-pm-doc-kind">`+r(H[e.kind]??e.kind)+`</span> <code>`+r(e.path)+`</code></li>`).join(``),o=t.mergedInto.map(e=>`<li><code>`+r(e)+`</code></li>`).join(``);return`<div class="dsh-pm-block"><div class="dsh-pm-block-head">`+n+`<code class="dsh-pm-block-path">`+r(t.dir)+`</code><span class="dsh-pm-hint">材料提交 `+r(m(t.submittedAt))+`</span>`+i+`</div><div class="dsh-pm-block-summary">索引条目：`+r(t.indexEntry)+`</div><div class="dsh-pm-doc-group"><span class="dsh-pm-hint">需求目录内的文档</span><ul class="dsh-pm-doc-list">`+a+`</ul></div><div class="dsh-pm-doc-group"><span class="dsh-pm-hint">合并进的项目文档</span><ul class="dsh-pm-doc-list">`+o+`</ul></div></div>`}const H={requirement:`需求说明`,plan:`实施计划`,verification:`验收材料`,retro:`复盘`,notes:`其他`},U=8e3;var W=class extends Error{code;constructor(e,t){super(e),this.code=t}};async function G(e){let t=await e;if(!t.ok)throw new W(`HTTP `+t.status);let n=await t.json().catch(()=>({}));if(n.success!==!0)throw new W(n.error??`API 返回失败`,n.code);return n.data}const K=e=>G(fetch(e,{signal:AbortSignal.timeout(U)})),q=(e,t)=>G(fetch(e,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify(t),signal:AbortSignal.timeout(U)})),ue=()=>K(`/dashboard/api/reqboard/`),de=()=>K(`/dashboard/api/reqboard/triage`);function fe(e){return q(`/dashboard/api/reqboard/req/create`,e)}function pe(e){return q(`/dashboard/api/reqboard/req/move`,e)}function me(e){return q(`/dashboard/api/reqboard/req/plan/approve`,e)}function he(e){return q(`/dashboard/api/reqboard/req/plan/reject`,e)}function ge(e){return q(`/dashboard/api/reqboard/req/verify/pass`,e)}function _e(e){return q(`/dashboard/api/reqboard/req/verify/rework`,e)}function ve(e){return q(`/dashboard/api/reqboard/req/archive`,e)}function ye(e){return q(`/dashboard/api/reqboard/task/create`,e)}function be(e){return q(`/dashboard/api/reqboard/comment`,e)}function J(e){return q(`/dashboard/api/reqboard/triage/confirm`,e)}function xe(e){return q(`/dashboard/api/reqboard/triage/rebind`,e)}function Se(e){return q(`/dashboard/api/reqboard/triage/reject`,e)}function Ce(e){let t=new EventSource(`/dashboard/api/reqboard/events`);return t.onmessage=t=>{try{let n=JSON.parse(t.data);e(n.revision,n.kind)}catch{}},()=>t.close()}function we(){let e=()=>window;return{getSessions:()=>{try{let t=e().__dshPmSessions??e().__dshPmCtx?.sessions;if(t&&typeof t.open==`function`&&t.list)return t}catch{}},getWorkspaces:()=>{try{let t=e().__dshPmWorkspaces??e().__dshPmCtx?.workspaces;if(t&&t.list)return t}catch{}}}}async function Y(e,t){let n=e.getSessions();if(n===void 0)return`unavailable`;let r=e=>{try{return n.list.getSnapshot().byId[e]!==void 0}catch{return!1}};if(r(t))return(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`);try{await n.refresh()}catch{}return r(t)?(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`):`missing`}function Te(){return{openBoard:()=>{},closeBoard:()=>{},toggleBoard:()=>{},getSnapshot:()=>({boardOpen:!1}),refresh:()=>{}}}function Ee(e){let t,n=[],r={kind:`board`},o,c,l=()=>{if(o!==void 0){if(t===void 0){o.innerHTML=k();return}switch(r.kind){case`board`:o.innerHTML=_(t);break;case`req`:{let e=t.requirements.find(e=>e.id===r.reqId);o.innerHTML=e?S(e,t.tasks):_(t),e||(r={kind:`board`});break}case`task`:{let e=t.tasks.find(e=>e.id===r.taskId),n=e?t.requirements.find(t=>t.id===e.requirementId):void 0;o.innerHTML=e?D(e,n):_(t),e||(r={kind:`board`});break}case`tasks`:o.innerHTML=ae(t);break;case`triage`:o.innerHTML=O(n,t)}}},u=async()=>{try{let[e,r]=await Promise.all([ue(),de()]);t=e,n=r.pending,l()}catch(e){o!==void 0&&(o.innerHTML=A(String(e)))}},d=()=>{c?.(),c=Ce(()=>{u()})},f=e=>{let i=e.target.closest(`[data-action]`);if(i!==null&&t!==void 0)switch(i.dataset.action??``){case`refresh`:u();return;case`new-req`:{let e=window.prompt(`需求标题`);e&&e.trim()&&fe({title:e.trim()}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`open-req`:i.dataset.req&&(r={kind:`req`,reqId:i.dataset.req},l());return;case`open-task`:i.dataset.task&&(r={kind:`task`,taskId:i.dataset.task},l());return;case`open-tasks`:r={kind:`tasks`},l();return;case`new-task`:{let e=i.dataset.id;if(!e)return;let t=window.prompt(`任务标题`);t&&t.trim()&&ye({requirementId:e,title:t.trim(),phase:`implement`,side:`fullstack`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`back`:r={kind:`board`},l();return;case`back-req`:r={kind:`req`,reqId:i.dataset.req??``},l();return;case`move-req`:{let e=i.dataset.id??(r.kind===`req`?r.reqId:void 0),t=i.dataset.to;e&&t&&pe({id:e,to:t,actor:`human`,reason:i.dataset.id?`看板泳道卡面操作`:`需求详情页操作`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`add-comment`:{let e=(o?.querySelector(`[data-role="comment-input"]`))?.value.trim();e&&i.dataset.target&&i.dataset.id&&be({target:i.dataset.target,id:i.dataset.id,body:e,actor:`human`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`jump-session`:{let e=i.dataset.sid;e&&Y(we(),e).then(e=>{e===`archived`?window.alert(`该会话已归档（日志保留，侧栏不可见）`):e===`missing`?window.alert(`该会话不在当前列表（可能已删除）`):e===`unavailable`&&window.alert(`会话服务暂不可用`)});return}case`verify-pass`:{let e=i.dataset.id;e&&ge({id:e}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`verify-rework`:{let e=i.dataset.id;if(!e)return;let t=window.prompt(`退回返工的意见（窗口会按它整改）`);if(t===null)return;_e({id:e,note:t.trim()||`（未填意见）`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`archive-req`:{let e=i.dataset.id;e&&ve({id:e}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`plan-approve`:{let e=i.dataset.id;e&&me({id:e}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`plan-reject`:{let e=i.dataset.id;if(!e)return;let t=window.prompt(`退回理由（窗口会按它重写计划）`);if(t===null)return;he({id:e,reason:t.trim()||`（未填理由）`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`triage-confirm`:{let e=i.dataset.triage;if(!e)return;let t=n.find(t=>t.id===e);if(t?.suggestedAction===`bind_req`&&t.suggestedTargetId)J({triageId:e,action:`bind_req`,targetId:t.suggestedTargetId}).then(()=>u()).catch(e=>window.alert(String(e)));else{let t=i.closest(`.dsh-pm-triage`),n=t?.querySelector(`[data-role="triage-title"]`)?.value.trim(),r=t?.querySelector(`[data-role="triage-category"]`)?.value;J({triageId:e,action:`create_req`,...n?{title:n}:{},...r?{category:r}:{}}).then(()=>u()).catch(e=>window.alert(String(e)))}return}case`triage-rebind`:{let e=o?.querySelector(`.dsh-pm-rebind-host`);e&&(e.style.display=`flex`,e.dataset.triage=i.dataset.triage??``);return}case`triage-rebind-confirm`:{let e=o?.querySelector(`.dsh-pm-rebind-host`),t=e?.dataset.triage,n=e?.querySelector(`[data-role="rebind-select"]`);t&&n?.value&&xe({triageId:t,targetId:n.value}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`triage-reject`:{let e=i.dataset.triage;e&&Se({triageId:e}).then(()=>u()).catch(e=>window.alert(String(e)));return}}},p=i({prefix:`dsh-pm`,panelName:a,activeAttr:`data-dsh-pm-active`,otherActiveAttrs:s,pollMs:2e4,pauseOnHidden:!0,buildContainer:()=>{let e=document.createElement(`div`);return e.dataset.dshPmView=``,e.className=`dsh-pm-view`,e},onMount:e=>(o=e,e.addEventListener(`click`,f),u(),d(),()=>{e.removeEventListener(`click`,f),c?.(),c=void 0,o=void 0}),onPoll:()=>{u()},onOpen:()=>{u()}}),m=e;return m.openBoard=p.open,m.closeBoard=p.close,m.toggleBoard=p.toggle,m.getSnapshot=()=>({boardOpen:p.isActive()}),m.refresh=()=>{u()},()=>{p.dispose()}}const X=`dsh-pmboard/footer-action.css`,Z=`dsh-pmboard:open-board`,Q=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function De(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${X}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=X,e.textContent=`
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
		`,document.head.appendChild(e)}function Oe(t){let{wide:n}=t,r=o;return(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-reqboard-foot wide`:`dsh-reqboard-foot rail`,title:r,"aria-label":r,onClick:()=>{window.dispatchEvent(new CustomEvent(Z,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},Q),(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-label`,key:`l`},r)]:(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},Q))}const $=`dsh-pmboard/styles.css`;function ke(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${$}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=$,e.textContent=`
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
		`,document.head.appendChild(e)}const Ae=[`slots`,`sessions`,`workspaces`];function je(e){try{De(),ke(),window.__dshReqboardClient?.dispose(),window.__dshPmCtx=e,window.__dshPmSessions=e.sessions,window.__dshPmWorkspaces=e.workspaces;let t=Te(),n=Ee(t),r=e=>{e.detail?.open===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(Z,r),window.__dshReqboardClient={dispose:()=>{window.removeEventListener(Z,r),n(),t.closeBoard(),delete window.__dshPmCtx,delete window.__dshPmSessions,delete window.__dshPmWorkspaces}};let i=e.slots;i?i.inject(`sidebar.footer.action`,()=>i.register({name:`sidebar.footer.action`,id:a,order:110,label:o},Oe)):console.warn(`[dsh-pmboard] ctx.slots unavailable`)}catch(e){console.error(`[dsh-pmboard] client half failed to start:`,e)}}exports.apply=je,exports.inject=Ae,exports.name=`dsh-pmboard/client`;
			return module.exports;
		}
	});

