window.__ModuleLoader__.load({
		id: "dsh-pmboard",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("@pi-investment/page-kit/client"),t=require("react");const n=`dsh-pmboard`,r=`项目看板`,i=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`,`data-dsh-bbd-active`,`data-dsh-gen-active`,`data-dsh-exec-active`],a={draft:`立项`,reviewing:`评审`,decomposing:`拆分`,implementing:`实施`,accepting:`验收`,done:`完成`,archived:`归档`,canceled:`取消`},o={todo:`待办`,in_progress:`进行中`,integrating:`联调`,testing:`测试`,in_review:`验收`,done:`完成`,canceled:`取消`},s={doc:`文档`,ui:`UI`,analysis:`分析`,implement:`实施`,test:`测试`,review:`评审`,merge:`合并`},c={feature:`功能`,bug:`缺陷`,doc:`文档`,refactor:`重构`,spike:`调研`,chore:`杂项`},l=[`draft`,`reviewing`,`decomposing`,`implementing`,`accepting`,`done`],u=e=>{let t=new Date(e),n=e=>String(e).padStart(2,`0`);return`${t.getMonth()+1}-${n(t.getDate())} ${n(t.getHours())}:${n(t.getMinutes())}`};function d(e,t){return t===0?`0/0`:`${e}/${t}`}function f(e){return e.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`).map(t=>{let n=e.tasks.filter(e=>e.requirementId===t.id);return{req:t,tasks:n,doneCount:n.filter(e=>e.status===`done`).length,totalCount:n.length,readyIds:e.ready[t.id]??[],blocked:t.blocked||n.some(e=>e.blocked)}})}function p(t){let n=f(t),r=l.map(e=>{let t=n.filter(t=>t.req.status===e),r=t.map(e=>m(e)).join(``);return`
		      <div class="dsh-pm-lane" data-lane="${e}">
		        <div class="dsh-pm-lane-head">
		          <span class="dsh-pm-lane-dot" data-status="${e}"></span>
		          <span class="dsh-pm-lane-title">${a[e]}</span>
		          <span class="dsh-pm-lane-count">${t.length}</span>
		        </div>
		        <div class="dsh-pm-lane-cards">${r}</div>
		      </div>`}).join(``),i=t.requirements.filter(e=>e.status===`archived`||e.status===`canceled`),o=i.length>0?`<div class="dsh-pm-archived-bar">
		         <span class="dsh-pm-archived-label">归档/取消 ${i.length}</span>
		         ${i.map(t=>`<span class="dsh-pm-archived-chip" data-status="${t.status}">${(0,e.esc)(t.id)} ${(0,e.esc)(t.title)}</span>`).join(``)}
		       </div>`:``;return`
		    <div class="dsh-pm-board">
		      <div class="dsh-pm-head">
		        <h1 class="dsh-pm-title">项目看板</h1>
		        <span class="dsh-pm-rev">rev ${t.revision}</span>
		        <button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button>
		        <button type="button" class="dsh-pm-btn primary" data-action="new-req" title="新建需求">+ 需求</button>
		      </div>
		      <div class="dsh-pm-lanes">${r}</div>
		      ${o}
		    </div>`}function m(t){let{req:n,tasks:r,doneCount:i,totalCount:a,readyIds:o,blocked:s}=t,l=a>0?Math.round(i/a*100):0,u=n.category?`<span class="dsh-pm-cat" data-cat="${n.category}">${c[n.category]??n.category}</span>`:``,f=s?`<span class="dsh-pm-flag blocked">阻塞</span>`:``,p=n.paused?`<span class="dsh-pm-flag paused">暂停</span>`:``,m=o.length>0?`<span class="dsh-pm-flag ready">${o.length} ready</span>`:``,g=h(r);return`
		    <div class="dsh-pm-card${s?` is-blocked`:``}" data-req="${(0,e.esc)(n.id)}" data-action="open-req">
		      <div class="dsh-pm-card-top">
		        <span class="dsh-pm-card-id">${(0,e.esc)(n.id)}</span>
		        ${u}${f}${p}${m}
		      </div>
		      <div class="dsh-pm-card-title">${(0,e.esc)(n.title)}</div>
		      <div class="dsh-pm-card-progress">
		        <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${l}%"></div></div>
		        <span class="dsh-pm-card-pct">${d(i,a)}</span>
		      </div>
		      ${g}
		    </div>`}function h(t){for(let n=t.length-1;n>=0;n--){let r=t[n].executions;for(let t=r.length-1;t>=0;t--){let n=r[t].sessionId;if(n)return`<button type="button" class="dsh-pm-session" data-action="jump-session" data-sid="${(0,e.esc)(n)}" title="跳转到执行会话">会话 ${(0,e.esc)(n.slice(0,12))}…</button>`}}return``}function g(t,n){let r=n.filter(e=>e.requirementId===t.id),i=v(r),o=y(r),s=b(t.comments),c=_(t.status);return`
		    <div class="dsh-pm-detail" data-detail-req="${(0,e.esc)(t.id)}">
		      <div class="dsh-pm-detail-head">
		        <button type="button" class="dsh-pm-btn" data-action="back" title="返回看板">← 看板</button>
		        <span class="dsh-pm-card-id">${(0,e.esc)(t.id)}</span>
		        <span class="dsh-pm-status" data-status="${t.status}">${a[t.status]}</span>
		        ${t.blocked?`<span class="dsh-pm-flag blocked">阻塞</span>`:``}
		        <span class="dsh-pm-detail-updated">${u(t.updatedAt)}</span>
		      </div>
		      <h2 class="dsh-pm-detail-title">${(0,e.esc)(t.title)}</h2>
		      ${t.description?`<div class="dsh-pm-detail-desc">${(0,e.esc)(t.description)}</div>`:``}
		      ${c}
		      <div class="dsh-pm-detail-section">
		        <h3>任务 DAG</h3>
		        ${i}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>任务（${r.length}）</h3>
		        ${o}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>评论（${t.comments.length}）</h3>
		        ${s}
		        <div class="dsh-pm-comment-form">
		          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
		          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="req" data-id="${(0,e.esc)(t.id)}">发送</button>
		        </div>
		      </div>
		    </div>`}function _(e){return{reviewing:`<div class="dsh-pm-gate">人工闸门：方案确认后进入拆分 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">确认方案</button></div>`,decomposing:`<div class="dsh-pm-gate">人工闸门：DAG 确认后进入实施 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="implementing">确认拆分</button></div>`,accepting:`<div class="dsh-pm-gate">人工闸门：验收通过后完成 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="done">验收通过</button></div>`,done:`<div class="dsh-pm-gate">人工闸门：归档归集文档 <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="archived">归档</button></div>`}[e]??``}function v(t){if(t.length===0)return`<div class="dsh-pm-empty">暂无任务</div>`;let n=new Map,r=new Map(t.map(e=>[e.id,e])),i=(e,t)=>{if(n.has(e.id))return n.get(e.id);if(t.has(e.id))return 0;t.add(e.id);let a=e.dependsOn.filter(e=>r.has(e)),o=a.length===0?0:1+Math.max(...a.map(e=>i(r.get(e),t)));return n.set(e.id,o),o};t.forEach(e=>i(e,new Set));let a=Math.max(...n.values()),o=Array.from({length:a+1},()=>[]);return t.forEach(e=>o[n.get(e.id)].push(e)),`<div class="dsh-pm-dag">`+o.map((t,n)=>`
		    <div class="dsh-pm-dag-layer">
		      <span class="dsh-pm-dag-layer-label">L${n}</span>
		      ${t.map(t=>`
		        <span class="dsh-pm-dag-node" data-status="${t.status}" data-action="open-task" data-task="${(0,e.esc)(t.id)}" title="${(0,e.esc)(t.title)}">
		          ${(0,e.esc)(t.id)} ${(0,e.esc)(t.title.slice(0,20))}${t.title.length>20?`…`:``}
		        </span>`).join(``)}
		    </div>`).join(``)+`</div>`}function y(t){return t.length===0?`<div class="dsh-pm-empty">暂无任务</div>`:`<div class="dsh-pm-taskcols">`+[`todo`,`in_progress`,`integrating`,`testing`,`in_review`,`done`].map(n=>{let r=t.filter(e=>e.status===n);return`
		      <div class="dsh-pm-taskcol" data-col="${n}">
		        <div class="dsh-pm-taskcol-head">${o[n]} ${r.length}</div>
		        ${r.map(t=>`
		          <div class="dsh-pm-task" data-task="${(0,e.esc)(t.id)}" data-action="open-task">
		            <div class="dsh-pm-task-title">${(0,e.esc)(t.title)}</div>
		            <div class="dsh-pm-task-meta">
		              <span class="dsh-pm-phase">${s[t.phase]??t.phase}</span>
		              ${t.blocked?`<span class="dsh-pm-flag blocked">阻塞</span>`:``}
		            </div>
		          </div>`).join(``)}
		      </div>`}).join(``)+`</div>`}function b(t){return t.length===0?`<div class="dsh-pm-empty">暂无评论</div>`:`<div class="dsh-pm-comments">`+t.map(t=>`
		    <div class="dsh-pm-comment">
		      <span class="dsh-pm-comment-meta">${(0,e.esc)(t.createdBy?.kind??`human`)} · ${u(t.createdAt)}</span>
		      <div class="dsh-pm-comment-body">${(0,e.esc)(t.body)}</div>
		    </div>`).join(``)+`</div>`}function x(t,n){let r=t.executions.map(t=>`
		    <div class="dsh-pm-exec" data-outcome="${t.outcome}">
		      <span class="dsh-pm-exec-outcome">${t.outcome}</span>
		      <span>${u(t.startedAt)}</span>
		      ${t.sessionId?`<button type="button" class="dsh-pm-session" data-action="jump-session" data-sid="${(0,e.esc)(t.sessionId)}">会话 ${(0,e.esc)(t.sessionId.slice(0,12))}…</button>`:``}
		      ${t.error?`<div class="dsh-pm-exec-error">${(0,e.esc)(t.error)}</div>`:``}
		      ${t.evidence&&t.evidence.length>0?`<div class="dsh-pm-exec-evidence">${t.evidence.map(t=>`<code>${(0,e.esc)(t)}</code>`).join(` `)}</div>`:``}
		    </div>`).join(``);return`
		    <div class="dsh-pm-taskdetail" data-detail-task="${(0,e.esc)(t.id)}">
		      <div class="dsh-pm-detail-head">
		        <button type="button" class="dsh-pm-btn" data-action="back-req" data-req="${(0,e.esc)(t.requirementId)}" title="返回需求">← ${(0,e.esc)(t.requirementId)}</button>
		        <span class="dsh-pm-card-id">${(0,e.esc)(t.id)}</span>
		        <span class="dsh-pm-status" data-status="${t.status}">${o[t.status]}</span>
		      </div>
		      <h2 class="dsh-pm-detail-title">${(0,e.esc)(t.title)}</h2>
		      ${t.description?`<div class="dsh-pm-detail-desc">${(0,e.esc)(t.description)}</div>`:``}
		      <div class="dsh-pm-detail-section">
		        <h3>属性</h3>
		        <div class="dsh-pm-kv">
		          <span>阶段</span><span>${s[t.phase]??t.phase}</span>
		          <span>端侧</span><span>${t.side}</span>
		          <span>依赖</span><span>${t.dependsOn.length>0?t.dependsOn.map(e.esc).join(`, `):`无`}</span>
		          <span>验收标准</span><span>${(0,e.esc)(t.acceptance)}</span>
		        </div>
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>执行记录（${t.executions.length}）</h3>
		        ${r||`<div class="dsh-pm-empty">暂无执行</div>`}
		      </div>
		      <div class="dsh-pm-detail-section">
		        <h3>评论（${t.comments.length}）</h3>
		        ${b(t.comments)}
		        <div class="dsh-pm-comment-form">
		          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
		          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="task" data-id="${(0,e.esc)(t.id)}">发送</button>
		        </div>
		      </div>
		    </div>`}function S(t,n){let r=t.filter(e=>e.status===`pending`),i=n.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`),a=r.map(t=>{let n=t.suggestedTargetId?`${t.suggestedAction===`bind_req`?`绑定需求`:t.suggestedAction===`bind_task`?`绑定任务`:`新建需求`} ${(0,e.esc)(t.suggestedTargetId)}`:t.suggestedAction===`create_req`?`新建需求`:``;return`
		      <div class="dsh-pm-triage" data-triage="${(0,e.esc)(t.id)}">
		        <div class="dsh-pm-triage-head">
		          <span class="dsh-pm-session-id">${(0,e.esc)(t.sessionId.slice(0,16))}…</span>
		          <span class="dsh-pm-triage-score">分 ${t.score}</span>
		          <span class="dsh-pm-triage-suggest">${n}</span>
		        </div>
		        <div class="dsh-pm-triage-text">${(0,e.esc)(t.firstMessageText.slice(0,200))}${t.firstMessageText.length>200?`…`:``}</div>
		        <div class="dsh-pm-triage-actions">
		          <button type="button" class="dsh-pm-btn primary" data-action="triage-confirm" data-triage="${(0,e.esc)(t.id)}">确认</button>
		          <button type="button" class="dsh-pm-btn" data-action="triage-rebind" data-triage="${(0,e.esc)(t.id)}">改绑</button>
		          <button type="button" class="dsh-pm-btn" data-action="triage-reject" data-triage="${(0,e.esc)(t.id)}">拒绝</button>
		        </div>
		      </div>`}).join(``);return`
		    <div class="dsh-pm-triage-panel">
		      <div class="dsh-pm-detail-head">
		        <span class="dsh-pm-title-sm">待归类（${r.length}）</span>
		        <span class="dsh-pm-hint">新会话自动捕获，确认后进入流水线</span>
		      </div>
		      ${a||`<div class="dsh-pm-empty">暂无待归类会话</div>`}
		      <div class="dsh-pm-rebind-host" style="display:none">
		        <select class="dsh-pm-input" data-role="rebind-select">
		          ${i.map(t=>`<option value="${(0,e.esc)(t.id)}">${(0,e.esc)(t.id)} ${(0,e.esc)(t.title.slice(0,30))}</option>`).join(``)}
		        </select>
		        <button type="button" class="dsh-pm-btn primary" data-action="triage-rebind-confirm">确认改绑</button>
		      </div>
		    </div>`}function C(){return`<div class="dsh-pm-board"><div class="dsh-pm-empty">暂无数据 — 点击「+ 需求」创建第一个需求</div></div>`}function w(t){return`<div class="dsh-pm-board"><div class="dsh-pm-error">加载失败：${(0,e.esc)(t)}</div></div>`}const T=8e3;var E=class extends Error{code;constructor(e,t){super(e),this.code=t}};async function D(e){if(!e.ok)throw new E(`HTTP `+e.status);let t=await e.json().catch(()=>({}));if(t.success!==!0)throw new E(t.error??`API 返回失败`,t.code);return t.data}const O=e=>D(fetch(e,{signal:AbortSignal.timeout(T)})),k=(e,t)=>D(fetch(e,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify(t),signal:AbortSignal.timeout(T)})),A=()=>O(`/dashboard/api/reqboard/`),j=()=>O(`/dashboard/api/reqboard/triage`);function M(e){return k(`/dashboard/api/reqboard/req/create`,e)}function N(e){return k(`/dashboard/api/reqboard/req/move`,e)}function P(e){return k(`/dashboard/api/reqboard/comment`,e)}function F(e){return k(`/dashboard/api/reqboard/triage/confirm`,e)}function I(e){return k(`/dashboard/api/reqboard/triage/rebind`,e)}function L(e){return k(`/dashboard/api/reqboard/triage/reject`,e)}function R(e){let t=new EventSource(`/dashboard/api/reqboard/events`);return t.onmessage=t=>{try{let n=JSON.parse(t.data);e(n.revision,n.kind)}catch{}},()=>t.close()}function z(){let e=()=>window;return{getSessions:()=>{try{let t=e().__dshPmSessions??e().__dshPmCtx?.sessions;if(t&&typeof t.open==`function`&&t.list)return t}catch{}},getWorkspaces:()=>{try{let t=e().__dshPmWorkspaces??e().__dshPmCtx?.workspaces;if(t&&t.list)return t}catch{}}}}async function B(e,t){let n=e.getSessions();if(n===void 0)return`unavailable`;let r=e=>{try{return n.list.getSnapshot().byId[e]!==void 0}catch{return!1}};if(r(t))return(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`);try{await n.refresh()}catch{}return r(t)?(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`):`missing`}function V(){return{openBoard:()=>{},closeBoard:()=>{},toggleBoard:()=>{},getSnapshot:()=>({boardOpen:!1}),refresh:()=>{}}}function H(t){let r,a=[],o={kind:`board`},s,c,l=()=>{if(s!==void 0){if(r===void 0){s.innerHTML=C();return}switch(o.kind){case`board`:s.innerHTML=p(r);break;case`req`:{let e=r.requirements.find(e=>e.id===o.reqId);s.innerHTML=e?g(e,r.tasks):p(r),e||(o={kind:`board`});break}case`task`:{let e=r.tasks.find(e=>e.id===o.taskId),t=e?r.requirements.find(t=>t.id===e.requirementId):void 0;s.innerHTML=e?x(e,t):p(r),e||(o={kind:`board`});break}case`triage`:s.innerHTML=S(a,r)}}},u=async()=>{try{let[e,t]=await Promise.all([A(),j()]);r=e,a=t.pending,l()}catch(e){s!==void 0&&(s.innerHTML=w(String(e)))}},d=()=>{c?.(),c=R(()=>{u()})},f=e=>{let t=e.target.closest(`[data-action]`);if(t!==null&&r!==void 0)switch(t.dataset.action??``){case`refresh`:u();return;case`new-req`:{let e=window.prompt(`需求标题`);e&&e.trim()&&M({title:e.trim()}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`open-req`:t.dataset.req&&(o={kind:`req`,reqId:t.dataset.req},l());return;case`open-task`:t.dataset.task&&(o={kind:`task`,taskId:t.dataset.task},l());return;case`back`:o={kind:`board`},l();return;case`back-req`:o={kind:`req`,reqId:t.dataset.req??``},l();return;case`move-req`:{let e=r.requirements.find(e=>o.kind===`req`&&e.id===o.reqId)?.id,n=t.dataset.to;e&&n&&N({id:e,to:n,actor:`human`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`add-comment`:{let e=(s?.querySelector(`[data-role="comment-input"]`))?.value.trim();e&&t.dataset.target&&t.dataset.id&&P({target:t.dataset.target,id:t.dataset.id,body:e,actor:`human`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`jump-session`:{let e=t.dataset.sid;e&&B(z(),e).then(e=>{e===`archived`?window.alert(`该会话已归档（日志保留，侧栏不可见）`):e===`missing`?window.alert(`该会话不在当前列表（可能已删除）`):e===`unavailable`&&window.alert(`会话服务暂不可用`)});return}case`triage-confirm`:{let e=t.dataset.triage;if(!e)return;let n=a.find(t=>t.id===e);n?.suggestedAction===`bind_req`&&n.suggestedTargetId?F({triageId:e,action:`bind_req`,targetId:n.suggestedTargetId}).then(()=>u()).catch(e=>window.alert(String(e))):F({triageId:e,action:`create_req`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`triage-rebind`:{let e=s?.querySelector(`.dsh-pm-rebind-host`);e&&(e.style.display=`flex`,e.dataset.triage=t.dataset.triage??``);return}case`triage-rebind-confirm`:{let e=s?.querySelector(`.dsh-pm-rebind-host`),t=e?.dataset.triage,n=e?.querySelector(`[data-role="rebind-select"]`);t&&n?.value&&I({triageId:t,targetId:n.value}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`triage-reject`:{let e=t.dataset.triage;e&&L({triageId:e}).then(()=>u()).catch(e=>window.alert(String(e)));return}}},m=(0,e.createBoardShell)({prefix:`dsh-pm`,panelName:n,activeAttr:`data-dsh-pm-active`,otherActiveAttrs:i,pollMs:2e4,pauseOnHidden:!0,buildContainer:()=>{let e=document.createElement(`div`);return e.dataset.dshPmView=``,e.className=`dsh-pm-view`,e},onMount:e=>(s=e,e.addEventListener(`click`,f),u(),d(),()=>{e.removeEventListener(`click`,f),c?.(),c=void 0,s=void 0}),onPoll:()=>{u()},onOpen:()=>{u()}}),h=t;return h.openBoard=m.open,h.closeBoard=m.close,h.toggleBoard=m.toggle,h.getSnapshot=()=>({boardOpen:m.isActive()}),h.refresh=()=>{u()},()=>{m.dispose()}}const U=`dsh-pmboard/footer-action.css`,W=`dsh-pmboard:open-board`,G=(0,t.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,t.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,t.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,t.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,t.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function K(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${U}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=U,e.textContent=`
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
		`,document.head.appendChild(e)}function q(e){let{wide:n}=e,i=r;return(0,t.createElement)(`button`,{type:`button`,className:n?`dsh-reqboard-foot wide`:`dsh-reqboard-foot rail`,title:i,"aria-label":i,onClick:()=>{window.dispatchEvent(new CustomEvent(W,{detail:{open:!0}}))}},n?[(0,t.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},G),(0,t.createElement)(`span`,{className:`dsh-reqboard-foot-label`,key:`l`},i)]:(0,t.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},G))}const J=`dsh-pmboard/styles.css`;function Y(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${J}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=J,e.textContent=`
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
		  position: absolute; inset: 0;
		  background: var(--dsw-bg-primary, #fff);
		  z-index: 10;
		  flex-direction: column;
		  overflow: hidden;
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
		.dsh-pm-lane-dot[data-status="reviewing"] { background: #f0a020; }
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
		.dsh-pm-triage-actions { display: flex; gap: 8px; }
		.dsh-pm-rebind-host { display: flex; gap: 8px; margin-top: 8px; }
		`,document.head.appendChild(e)}const X=[`slots`,`sessions`,`workspaces`];function Z(e){try{K(),Y(),window.__dshReqboardClient?.dispose(),window.__dshPmCtx=e,window.__dshPmSessions=e.sessions,window.__dshPmWorkspaces=e.workspaces;let t=V(),i=H(t),a=e=>{e.detail?.open===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(W,a),window.__dshReqboardClient={dispose:()=>{window.removeEventListener(W,a),i(),t.closeBoard(),delete window.__dshPmCtx,delete window.__dshPmSessions,delete window.__dshPmWorkspaces}};let o=e.slots;o?o.inject(`sidebar.footer.action`,()=>o.register({name:`sidebar.footer.action`,id:n,order:110,label:r},q)):console.warn(`[dsh-pmboard] ctx.slots unavailable`)}catch(e){console.error(`[dsh-pmboard] client half failed to start:`,e)}}exports.apply=Z,exports.inject=X,exports.name=`dsh-pmboard/client`;
			return module.exports;
		}
	});

