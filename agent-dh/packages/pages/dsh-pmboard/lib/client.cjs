Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");const t=`dsh-panel-activate`;function n(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}function r(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}function i(e){let{panelName:r,activeAttr:i,otherActiveAttrs:a,pollMs:o=3e4,pauseOnHidden:s=!1,dispatchTarget:c=`window`,listenTarget:l=`window`,buildContainer:u,onMount:d,onPoll:f,onOpen:p,onClose:m}=e,h=!1,g,_,v,y=!1,b=()=>{if(g!==void 0||y)return;let e=n();if(e===void 0)return;let t=u();e.appendChild(t),g=t,v=d(t)??void 0},x=new MutationObserver(()=>{b()});x.observe(document.body,{childList:!0,subtree:!0}),b();let S=()=>{if(!(h||y)){h=!0,b();for(let e of a)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(i,``),(c===`document`?document:window).dispatchEvent(new CustomEvent(t,{detail:r})),D(),p?.()}},C=()=>{!h||y||(h=!1,document.documentElement.removeAttribute(i),O(),m?.())},w=()=>{h?C():S()},T=()=>h,E=()=>{h&&f()},D=()=>{O(),_=window.setInterval(E,o)},O=()=>{_!==void 0&&(clearInterval(_),_=void 0)},k=()=>{document.hidden?O():h&&D()};s&&document.addEventListener(`visibilitychange`,k);let A=t=>{if(!h)return;let n=t.target;if(n===null||g!==void 0&&(g===n||g.contains(n)))return;let r=`[data-`+e.prefix+`-entry]`;n.closest(r)===null&&C()};document.addEventListener(`click`,A,!0);let j=e=>{let t=e.detail;t!==void 0&&t!==r&&h&&C()},M=l===`document`?document:window;return M.addEventListener(t,j),{open:S,close:C,toggle:w,isActive:T,dispose:()=>{y||(y=!0,O(),s&&document.removeEventListener(`visibilitychange`,k),document.removeEventListener(`click`,A,!0),M.removeEventListener(t,j),x.disconnect(),v?.(),g?.remove(),g=void 0)}}}const a=`dsh-pmboard`,o=`项目看板`,s=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`,`data-dsh-bbd-active`,`data-dsh-gen-active`,`data-dsh-exec-active`],c={draft:`立项`,reviewing:`评审`,decomposing:`拆分`,implementing:`实施`,accepting:`验收`,done:`完成`,archived:`归档`,canceled:`取消`},l={todo:`待办`,in_progress:`进行中`,integrating:`联调`,testing:`测试`,in_review:`验收`,done:`完成`,canceled:`取消`},u={doc:`文档`,ui:`UI`,analysis:`分析`,implement:`实施`,test:`测试`,review:`评审`,merge:`合并`},d={feature:`功能`,bug:`缺陷`,doc:`文档`,refactor:`重构`,spike:`调研`,chore:`杂项`},f=[`draft`,`reviewing`,`decomposing`,`implementing`,`accepting`,`done`];function p(e){let t=e.startsWith(`session-`)?e.slice(8):e;return`w-${(t.split(`-`)[0]??t).slice(0,8)}`}const m=e=>{let t=new Date(e),n=e=>String(e).padStart(2,`0`);return`${t.getMonth()+1}-${n(t.getDate())} ${n(t.getHours())}:${n(t.getMinutes())}`};function h(e,t){return t===0?`0/0`:`${e}/${t}`}function g(e){return e.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`).map(t=>{let n=e.tasks.filter(e=>e.requirementId===t.id);return{req:t,tasks:n,doneCount:n.filter(e=>e.status===`done`).length,totalCount:n.length,readyIds:e.ready[t.id]??[],blocked:t.blocked||n.some(e=>e.blocked)}})}function _(e){let t=g(e),n=f.map(e=>{let n=t.filter(t=>t.req.status===e),r=n.map(e=>v(e)).join(``);return`
      <div class="dsh-pm-lane" data-lane="${e}">
        <div class="dsh-pm-lane-head">
          <span class="dsh-pm-lane-dot" data-status="${e}"></span>
          <span class="dsh-pm-lane-title">${c[e]}</span>
          <span class="dsh-pm-lane-count">${n.length}</span>
        </div>
        <div class="dsh-pm-lane-cards">${r}</div>
      </div>`}).join(``),i=e.requirements.filter(e=>e.status===`archived`||e.status===`canceled`),a=i.length>0?`<div class="dsh-pm-archived-bar">
         <span class="dsh-pm-archived-label">归档/取消 ${i.length}</span>
         ${i.map(e=>`<span class="dsh-pm-archived-chip" data-status="${e.status}">${r(e.id)} ${r(e.title)}</span>`).join(``)}
       </div>`:``;return`
    <div class="dsh-pm-board">
      <div class="dsh-pm-head">
        <h1 class="dsh-pm-title">项目看板</h1>
        <span class="dsh-pm-rev">rev ${e.revision}</span>
        <button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button>
        <button type="button" class="dsh-pm-btn primary" data-action="new-req" title="新建需求">+ 需求</button>
      </div>
      <div class="dsh-pm-lanes">${n}</div>
      ${a}
    </div>`}function v(e){let{req:t,tasks:n,doneCount:i,totalCount:a,readyIds:o,blocked:s}=e,c=a>0?Math.round(i/a*100):0,l=t.category?`<span class="dsh-pm-cat" data-cat="${t.category}">${d[t.category]??t.category}</span>`:``,u=s?`<span class="dsh-pm-flag blocked">阻塞</span>`:``,f=t.paused?`<span class="dsh-pm-flag paused">暂停</span>`:``,p=o.length>0?`<span class="dsh-pm-flag ready">${o.length} ready</span>`:``,m=y(t)+b(n);return`
    <div class="dsh-pm-card${s?` is-blocked`:``}" data-req="${r(t.id)}" data-action="open-req">
      <div class="dsh-pm-card-top">
        <span class="dsh-pm-card-id">${r(t.id)}</span>
        ${l}${u}${f}${p}
      </div>
      <div class="dsh-pm-card-title">${r(t.title)}</div>
      <div class="dsh-pm-card-progress">
        <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${c}%"></div></div>
        <span class="dsh-pm-card-pct">${h(i,a)}</span>
      </div>
      ${m}
    </div>`}function y(e){let t=e.sourceSessionId;if(!t)return``;let n=p(t);return`<button type="button" class="dsh-pm-window" data-action="jump-session" data-sid="${r(t)}" title="立项来源窗口（点击跳转到该会话）：${r(t)}">窗口 ${r(n)}</button>`}function b(e){for(let t=e.length-1;t>=0;t--){let n=e[t].executions;for(let e=n.length-1;e>=0;e--){let t=n[e].sessionId;if(t)return`<button type="button" class="dsh-pm-session" data-action="jump-session" data-sid="${r(t)}" title="跳转到执行会话">会话 ${r(t.slice(0,12))}…</button>`}}return``}function x(e,t){let n=t.filter(t=>t.requirementId===e.id),i=C(n),a=w(n),o=T(e.comments),s=S(e.status);return`
    <div class="dsh-pm-detail" data-detail-req="${r(e.id)}">
      <div class="dsh-pm-detail-head">
        <button type="button" class="dsh-pm-btn" data-action="back" title="返回看板">← 看板</button>
        <span class="dsh-pm-card-id">${r(e.id)}</span>
        <span class="dsh-pm-status" data-status="${e.status}">${c[e.status]}</span>
        ${e.blocked?`<span class="dsh-pm-flag blocked">阻塞</span>`:``}
        ${y(e)}
        <span class="dsh-pm-detail-updated">${m(e.updatedAt)}</span>
      </div>
      <h2 class="dsh-pm-detail-title">${r(e.title)}</h2>
      ${e.description?`<div class="dsh-pm-detail-desc">${r(e.description)}</div>`:``}
      ${s}
      <div class="dsh-pm-detail-section">
        <h3>任务 DAG</h3>
        ${i}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>任务（${n.length}）</h3>
        ${a}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>评论（${e.comments.length}）</h3>
        ${o}
        <div class="dsh-pm-comment-form">
          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="req" data-id="${r(e.id)}">发送</button>
        </div>
      </div>
    </div>`}function S(e){return{draft:`<div class="dsh-pm-gate">需求已立项：窗口接手开工后自动进入评审 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="reviewing">提交评审</button></div>`,reviewing:`<div class="dsh-pm-gate">人工闸门：方案确认后进入拆分 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="decomposing">确认方案</button></div>`,decomposing:`<div class="dsh-pm-gate">人工闸门：DAG 确认后进入实施 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="implementing">确认拆分</button></div>`,accepting:`<div class="dsh-pm-gate">人工闸门：验收通过后完成 <button type="button" class="dsh-pm-btn primary" data-action="move-req" data-to="done">验收通过</button></div>`,done:`<div class="dsh-pm-gate">人工闸门：归档归集文档 <button type="button" class="dsh-pm-btn" data-action="move-req" data-to="archived">归档</button></div>`}[e]??``}function C(e){if(e.length===0)return`<div class="dsh-pm-empty">暂无任务</div>`;let t=new Map,n=new Map(e.map(e=>[e.id,e])),i=(e,r)=>{if(t.has(e.id))return t.get(e.id);if(r.has(e.id))return 0;r.add(e.id);let a=e.dependsOn.filter(e=>n.has(e)),o=a.length===0?0:1+Math.max(...a.map(e=>i(n.get(e),r)));return t.set(e.id,o),o};e.forEach(e=>i(e,new Set));let a=Math.max(...t.values()),o=Array.from({length:a+1},()=>[]);return e.forEach(e=>o[t.get(e.id)].push(e)),`<div class="dsh-pm-dag">`+o.map((e,t)=>`
    <div class="dsh-pm-dag-layer">
      <span class="dsh-pm-dag-layer-label">L${t}</span>
      ${e.map(e=>`
        <span class="dsh-pm-dag-node" data-status="${e.status}" data-action="open-task" data-task="${r(e.id)}" title="${r(e.title)}">
          ${r(e.id)} ${r(e.title.slice(0,20))}${e.title.length>20?`…`:``}
        </span>`).join(``)}
    </div>`).join(``)+`</div>`}function w(e){return e.length===0?`<div class="dsh-pm-empty">暂无任务</div>`:`<div class="dsh-pm-taskcols">`+[`todo`,`in_progress`,`integrating`,`testing`,`in_review`,`done`].map(t=>{let n=e.filter(e=>e.status===t);return`
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
      </div>`}).join(``)+`</div>`}function T(e){return e.length===0?`<div class="dsh-pm-empty">暂无评论</div>`:`<div class="dsh-pm-comments">`+e.map(e=>`
    <div class="dsh-pm-comment">
      <span class="dsh-pm-comment-meta">${r(e.createdBy?.kind??`human`)} · ${m(e.createdAt)}</span>
      <div class="dsh-pm-comment-body">${r(e.body)}</div>
    </div>`).join(``)+`</div>`}function E(e,t){let n=e.executions.map(e=>`
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
        <h3>执行记录（${e.executions.length}）</h3>
        ${n||`<div class="dsh-pm-empty">暂无执行</div>`}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>评论（${e.comments.length}）</h3>
        ${T(e.comments)}
        <div class="dsh-pm-comment-form">
          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论…" />
          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="task" data-id="${r(e.id)}">发送</button>
        </div>
      </div>
    </div>`}function D(e,t){let n=e.filter(e=>e.status===`pending`),i=t.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`),a=n.map(e=>{let t=e.suggestedAction===`create_req`&&!e.suggestedTargetId,n=e.suggestedTargetId?`${e.suggestedAction===`bind_req`?`绑定需求`:e.suggestedAction===`bind_task`?`绑定任务`:`新建需求`} ${r(e.suggestedTargetId)}`:e.suggestedAction===`create_req`?`新建需求${e.suggestedCategory?` · ${d[e.suggestedCategory]??e.suggestedCategory}`:``}`:``,i=t?`
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
    </div>`}function O(){return`<div class="dsh-pm-board"><div class="dsh-pm-empty">暂无数据 — 点击「+ 需求」创建第一个需求</div></div>`}function k(e){return`<div class="dsh-pm-board"><div class="dsh-pm-error">加载失败：${r(e)}</div></div>`}const A=8e3;var j=class extends Error{code;constructor(e,t){super(e),this.code=t}};async function M(e){let t=await e;if(!t.ok)throw new j(`HTTP `+t.status);let n=await t.json().catch(()=>({}));if(n.success!==!0)throw new j(n.error??`API 返回失败`,n.code);return n.data}const N=e=>M(fetch(e,{signal:AbortSignal.timeout(A)})),P=(e,t)=>M(fetch(e,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify(t),signal:AbortSignal.timeout(A)})),F=()=>N(`/dashboard/api/reqboard/`),I=()=>N(`/dashboard/api/reqboard/triage`);function L(e){return P(`/dashboard/api/reqboard/req/create`,e)}function R(e){return P(`/dashboard/api/reqboard/req/move`,e)}function z(e){return P(`/dashboard/api/reqboard/comment`,e)}function B(e){return P(`/dashboard/api/reqboard/triage/confirm`,e)}function V(e){return P(`/dashboard/api/reqboard/triage/rebind`,e)}function H(e){return P(`/dashboard/api/reqboard/triage/reject`,e)}function U(e){let t=new EventSource(`/dashboard/api/reqboard/events`);return t.onmessage=t=>{try{let n=JSON.parse(t.data);e(n.revision,n.kind)}catch{}},()=>t.close()}function W(){let e=()=>window;return{getSessions:()=>{try{let t=e().__dshPmSessions??e().__dshPmCtx?.sessions;if(t&&typeof t.open==`function`&&t.list)return t}catch{}},getWorkspaces:()=>{try{let t=e().__dshPmWorkspaces??e().__dshPmCtx?.workspaces;if(t&&t.list)return t}catch{}}}}async function G(e,t){let n=e.getSessions();if(n===void 0)return`unavailable`;let r=e=>{try{return n.list.getSnapshot().byId[e]!==void 0}catch{return!1}};if(r(t))return(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`);try{await n.refresh()}catch{}return r(t)?(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`):`missing`}function K(){return{openBoard:()=>{},closeBoard:()=>{},toggleBoard:()=>{},getSnapshot:()=>({boardOpen:!1}),refresh:()=>{}}}function q(e){let t,n=[],r={kind:`board`},o,c,l=()=>{if(o!==void 0){if(t===void 0){o.innerHTML=O();return}switch(r.kind){case`board`:o.innerHTML=_(t);break;case`req`:{let e=t.requirements.find(e=>e.id===r.reqId);o.innerHTML=e?x(e,t.tasks):_(t),e||(r={kind:`board`});break}case`task`:{let e=t.tasks.find(e=>e.id===r.taskId),n=e?t.requirements.find(t=>t.id===e.requirementId):void 0;o.innerHTML=e?E(e,n):_(t),e||(r={kind:`board`});break}case`triage`:o.innerHTML=D(n,t)}}},u=async()=>{try{let[e,r]=await Promise.all([F(),I()]);t=e,n=r.pending,l()}catch(e){o!==void 0&&(o.innerHTML=k(String(e)))}},d=()=>{c?.(),c=U(()=>{u()})},f=e=>{let i=e.target.closest(`[data-action]`);if(i!==null&&t!==void 0)switch(i.dataset.action??``){case`refresh`:u();return;case`new-req`:{let e=window.prompt(`需求标题`);e&&e.trim()&&L({title:e.trim()}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`open-req`:i.dataset.req&&(r={kind:`req`,reqId:i.dataset.req},l());return;case`open-task`:i.dataset.task&&(r={kind:`task`,taskId:i.dataset.task},l());return;case`back`:r={kind:`board`},l();return;case`back-req`:r={kind:`req`,reqId:i.dataset.req??``},l();return;case`move-req`:{let e=t.requirements.find(e=>r.kind===`req`&&e.id===r.reqId)?.id,n=i.dataset.to;e&&n&&R({id:e,to:n,actor:`human`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`add-comment`:{let e=(o?.querySelector(`[data-role="comment-input"]`))?.value.trim();e&&i.dataset.target&&i.dataset.id&&z({target:i.dataset.target,id:i.dataset.id,body:e,actor:`human`}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`jump-session`:{let e=i.dataset.sid;e&&G(W(),e).then(e=>{e===`archived`?window.alert(`该会话已归档（日志保留，侧栏不可见）`):e===`missing`?window.alert(`该会话不在当前列表（可能已删除）`):e===`unavailable`&&window.alert(`会话服务暂不可用`)});return}case`triage-confirm`:{let e=i.dataset.triage;if(!e)return;let t=n.find(t=>t.id===e);if(t?.suggestedAction===`bind_req`&&t.suggestedTargetId)B({triageId:e,action:`bind_req`,targetId:t.suggestedTargetId}).then(()=>u()).catch(e=>window.alert(String(e)));else{let t=i.closest(`.dsh-pm-triage`),n=t?.querySelector(`[data-role="triage-title"]`)?.value.trim(),r=t?.querySelector(`[data-role="triage-category"]`)?.value;B({triageId:e,action:`create_req`,...n?{title:n}:{},...r?{category:r}:{}}).then(()=>u()).catch(e=>window.alert(String(e)))}return}case`triage-rebind`:{let e=o?.querySelector(`.dsh-pm-rebind-host`);e&&(e.style.display=`flex`,e.dataset.triage=i.dataset.triage??``);return}case`triage-rebind-confirm`:{let e=o?.querySelector(`.dsh-pm-rebind-host`),t=e?.dataset.triage,n=e?.querySelector(`[data-role="rebind-select"]`);t&&n?.value&&V({triageId:t,targetId:n.value}).then(()=>u()).catch(e=>window.alert(String(e)));return}case`triage-reject`:{let e=i.dataset.triage;e&&H({triageId:e}).then(()=>u()).catch(e=>window.alert(String(e)));return}}},p=i({prefix:`dsh-pm`,panelName:a,activeAttr:`data-dsh-pm-active`,otherActiveAttrs:s,pollMs:2e4,pauseOnHidden:!0,buildContainer:()=>{let e=document.createElement(`div`);return e.dataset.dshPmView=``,e.className=`dsh-pm-view`,e},onMount:e=>(o=e,e.addEventListener(`click`,f),u(),d(),()=>{e.removeEventListener(`click`,f),c?.(),c=void 0,o=void 0}),onPoll:()=>{u()},onOpen:()=>{u()}}),m=e;return m.openBoard=p.open,m.closeBoard=p.close,m.toggleBoard=p.toggle,m.getSnapshot=()=>({boardOpen:p.isActive()}),m.refresh=()=>{u()},()=>{p.dispose()}}const J=`dsh-pmboard/footer-action.css`,Y=`dsh-pmboard:open-board`,X=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function Z(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${J}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=J,e.textContent=`
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
`,document.head.appendChild(e)}function Q(t){let{wide:n}=t,r=o;return(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-reqboard-foot wide`:`dsh-reqboard-foot rail`,title:r,"aria-label":r,onClick:()=>{window.dispatchEvent(new CustomEvent(Y,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},X),(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-label`,key:`l`},r)]:(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},X))}const $=`dsh-pmboard/styles.css`;function ee(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${$}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=$,e.textContent=`
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
`,document.head.appendChild(e)}const te=[`slots`,`sessions`,`workspaces`];function ne(e){try{Z(),ee(),window.__dshReqboardClient?.dispose(),window.__dshPmCtx=e,window.__dshPmSessions=e.sessions,window.__dshPmWorkspaces=e.workspaces;let t=K(),n=q(t),r=e=>{e.detail?.open===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(Y,r),window.__dshReqboardClient={dispose:()=>{window.removeEventListener(Y,r),n(),t.closeBoard(),delete window.__dshPmCtx,delete window.__dshPmSessions,delete window.__dshPmWorkspaces}};let i=e.slots;i?i.inject(`sidebar.footer.action`,()=>i.register({name:`sidebar.footer.action`,id:a,order:110,label:o},Q)):console.warn(`[dsh-pmboard] ctx.slots unavailable`)}catch(e){console.error(`[dsh-pmboard] client half failed to start:`,e)}}exports.apply=ne,exports.inject=te,exports.name=`dsh-pmboard/client`;