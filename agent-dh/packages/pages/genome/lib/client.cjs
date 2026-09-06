Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});const e=`data-dsh-gen-active`,t=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`,`data-dsh-exec-active`,`data-dsh-bbd-active`],n=`dsh-panel-activate`;function r(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function i(e){let t,n=()=>{let t=document.createElement(`button`);return t.type=`button`,t.className=`dsh-gen-entry`,t.dataset.dshGenEntry=``,t.setAttribute(`aria-label`,`自主进化`),t.title=`自主进化看板 (dashboard-genome) — 基因组/候选/一致性诊断`,t.innerHTML=`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/><circle cx="12" cy="12" r="3"/></svg><span class="dsh-gen-entry-label">自主进化</span>`,t.addEventListener(`click`,t=>{t.preventDefault(),t.stopPropagation(),e.toggle()}),t},i=()=>{let e=r();if(e===void 0)return!1;if(e.querySelector(`[data-dsh-gen-entry]`)!==null){let n=e.querySelector(`[data-dsh-gen-entry]`);return n!==void 0&&t===void 0&&(t=n),!0}let i=n(),a=e.querySelector(`[class*="logoRow"]`);return a!==null&&a.nextSibling!==null?e.insertBefore(i,a.nextSibling):e.prepend(i),t=i,!0};i();let a=new MutationObserver(()=>{(t===void 0||!document.contains(t)||t.parentElement===null)&&i()});a.observe(document.body,{childList:!0,subtree:!0});let o=window.setInterval(()=>{(t===void 0||!document.contains(t))&&i()},5e3);return()=>{window.clearInterval(o),a.disconnect(),t?.remove(),t=void 0}}function a(e){return String(e??``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`).replace(/'/g,`&#39;`)}function o(e){if(!e)return`—`;let t=new Date(e);if(Number.isNaN(t.getTime()))return e;let n=e=>String(e).padStart(2,`0`);return`${t.getMonth()+1}-${n(t.getDate())} ${n(t.getHours())}:${n(t.getMinutes())}`}function s(e){if(!e)return`—`;let t=new Date(e);return Number.isNaN(t.getTime())?e:`${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,`0`)}-${String(t.getDate()).padStart(2,`0`)}`}const c={constitution:`宪法`,principles:`决策原则`,rules:`操作规则`,lessons:`经验教训`},l={constitution:`交易宪法（不可修改）`,principles:`决策原则`,rules:`操作规则`,lessons:`经验教训`},u={update:`更新`,promote:`转正`,rollback:`回滚`},d={update:`up`,promote:`ok`,rollback:`bad`},f={watching:`观察中`,promoted:`已转正`,rejected:`已拒绝`,extended:`观察延期`,unknown:`未知`},p={watching:`wait`,promoted:`ok`,rejected:`bad`,extended:`wait`,unknown:`unk`},m=[{key:`all`,label:`全部`},{key:`watching`,label:`观察中`},{key:`due`,label:`待裁决`},{key:`promoted`,label:`已转正`},{key:`rejected`,label:`已回滚/拒绝`}];let h,g=`all`;function _(e,t){switch(t){case`all`:return!0;case`watching`:return e.status===`watching`&&!e.due;case`due`:return e.due===!0;case`promoted`:return e.status===`promoted`;case`rejected`:return e.status===`rejected`;case`extended`:return e.status===`extended`;default:return!0}}function v(e,t){return`<span class="dsh-gen-badge ${t}">${a(e)}</span>`}function y(e){let t=e.consistency,n=t.healthy?v(`🟢 一致性健康`,`ok`):v(`⚠️ ${t.issues.filter(e=>e.items.length>0).length} 项异常`,`bad`),r=e.candidates.length,i=e.candidates.filter(e=>e.status===`watching`).length,c=e.candidates.filter(e=>e.due).length;return`
  <div class="dsh-gen-ov">
    <div class="dsh-gen-ov-title">
      <span class="dsh-gen-ov-big">自主进化</span>
      <span class="dsh-gen-ov-sub">Autonomy 线 · 能力设计层可观测 — 回答「改了什么规则 / 什么在试运行何时出结果 / 进化链路有无卡住」</span>
    </div>
    <div class="dsh-gen-ov-stats">
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">基因组版本</span><span class="dsh-gen-stat-v dsh-gen-gv">${a(e.genomeVersion)}</span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">段</span><span class="dsh-gen-stat-v">${e.sections.length}<small>/4</small></span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">谱系事件</span><span class="dsh-gen-stat-v">${e.history.length}</span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">候选</span><span class="dsh-gen-stat-v">${r}<small> · 观察中 ${i}${c?` · <b class="dsh-gen-warn-txt">待裁决 ${c}</b>`:``}</small></span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">一致性</span><span class="dsh-gen-stat-v">${n}</span></div>
    </div>
    <div class="dsh-gen-ov-meta">创建 ${s(e.createdAt)} · 最近更新 ${o(e.updatedAt)} · 核验 ${o(t.checkedAt)}</div>
  </div>`}function b(e){let t=e.id===`constitution`?v(`🔒 宪法层 · 锁定`,`lock`):v(`可进化`,`ev`),n=e.lastChange,r=n?`<details class="dsh-gen-exp"><summary><span class="dsh-gen-lc-head">最近：<b>${u[n.type??``]??a(n.type??``)}</b> @ ${a(n.genomeVersion??``)} · ${o(n.ts)}</span></summary><div class="dsh-gen-exp-body">${a(n.reason??`—`)}</div></details>`:`<div class="dsh-gen-lc-empty">无变更记录</div>`;return`
  <div class="dsh-gen-sec-card">
    <div class="dsh-gen-sec-head">
      <span class="dsh-gen-sec-name">${a(l[e.id]??e.id)}</span>
      ${t}
    </div>
    <div class="dsh-gen-sec-ver">v${e.version??0}</div>
    ${r}
  </div>`}function x(e){return`
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">② 段状态矩阵</span><span class="dsh-gen-block-s">4 个基因组段 · 版本与最近变更</span></div>
    <div class="dsh-gen-sec-grid">
      ${e.sections.map(b).join(``)}
    </div>
  </div>`}function S(e){if(e.items.length===0)return`<div class="dsh-gen-iss ok"><span class="dsh-gen-iss-id">${a(e.id)}</span><span class="dsh-gen-iss-t">${a(e.label)}</span><span class="dsh-gen-iss-r">✅ 通过</span></div>`;let t=e.items.map(e=>{let t=e,n=[];t.genomeVersion&&n.push(`g<code>${a(t.genomeVersion)}</code>`),t.section&&n.push(a(c[String(t.section)]??String(t.section))),t.sectionVersion&&n.push(`v${String(t.sectionVersion)}`),t.id&&n.push(`<code>${a(t.id)}</code>`),t.file&&n.push(`<code>${a(t.file)}</code>`),t.ts&&n.push(o(String(t.ts)));let r=t.reason?`<div class="dsh-gen-iss-reason">${a(t.reason)}</div>`:``;return`<div class="dsh-gen-iss-item">${n.join(` · `)}${r}</div>`}).join(``);return`
  <div class="dsh-gen-iss bad">
    <span class="dsh-gen-iss-id">${a(e.id)}</span>
    <span class="dsh-gen-iss-t">${a(e.label)}</span>
    <span class="dsh-gen-iss-r">❌ ${e.items.length} 项</span>
  </div>
  <div class="dsh-gen-iss-desc">${a(e.description)}</div>
  ${t}`}function C(e){let t=e.consistency;return`
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">③ 一致性诊断</span><span class="dsh-gen-block-s">F1 哨兵可视化仪表 · 状态一致性核验（genome.json ↔ candidates.json）</span></div>
    <div class="dsh-gen-cons-head ${t.healthy?`ok`:`bad`}">${t.healthy?`C1/C2/C3 全部通过 — 登记与落库一致，gate 有案可裁`:`检测到 ${t.issues.filter(e=>e.items.length>0).length} 类异常（F1 哨兵规则，与 gate runConsistencyCheck 同源）`}</div>
    <div class="dsh-gen-iss-list">
      ${e.consistency.issues.map(S).join(``)}
    </div>
  </div>`}function w(e){let t=c[e.section]??e.section,n=e.due?`⏰ 已过观察期 · 待 gate 裁决`:f[e.status]??e.status,r=e.due?`due`:p[e.status]??`unk`,i=``;i=(e.status===`watching`||e.due)&&e.progress!==void 0?`
    <div class="dsh-gen-cand-bar">
      <div class="dsh-gen-cand-bar-in" style="width:${Math.round((e.progress??0)*100)}%"></div>
    </div>
    <div class="dsh-gen-cand-bar-meta">${s(e.createdAt)} → ${s(e.observeUntil)} · ${e.due?`已到期`:`余 ${e.remainingDays??0} 天`}</div>`:`<div class="dsh-gen-cand-bar-meta">${s(e.createdAt)}${e.observeUntil?` → ${s(e.observeUntil)}`:``}</div>`;let l=``;if(e.healthCheck){let t=e.healthCheck.passed?`✅ 结构健康`:`❌ 结构异常`,n=[];e.healthCheck.sizeDelta!==void 0&&n.push(`diff ${e.healthCheck.sizeDelta} 字符`),e.healthCheck.issues&&e.healthCheck.issues.length>0&&n.push(...e.healthCheck.issues);let r=n.length>0?`<div class="dsh-gen-cand-hc-extra">${n.map(e=>a(e)).join(`；`)}</div>`:``;l=`<div class="dsh-gen-cand-hc">${t}${e.healthCheck.checkedAt?` · ${o(e.healthCheck.checkedAt)} 核`:``}${r}</div>`}let u=e.note?`<div class="dsh-gen-cand-note">${a(e.note)}</div>`:``,d=e.mutationType?`<span class="dsh-gen-cand-mut">${a(e.mutationType)}</span>`:``;return`
  <div class="dsh-gen-cand">
    <div class="dsh-gen-cand-head">
      <span class="dsh-gen-cand-sec">${a(t)}</span>
      <span class="dsh-gen-cand-gv">${a(e.genomeVersion)} · v${e.sectionVersion}</span>
      <span class="dsh-gen-cand-id"><code>${a(e.id)}</code></span>
      ${d}
      ${v(n,r)}
    </div>
    ${i}
    ${l}
    ${u}
  </div>`}function T(){return`<div class="dsh-gen-tabs">${m.map(e=>`<button type="button" class="dsh-gen-tab${e.key===g?` on`:``}" data-cand-filter="${e.key}">${a(e.label)}</button>`).join(``)}</div>`}function E(e){let t=e.candidates.filter(e=>_(e,g));return`<div class="dsh-gen-cand-list">${t.length===0?`<div class="dsh-gen-cand-empty">此筛选下无候选${e.candidates.length===0?`（candidates.json 暂无记录）`:``}</div>`:t.map(w).join(``)}</div>`}function D(e){return`
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">④ 候选生命周期流水线</span><span class="dsh-gen-block-s">genome_update(candidate) → 观察期 → validation_gate 裁决（转正 / 回滚）</span></div>
    ${T()}
    <div class="dsh-gen-cand-list-root">${E(e)}</div>
  </div>`}function O(e){return e.history.length===0?`<div class="dsh-gen-tl-empty">无谱系记录</div>`:`<div class="dsh-gen-tl">${e.history.map(e=>{let t=u[e.type]??a(e.type),n=d[e.type]??`unk`,r=c[e.section]??e.section,i=e.stage?v(e.stage===`candidate`?`观察版`:`正式版`,e.stage===`candidate`?`wait`:`ev`):``,s=e.gitCommit?` <code>${a(e.gitCommit)}</code>`:``,l=e.reason?`<details class="dsh-gen-exp"><summary>理由</summary><div class="dsh-gen-exp-body">${a(e.reason)}</div></details>`:``;return`
    <div class="dsh-gen-tl-item">
      <div class="dsh-gen-tl-dot ${n}"></div>
      <div class="dsh-gen-tl-main">
        <div class="dsh-gen-tl-head">
          <span class="dsh-gen-tl-gv">${a(e.genomeVersion)}</span>
          ${v(t,n)}
          <span class="dsh-gen-tl-sec">${a(r)} v${e.sectionVersion}</span>
          ${i}
          <span class="dsh-gen-tl-ts">${o(e.ts)}</span>
          ${s}
        </div>
        ${l}
      </div>
    </div>`}).join(``)}</div>`}function k(e){return`${y(e)}${x(e)}${C(e)}${D(e)}${O(e)}`}function A(){let e=document.createElement(`div`);e.className=`dsh-gen-board`;let t=document.createElement(`div`);t.className=`dsh-gen-head`;let n=document.createElement(`button`);n.type=`button`,n.className=`dsh-gen-recheck`,n.title=`重新读取 genome.json / candidates.json 并重跑 C1/C2/C3 一致性核验`,n.innerHTML=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg><span>⟳ 重检</span>`;let r=document.createElement(`div`);r.className=`dsh-gen-meta`,r.textContent=`加载中…`,t.appendChild(r),t.appendChild(n);let i=document.createElement(`div`);return i.className=`dsh-gen-body`,e.appendChild(t),e.appendChild(i),{root:e,refreshBtn:n,meta:r}}function j(e,t){h=t;let n=e.root.querySelector(`.dsh-gen-body`);n!==null&&(n.innerHTML=k(t),n.addEventListener(`click`,e=>{let t=e.target?.closest(`[data-cand-filter]`);if(t==null||h===void 0)return;g=t.dataset.candFilter??`all`;let r=n.querySelector(`.dsh-gen-tabs`),i=n.querySelector(`.dsh-gen-cand-list-root`);r!==null&&(r.outerHTML=T()),i!==null&&(i.innerHTML=E(h))}))}let M=!1;function N(){let r={boardOpen:!1},i=()=>{r.boardOpen=!0,o()},a=()=>{r.boardOpen=!1,o()},o=()=>{if(r.boardOpen){for(let e of t)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(e,``),document.dispatchEvent(new CustomEvent(n,{detail:`dashboard-genome`}))}else document.documentElement.removeAttribute(e)};return{isActive:()=>r.boardOpen,toggle:()=>{r.boardOpen?a():i()},getSnapshot:()=>r,openBoard:i,closeBoard:a}}function P(t){let r,i,a,o,s=!1,c=()=>{if(i!==void 0||s)return;let e=conversationColumn();e!==void 0&&(i=document.createElement(`div`),i.className=`dsh-gen-board`,i.dataset.dshGenView=``,e.appendChild(i),r=A(),i.appendChild(r.root),r.refreshBtn?.addEventListener(`click`,()=>{l()}),l(!0))};async function l(e=!1){if(!M){M=!0;try{let e=await(await fetch(`/dashboard/api/genome`,{headers:{Accept:`application/json`}})).json();if(!e.success||e.data===void 0)throw Error(e.error??`接口失败`);o=e.data,j(r,e.data),r.meta.textContent=`刷新于 `+new Date().toLocaleTimeString()+` · 数据 `+(e.data.fetchedAt?new Date(e.data.fetchedAt).toLocaleTimeString():``)}catch(t){r.meta.textContent=`⚠️ 加载失败: `+(t instanceof Error?t.message:String(t)),e||j(r,o)}finally{M=!1}}}let u=()=>{a===void 0&&(a=window.setInterval(()=>{l()},3e4))},d=()=>{a!==void 0&&(window.clearInterval(a),a=void 0)},f=t.openBoard,p=t.closeBoard,m=()=>{c(),u(),f()},h=()=>{d(),p()},g=t;g.openBoard=m,g.closeBoard=h,g.toggle=()=>{t.isActive()?h():m()};let _=e=>{let n=e.detail;n!==void 0&&n!==`dashboard-genome`&&t.isActive()&&h()};window.addEventListener(n,_);let v=e=>{if(!t.isActive())return;let n=e.target;n!==null&&n.closest(`[data-dsh-gen-entry], [data-dsh-gen-view]`)===null&&n.closest(`[data-pane="sidebar"]`)!==null&&n.closest(`[data-dsh-gen-entry]`)===null&&h()};return document.addEventListener(`click`,v),()=>{s=!0,d(),window.removeEventListener(n,_),document.removeEventListener(`click`,v),i?.remove(),i=void 0,document.documentElement.removeAttribute(e)}}const F=`@pi-investment/dashboard-genome/styles`;function I(){if(document.getElementById(F)!==null)return;let e=document.createElement(`style`);e.id=F,e.textContent=`
/* ===== 板容器与显隐（dsh-taskboard 契约） ===== */
.dsh-gen-board {
  display: none;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  padding: 16px 20px 40px;
  overflow-y: auto;
  font-family: var(--dsw-font, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif);
  color: var(--dsw-text-1, #1f2329);
  background: transparent;
}
html[data-dsh-gen-active] .dsh-gen-board { display: flex; }
html[data-dsh-gen-active] [data-pane="conversation"] > *:not([data-dsh-gen-view]) { display: none !important; }
html[data-dsh-gen-active] .dsh-gen-board code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  background: var(--dsw-bg-2, rgba(0,0,0,0.05));
  padding: 1px 5px;
  border-radius: 4px;
}

/* ===== 头部行 ===== */
.dsh-gen-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.dsh-gen-meta {
  flex: 1;
  font-size: 11px;
  color: var(--dsw-text-3, #8a8f99);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dsh-gen-recheck {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--dsw-border, #dcdfe6);
  border-radius: 6px;
  background: var(--dsw-bg-1, #fff);
  color: var(--dsw-text-2, #4e5969);
  font-size: 12px;
  padding: 4px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.dsh-gen-recheck:hover { border-color: var(--dsw-primary, #2f6bff); color: var(--dsw-primary, #2f6bff); }

/* ===== 徽章 ===== */
.dsh-gen-badge {
  display: inline-block;
  font-size: 11px;
  line-height: 1;
  padding: 3px 7px;
  border-radius: 10px;
  white-space: nowrap;
}
.dsh-gen-badge.ok   { background: #e1f5e8; color: #0a7d33; }
.dsh-gen-badge.bad  { background: #fde2e2; color: #c41d1d; }
.dsh-gen-badge.wait { background: #e8f0fe; color: #1d5fd6; }
.dsh-gen-badge.due  { background: #fff3d6; color: #ad6b00; }
.dsh-gen-badge.ev   { background: #e9f7fa; color: #0e7c8c; }
.dsh-gen-badge.lock { background: #efe9f7; color: #6b3fa0; }
.dsh-gen-badge.up   { background: #e8f0fe; color: #1d5fd6; }
.dsh-gen-badge.unk  { background: #f0f1f3; color: #6b7280; }

/* ===== ① 概览 ===== */
.dsh-gen-ov {
  border: 1px solid var(--dsw-border, #dcdfe6);
  border-radius: 10px;
  background: var(--dsw-bg-1, #fff);
  padding: 14px 16px;
  margin-bottom: 14px;
}
.dsh-gen-ov-title { display: flex; flex-direction: column; gap: 2px; margin-bottom: 10px; }
.dsh-gen-ov-big { font-size: 17px; font-weight: 700; }
.dsh-gen-ov-sub { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-ov-stats { display: flex; flex-wrap: wrap; gap: 22px; }
.dsh-gen-stat { display: flex; flex-direction: column; gap: 2px; }
.dsh-gen-stat-k { font-size: 10px; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-stat-v { font-size: 16px; font-weight: 700; }
.dsh-gen-stat-v small { font-size: 11px; font-weight: 400; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-gv { color: var(--dsw-primary, #2f6bff); }
.dsh-gen-warn-txt { color: #c41d1d; }
.dsh-gen-ov-meta { margin-top: 8px; font-size: 11px; color: var(--dsw-text-3, #8a8f99); }

/* ===== 通用块 ===== */
.dsh-gen-block {
  border: 1px solid var(--dsw-border, #dcdfe6);
  border-radius: 10px;
  background: var(--dsw-bg-1, #fff);
  padding: 12px 14px;
  margin-bottom: 14px;
}
.dsh-gen-block-h { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }
.dsh-gen-block-t { font-size: 13px; font-weight: 700; }
.dsh-gen-block-s { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }

/* ===== 展开（details） ===== */
.dsh-gen-exp summary {
  cursor: pointer;
  font-size: 11px;
  color: var(--dsw-text-3, #8a8f99);
  user-select: none;
}
.dsh-gen-exp summary:hover { color: var(--dsw-primary, #2f6bff); }
.dsh-gen-exp-body {
  font-size: 11px;
  line-height: 1.6;
  color: var(--dsw-text-2, #4e5969);
  background: var(--dsw-bg-2, rgba(0,0,0,0.03));
  border-radius: 6px;
  padding: 6px 8px;
  margin-top: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ===== ② 段矩阵 ===== */
.dsh-gen-sec-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; }
.dsh-gen-sec-card {
  border: 1px solid var(--dsw-border, #e5e6eb);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--dsw-bg-1, #fff);
}
.dsh-gen-sec-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.dsh-gen-sec-name { font-size: 13px; font-weight: 600; }
.dsh-gen-sec-ver { font-size: 20px; font-weight: 700; color: var(--dsw-primary, #2f6bff); }
.dsh-gen-lc-head { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-lc-empty { font-size: 11px; color: var(--dsw-text-4, #c9cdd4); }

/* ===== ③ 一致性 ===== */
.dsh-gen-cons-head {
  font-size: 12px;
  font-weight: 600;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.dsh-gen-cons-head.ok  { background: #e1f5e8; color: #0a7d33; }
.dsh-gen-cons-head.bad { background: #fde2e2; color: #c41d1d; }
.dsh-gen-iss-list { display: flex; flex-direction: column; gap: 6px; }
.dsh-gen-iss {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  border-radius: 6px;
  padding: 6px 10px;
  background: var(--dsw-bg-2, rgba(0,0,0,0.03));
}
.dsh-gen-iss.ok { background: #f3fbf5; }
.dsh-gen-iss.bad { background: #fdf4f4; }
.dsh-gen-iss-id { font-weight: 700; min-width: 26px; }
.dsh-gen-iss.ok .dsh-gen-iss-id { color: #0a7d33; }
.dsh-gen-iss.bad .dsh-gen-iss-id { color: #c41d1d; }
.dsh-gen-iss-t { flex: 1; }
.dsh-gen-iss-r { font-size: 11px; font-weight: 600; }
.dsh-gen-iss.ok .dsh-gen-iss-r { color: #0a7d33; }
.dsh-gen-iss.bad .dsh-gen-iss-r { color: #c41d1d; }
.dsh-gen-iss-desc { font-size: 11px; color: var(--dsw-text-3, #8a8f99); padding: 0 4px; }
.dsh-gen-iss-item {
  font-size: 11px;
  color: #c41d1d;
  border-left: 2px solid #e5b8b8;
  background: #fdf6f6;
  border-radius: 0 4px 4px 0;
  padding: 4px 8px;
  margin: 0 4px;
}
.dsh-gen-iss-reason { color: #8a5a5a; margin-top: 2px; word-break: break-all; }

/* ===== ④ 候选 ===== */
.dsh-gen-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.dsh-gen-tab {
  border: 1px solid var(--dsw-border, #dcdfe6);
  background: var(--dsw-bg-1, #fff);
  color: var(--dsw-text-2, #4e5969);
  border-radius: 12px;
  font-size: 11px;
  padding: 3px 10px;
  cursor: pointer;
}
.dsh-gen-tab.on { background: var(--dsw-primary, #2f6bff); border-color: var(--dsw-primary, #2f6bff); color: #fff; }
.dsh-gen-cand-list { display: flex; flex-direction: column; gap: 8px; }
.dsh-gen-cand-empty { font-size: 12px; color: var(--dsw-text-4, #c9cdd4); padding: 14px 0; text-align: center; }
.dsh-gen-cand {
  border: 1px solid var(--dsw-border, #e5e6eb);
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--dsw-bg-1, #fff);
}
.dsh-gen-cand-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dsh-gen-cand-sec { font-size: 12px; font-weight: 700; }
.dsh-gen-cand-gv { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }
.dsh-gen-cand-id { margin-left: auto; font-size: 10px; color: var(--dsw-text-4, #c9cdd4); }
.dsh-gen-cand-mut { font-size: 10px; color: #6b3fa0; border: 1px solid #d8c9ec; border-radius: 8px; padding: 1px 6px; }
.dsh-gen-cand-bar { height: 5px; border-radius: 3px; background: var(--dsw-bg-2, #e5e6eb); margin-top: 8px; overflow: hidden; }
.dsh-gen-cand-bar-in { height: 100%; background: linear-gradient(90deg, #2f6bff, #53a0ff); border-radius: 3px; }
.dsh-gen-cand-bar-meta { font-size: 10px; color: var(--dsw-text-3, #8a8f99); margin-top: 3px; }
.dsh-gen-cand-hc { font-size: 11px; color: var(--dsw-text-2, #4e5969); margin-top: 6px; }
.dsh-gen-cand-hc-extra { color: #c41d1d; font-size: 10px; }
.dsh-gen-cand-note { font-size: 11px; color: var(--dsw-text-2, #4e5969); margin-top: 6px; word-break: break-all; }

/* ===== ⑤ 时间线 ===== */
.dsh-gen-tl-empty { font-size: 12px; color: var(--dsw-text-4, #c9cdd4); padding: 10px 0; }
.dsh-gen-tl { position: relative; padding-left: 18px; }
.dsh-gen-tl::before {
  content: "";
  position: absolute;
  left: 5px; top: 4px; bottom: 4px;
  width: 1px;
  background: var(--dsw-border, #e5e6eb);
}
.dsh-gen-tl-item { position: relative; padding-bottom: 12px; }
.dsh-gen-tl-dot {
  position: absolute;
  left: -18px; top: 4px;
  width: 9px; height: 9px;
  border-radius: 50%;
  background: #c9cdd4;
  border: 2px solid var(--dsw-bg-1, #fff);
}
.dsh-gen-tl-dot.ok  { background: #0a7d33; }
.dsh-gen-tl-dot.up  { background: #2f6bff; }
.dsh-gen-tl-dot.bad { background: #c41d1d; }
.dsh-gen-tl-main { display: flex; flex-direction: column; gap: 3px; }
.dsh-gen-tl-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dsh-gen-tl-gv { font-size: 12px; font-weight: 700; color: var(--dsw-primary, #2f6bff); }
.dsh-gen-tl-sec { font-size: 12px; font-weight: 600; }
.dsh-gen-tl-ts { font-size: 10px; color: var(--dsw-text-4, #c9cdd4); margin-left: auto; }

/* ===== 侧栏入口 ===== */
.dsh-gen-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  width: calc(100% - 16px);
  margin: 4px 8px;
  padding: 7px 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--dsw-text-2, #4e5969);
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  box-sizing: border-box;
}
.dsh-gen-entry:hover { background: var(--dsw-bg-2, rgba(0,0,0,0.06)); color: var(--dsw-primary, #2f6bff); }
html[data-dsh-gen-active] .dsh-gen-entry { background: var(--dsw-primary, #2f6bff); color: #fff; }
html[data-dsh-gen-active] [data-dsh-gen-entry] svg { stroke: #fff; }
.dsh-gen-entry svg { flex: none; stroke: var(--dsw-text-2, #4e5969); }
html[data-dsh-gen-active] [data-dsh-gen-entry] { background: color-mix(in srgb, var(--dsw-primary, #2f6bff) 14%, transparent); }
[data-sidebar-collapsed] .dsh-gen-entry,
[class*="_collapsed"] .dsh-gen-entry { justify-content: center; width: 36px; margin: 4px auto; padding: 7px 0; }
[data-sidebar-collapsed] .dsh-gen-entry .dsh-gen-entry-label,
[class*="_collapsed"] .dsh-gen-entry .dsh-gen-entry-label { display: none; }
`,document.head.appendChild(e)}const L=[],R=`__dshGenomeClient`;function z(){if(window[R]!==void 0)try{window[R].dispose()}catch{}I();let e=N(),t=i(e),n=P(e);window[R]={dispose:()=>{try{t(),n()}catch{}}},console.log(`[dashboard-genome] client applied — 侧栏「自主进化」入口就绪`)}exports.apply=z,exports.inject=L,exports.name=`@pi-investment/dashboard-genome/client`;