window.__ModuleLoader__.load({
		id: "@pi-investment/dashboard-genome",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});const e=`data-dsh-gen-active`,t=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`,`data-dsh-exec-active`,`data-dsh-bbd-active`],n=`dsh-panel-activate`;function r(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function i(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}function a(e){let t,n=()=>{let t=document.createElement(`button`);return t.type=`button`,t.className=`dsh-gen-entry`,t.dataset.dshGenEntry=``,t.setAttribute(`aria-label`,`自主进化`),t.title=`自主进化看板 (dashboard-genome) — 基因组/候选/一致性诊断`,t.innerHTML=`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/><circle cx="12" cy="12" r="3"/></svg><span class="dsh-gen-entry-label">自主进化</span>`,t.addEventListener(`click`,t=>{t.preventDefault(),t.stopPropagation(),e.toggle()}),t},i=()=>{let e=r();if(e===void 0)return!1;if(e.querySelector(`[data-dsh-gen-entry]`)!==null){let n=e.querySelector(`[data-dsh-gen-entry]`);return n!==void 0&&t===void 0&&(t=n),!0}let i=n(),a=e.querySelector(`[class*="logoRow"]`);return a!==null&&a.nextSibling!==null?e.insertBefore(i,a.nextSibling):e.prepend(i),t=i,!0};i();let a=new MutationObserver(()=>{(t===void 0||!document.contains(t)||t.parentElement===null)&&i()});a.observe(document.body,{childList:!0,subtree:!0});let o=window.setInterval(()=>{(t===void 0||!document.contains(t))&&i()},5e3);return()=>{window.clearInterval(o),a.disconnect(),t?.remove(),t=void 0}}function o(e){return`<button type="button" class="dsh-gen-explain" data-explain-module="${e}" title="AI 讲解：请当前 AI 介绍该区域解决什么问题、有什么作用（讲解将出现在下方会话）">🤖 讲解</button>`}function s(e){return String(e??``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`).replace(/'/g,`&#39;`)}function c(e){if(!e)return`—`;let t=new Date(e);if(Number.isNaN(t.getTime()))return e;let n=e=>String(e).padStart(2,`0`);return`${t.getMonth()+1}-${n(t.getDate())} ${n(t.getHours())}:${n(t.getMinutes())}`}function l(e){if(!e)return`—`;let t=new Date(e);return Number.isNaN(t.getTime())?e:`${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,`0`)}-${String(t.getDate()).padStart(2,`0`)}`}const u={constitution:`宪法`,principles:`决策原则`,rules:`操作规则`,lessons:`经验教训`},d={constitution:`交易宪法（不可修改）`,principles:`决策原则`,rules:`操作规则`,lessons:`经验教训`},f={update:`更新`,promote:`转正`,rollback:`回滚`},p={update:`up`,promote:`ok`,rollback:`bad`},m={watching:`观察中`,promoted:`已转正`,rejected:`已拒绝`,extended:`观察延期`,unknown:`未知`},h={watching:`wait`,promoted:`ok`,rejected:`bad`,extended:`wait`,unknown:`unk`},g=[{key:`all`,label:`全部`},{key:`watching`,label:`观察中`},{key:`due`,label:`待裁决`},{key:`promoted`,label:`已转正`},{key:`rejected`,label:`已回滚/拒绝`}];let _,v=`all`;function y(e,t){switch(t){case`all`:return!0;case`watching`:return e.status===`watching`&&!e.due;case`due`:return e.due===!0;case`promoted`:return e.status===`promoted`;case`rejected`:return e.status===`rejected`;case`extended`:return e.status===`extended`;default:return!0}}function b(e,t){return`<span class="dsh-gen-badge ${t}">${s(e)}</span>`}function x(e){let t=e.consistency,n=t.healthy?b(`🟢 一致性健康`,`ok`):b(`⚠️ ${t.issues.filter(e=>e.items.length>0).length} 项异常`,`bad`),r=e.candidates.length,i=e.candidates.filter(e=>e.status===`watching`).length,a=e.candidates.filter(e=>e.due).length;return`
		  <div class="dsh-gen-ov">
		    <div class="dsh-gen-ov-title">
		      <span class="dsh-gen-ov-big">自主进化</span>
		      <span class="dsh-gen-ov-sub">Autonomy 线 · 能力设计层可观测 — 回答「改了什么规则 / 什么在试运行何时出结果 / 进化链路有无卡住」</span>
		    </div>
		    <div class="dsh-gen-ov-stats">
		      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">基因组版本</span><span class="dsh-gen-stat-v dsh-gen-gv">${s(e.genomeVersion)}</span></div>
		      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">段</span><span class="dsh-gen-stat-v">${e.sections.length}<small>/4</small></span></div>
		      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">谱系事件</span><span class="dsh-gen-stat-v">${e.history.length}</span></div>
		      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">候选</span><span class="dsh-gen-stat-v">${r}<small> · 观察中 ${i}${a?` · <b class="dsh-gen-warn-txt">待裁决 ${a}</b>`:``}</small></span></div>
		      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">一致性</span><span class="dsh-gen-stat-v">${n}</span></div>
		    </div>
		    <div class="dsh-gen-ov-meta">创建 ${l(e.createdAt)} · 最近更新 ${c(e.updatedAt)} · 核验 ${c(t.checkedAt)}</div>
		  </div>`}function S(e){let t=e.id===`constitution`?b(`🔒 宪法层 · 锁定`,`lock`):b(`可进化`,`ev`),n=(e.content??``).trim(),r=n.length>0?`${n.length} 字 · `:``,i=n.length>0?`<details class="dsh-gen-sec-body" open><summary>${r}全文 v${e.version??0}（点击收起）</summary><pre class="dsh-gen-sec-content">${s(n)}</pre></details>`:`<div class="dsh-gen-sec-empty">（sections/${String(e.id)}.md 缺失——genome 工具写入异常）</div>`,a=e.lastChange,o=a?`<details class="dsh-gen-exp" open><summary><span class="dsh-gen-lc-head">最近：<b>${f[a.type??``]??s(a.type??``)}</b> @ ${s(a.genomeVersion??``)} · ${c(a.ts)}（点击收起理由）</span></summary><div class="dsh-gen-exp-body">${s(a.reason??`—`)}</div></details>`:`<div class="dsh-gen-lc-empty">无变更记录</div>`;return`
		  <div class="dsh-gen-sec-card">
		    <div class="dsh-gen-sec-head">
		      <span class="dsh-gen-sec-name">${s(d[e.id]??e.id)}</span>
		      <span class="dsh-gen-sec-ver">v${e.version??0}</span>
		      ${t}
		    </div>
		    ${i}
		    ${o}
		  </div>`}function C(e){return`
		  <div class="dsh-gen-block">
		    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">② 段状态矩阵</span><span class="dsh-gen-block-s">4 个基因组段 · 版本与最近变更</span>${o(`sections`)}</div>
		    <div class="dsh-gen-sec-grid">
		      ${e.sections.map(S).join(``)}
		    </div>
		  </div>`}function w(e){if(e.items.length===0)return`<div class="dsh-gen-iss ok"><span class="dsh-gen-iss-id">${s(e.id)}</span><span class="dsh-gen-iss-t">${s(e.label)}</span><span class="dsh-gen-iss-r">✅ 通过</span></div>`;let t=e.items.map(e=>{let t=e,n=[];t.genomeVersion&&n.push(`g<code>${s(t.genomeVersion)}</code>`),t.section&&n.push(s(u[String(t.section)]??String(t.section))),t.sectionVersion&&n.push(`v${String(t.sectionVersion)}`),t.id&&n.push(`<code>${s(t.id)}</code>`),t.file&&n.push(`<code>${s(t.file)}</code>`),t.ts&&n.push(c(String(t.ts)));let r=t.reason?`<div class="dsh-gen-iss-reason">${s(t.reason)}</div>`:``;return`<div class="dsh-gen-iss-item">${n.join(` · `)}${r}</div>`}).join(``);return`
		  <div class="dsh-gen-iss bad">
		    <span class="dsh-gen-iss-id">${s(e.id)}</span>
		    <span class="dsh-gen-iss-t">${s(e.label)}</span>
		    <span class="dsh-gen-iss-r">❌ ${e.items.length} 项</span>
		  </div>
		  <div class="dsh-gen-iss-desc">${s(e.description)}</div>
		  ${t}`}function T(e){let t=e.consistency,n=t.healthy?`ok`:`bad`,r=t.healthy?`C1/C2/C3 全部通过 — 登记与落库一致，gate 有案可裁`:`检测到 ${t.issues.filter(e=>e.items.length>0).length} 类异常（F1 哨兵规则，与 gate runConsistencyCheck 同源）`;return`
		  <div class="dsh-gen-block">
		    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">③ 一致性诊断</span><span class="dsh-gen-block-s">F1 哨兵可视化仪表 · 状态一致性核验（genome.json ↔ candidates.json）</span>${o(`consistency`)}</div>
		    <div class="dsh-gen-cons-head ${n}">${r}</div>
		    <div class="dsh-gen-iss-list">
		      ${e.consistency.issues.map(w).join(``)}
		    </div>
		  </div>`}function E(e){let t=u[e.section]??e.section,n=e.due?`⏰ 已过观察期 · 待 gate 裁决`:m[e.status]??e.status,r=e.due?`due`:h[e.status]??`unk`,i=``;i=(e.status===`watching`||e.due)&&e.progress!==void 0?`
		    <div class="dsh-gen-cand-bar">
		      <div class="dsh-gen-cand-bar-in" style="width:${Math.round((e.progress??0)*100)}%"></div>
		    </div>
		    <div class="dsh-gen-cand-bar-meta">${l(e.createdAt)} → ${l(e.observeUntil)} · ${e.due?`已到期`:`余 ${e.remainingDays??0} 天`}</div>`:`<div class="dsh-gen-cand-bar-meta">${l(e.createdAt)}${e.observeUntil?` → ${l(e.observeUntil)}`:``}</div>`;let a=``;if(e.healthCheck){let t=e.healthCheck.passed?`✅ 结构健康`:`❌ 结构异常`,n=[];e.healthCheck.sizeDelta!==void 0&&n.push(`diff ${e.healthCheck.sizeDelta} 字符`),e.healthCheck.issues&&e.healthCheck.issues.length>0&&n.push(...e.healthCheck.issues);let r=n.length>0?`<div class="dsh-gen-cand-hc-extra">${n.map(e=>s(e)).join(`；`)}</div>`:``;a=`<div class="dsh-gen-cand-hc">${t}${e.healthCheck.checkedAt?` · ${c(e.healthCheck.checkedAt)} 核`:``}${r}</div>`}let o=e.note?`<div class="dsh-gen-cand-note">${s(e.note)}</div>`:``,d=e.mutationType?`<span class="dsh-gen-cand-mut">${s(e.mutationType)}</span>`:``;return`
		  <div class="dsh-gen-cand">
		    <div class="dsh-gen-cand-head">
		      <span class="dsh-gen-cand-sec">${s(t)}</span>
		      <span class="dsh-gen-cand-gv">${s(e.genomeVersion)} · v${e.sectionVersion}</span>
		      <span class="dsh-gen-cand-id"><code>${s(e.id)}</code></span>
		      ${d}
		      ${b(n,r)}
		    </div>
		    ${i}
		    ${a}
		    ${o}
		  </div>`}function D(){return`<div class="dsh-gen-tabs">${g.map(e=>`<button type="button" class="dsh-gen-tab${e.key===v?` on`:``}" data-cand-filter="${e.key}">${s(e.label)}</button>`).join(``)}</div>`}function O(e){let t=e.candidates.filter(e=>y(e,v));return`<div class="dsh-gen-cand-list">${t.length===0?`<div class="dsh-gen-cand-empty">此筛选下无候选${e.candidates.length===0?`（candidates.json 暂无记录）`:``}</div>`:t.map(E).join(``)}</div>`}function k(e){return`
		  <div class="dsh-gen-block">
		    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">④ 候选生命周期流水线</span><span class="dsh-gen-block-s">genome_update(candidate) → 观察期 → validation_gate 裁决（转正 / 回滚）</span>${o(`candidates`)}</div>
		    ${D()}
		    <div class="dsh-gen-cand-list-root">${O(e)}</div>
		  </div>`}function A(e){let t=e.history.length===0?`<div class="dsh-gen-tl-empty">无谱系记录</div>`:`<div class="dsh-gen-tl">${e.history.map(e=>{let t=f[e.type]??s(e.type),n=p[e.type]??`unk`,r=u[e.section]??e.section,i=e.stage?b(e.stage===`candidate`?`观察版`:`正式版`,e.stage===`candidate`?`wait`:`ev`):``,a=e.gitCommit?` <code>${s(e.gitCommit)}</code>`:``,o=e.reason?`<details class="dsh-gen-exp"><summary>理由</summary><div class="dsh-gen-exp-body">${s(e.reason)}</div></details>`:``;return`
		      <div class="dsh-gen-tl-item">
		        <div class="dsh-gen-tl-dot ${n}"></div>
		        <div class="dsh-gen-tl-main">
		          <div class="dsh-gen-tl-head">
		            <span class="dsh-gen-tl-gv">${s(e.genomeVersion)}</span>
		            ${b(t,n)}
		            <span class="dsh-gen-tl-sec">${s(r)} v${e.sectionVersion}</span>
		            ${i}
		            <span class="dsh-gen-tl-ts">${c(e.ts)}</span>
		            ${a}
		          </div>
		          ${o}
		        </div>
		      </div>`}).join(``)}</div>`;return`
		  <div class="dsh-gen-block">
		    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">⑤ 谱系时间线</span><span class="dsh-gen-block-s">规则进化历史 · 谁在何时改了什么（genome_version 倒序）</span>${o(`timeline`)}</div>
		    ${t}
		  </div>`}async function j(e){if(e.disabled)return;let t=e.dataset.explainModule??``,n=e.textContent??`🤖 讲解`;e.disabled=!0,e.classList.add(`loading`),e.textContent=`⏳ 请求中…`;try{let n=await fetch(`/dashboard/api/genome/explain?module=${encodeURIComponent(t)}`,{headers:{Accept:`application/json`}}),r=await n.json();if(!n.ok||r.success===!1)throw Error(r.error??`HTTP ${n.status}`);e.classList.remove(`loading`),e.classList.add(`done`),e.textContent=`✓ 已请求 · 收起看板看回复`,e.title=`讲解任务已投递给 AI 会话：点左上「✕ 收起」回到会话，AI 将介绍该区域解决什么问题、有什么作用`}catch(t){e.classList.remove(`loading`),e.classList.add(`err`),e.textContent=`✗ 请求失败`,e.title=`失败：`+(t instanceof Error?t.message:String(t))}finally{window.setTimeout(()=>{e.disabled=!1,e.classList.remove(`done`,`err`,`loading`),e.textContent=n},3500)}}function M(e){return`${x(e)}${C(e)}${T(e)}${k(e)}${A(e)}`}function N(){let e=document.createElement(`div`);e.className=`dsh-gen-board`;let t=document.createElement(`div`);t.className=`dsh-gen-head`;let n=document.createElement(`button`);n.type=`button`,n.className=`dsh-gen-recheck`,n.title=`重新读取 genome.json / candidates.json 并重跑 C1/C2/C3 一致性核验`,n.innerHTML=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg><span>⟳ 重检</span>`;let r=document.createElement(`div`);r.className=`dsh-gen-meta`,r.textContent=`加载中…`,t.appendChild(r),t.appendChild(n);let i=document.createElement(`div`);return i.className=`dsh-gen-body`,i.addEventListener(`click`,e=>{let t=e.target;if(t===null)return;let n=t.closest(`[data-cand-filter]`);if(n!==null){if(_===void 0)return;v=n.dataset.candFilter??`all`;let e=i.querySelector(`.dsh-gen-tabs`),t=i.querySelector(`.dsh-gen-cand-list-root`);e!==null&&(e.outerHTML=D()),t!==null&&(t.innerHTML=O(_));return}let r=t.closest(`[data-explain-module]`);if(r!==null){j(r);return}}),e.appendChild(t),e.appendChild(i),{root:e,refreshBtn:n,meta:r,head:t}}function P(e,t){_=t;let n=e.root.querySelector(`.dsh-gen-body`);n!==null&&(n.innerHTML=M(t))}let F=!1;function I(){let r={boardOpen:!1},i=()=>{r.boardOpen=!0,o()},a=()=>{r.boardOpen=!1,o()},o=()=>{if(r.boardOpen){for(let e of t)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(e,``),document.dispatchEvent(new CustomEvent(n,{detail:`dashboard-genome`}))}else document.documentElement.removeAttribute(e)};return{isActive:()=>r.boardOpen,toggle:()=>{r.boardOpen?a():i()},getSnapshot:()=>r,openBoard:i,closeBoard:a}}function L(t){let r,a,o,s,c=!1,l=()=>{if(a!==void 0||c)return;let e=i();if(e===void 0)return;a=document.createElement(`div`),a.className=`dsh-gen-board`,a.dataset.dshGenView=``,e.appendChild(a),r=N(),a.appendChild(r.root),r.refreshBtn?.addEventListener(`click`,()=>{d()});let n=document.createElement(`button`);n.type=`button`,n.className=`dsh-gen-close`,n.title=`收起看板，回到会话`,n.textContent=`✕ 收起`,n.addEventListener(`click`,()=>{t.toggle()}),r.head!==void 0&&r.head.insertBefore(n,r.refreshBtn??null),d(!0),console.log(`[dashboard-genome] board container mounted`)},u=new MutationObserver(()=>{l()});u.observe(document.body,{childList:!0,subtree:!0}),l();async function d(e=!1){if(!(F||r===void 0)){F=!0;try{let e=await(await fetch(`/dashboard/api/genome`,{headers:{Accept:`application/json`}})).json();if(!e.success||e.data===void 0)throw Error(e.error??`接口失败`);s=e.data,P(r,e.data),r.meta.textContent=`刷新于 `+new Date().toLocaleTimeString()+` · 数据 `+(e.data.fetchedAt?new Date(e.data.fetchedAt).toLocaleTimeString():``)}catch(t){if(r===void 0)return;r.meta.textContent=`⚠️ 加载失败: `+(t instanceof Error?t.message:String(t)),!e&&s!==void 0&&P(r,s)}finally{F=!1}}}let f=()=>{o===void 0&&(o=window.setInterval(()=>{d()},3e4))},p=()=>{o!==void 0&&(window.clearInterval(o),o=void 0)},m=t.openBoard,h=t.closeBoard,g=()=>{l(),f(),m()},_=()=>{p(),h()},v=t;v.openBoard=g,v.closeBoard=_,v.toggle=()=>{t.isActive()?_():g()};let y=e=>{let n=e.detail;n!==void 0&&n!==`dashboard-genome`&&t.isActive()&&_()};window.addEventListener(n,y);let b=e=>{if(!t.isActive())return;let n=e.target;n!==null&&n.closest(`[data-dsh-gen-entry], [data-dsh-gen-view]`)===null&&_()};return document.addEventListener(`click`,b),()=>{c=!0,u.disconnect(),p(),window.removeEventListener(n,y),document.removeEventListener(`click`,b),a?.remove(),a=void 0,document.documentElement.removeAttribute(e)}}const R=`@pi-investment/dashboard-genome/styles`;function z(){if(document.getElementById(R)!==null)return;let e=document.createElement(`style`);e.id=R,e.textContent=`
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
		/* 三代中心列特征各配隐藏兜底（bulletin 同款：data-pane dev shell / centerCol 官方布局 / Desktop surface） */
		html[data-dsh-gen-active] [data-pane="conversation"] > *:not([data-dsh-gen-view]),
		html[data-dsh-gen-active] [class*="centerCol"] > *:not([data-dsh-gen-view]),
		html[data-dsh-gen-active] .dshDesktopConversationSurface > *:not([data-dsh-gen-view]) { display: none !important; }
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
		.dsh-gen-close {
		  display: inline-flex;
		  align-items: center;
		  gap: 4px;
		  border: 1px solid var(--dsw-border, #dcdfe6);
		  border-radius: 6px;
		  background: var(--dsw-bg-1, #fff);
		  color: var(--dsw-text-2, #4e5969);
		  font-size: 12px;
		  padding: 4px 10px;
		  cursor: pointer;
		  white-space: nowrap;
		  flex-shrink: 0;
		}
		.dsh-gen-close:hover { border-color: #f53f3f; color: #f53f3f; }
		
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
		.dsh-gen-block-h { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 10px; margin-bottom: 10px; }
		.dsh-gen-block-t { font-size: 13px; font-weight: 700; }
		.dsh-gen-block-s { font-size: 11px; color: var(--dsw-text-3, #8a8f99); }
		
		/* =====「🤖 讲解」按钮 ===== */
		.dsh-gen-explain {
		  margin-left: auto;
		  display: inline-flex;
		  align-items: center;
		  gap: 3px;
		  font-size: 11px;
		  line-height: 1;
		  color: var(--dsw-primary, #2f6bff);
		  background: var(--dsw-bg-2, rgba(47,107,255,0.08));
		  border: 1px solid transparent;
		  border-radius: 999px;
		  padding: 4px 10px;
		  cursor: pointer;
		  user-select: none;
		  transition: background 0.15s ease, color 0.15s ease;
		}
		.dsh-gen-explain:hover { background: var(--dsw-primary, #2f6bff); color: #fff; }
		.dsh-gen-explain:disabled { cursor: default; opacity: 0.85; }
		.dsh-gen-explain.loading { color: var(--dsw-text-3, #8a8f99); background: var(--dsw-bg-2, rgba(0,0,0,0.04)); }
		.dsh-gen-explain.done { color: #1e7f4f; background: rgba(30,127,79,0.10); }
		.dsh-gen-explain.err { color: #c41d1d; background: rgba(196,29,29,0.08); }
		
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
		
		/* ===== ② 段矩阵（纵向全宽：全文阅读优先） ===== */
		.dsh-gen-sec-grid { display: flex; flex-direction: column; gap: 10px; }
		.dsh-gen-sec-card {
		  border: 1px solid var(--dsw-border, #e5e6eb);
		  border-radius: 8px;
		  padding: 10px 14px;
		  display: flex;
		  flex-direction: column;
		  gap: 6px;
		  background: var(--dsw-bg-1, #fff);
		}
		.dsh-gen-sec-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
		.dsh-gen-sec-head .dsh-gen-badge { margin-left: auto; }
		.dsh-gen-sec-name { font-size: 13px; font-weight: 600; }
		.dsh-gen-sec-ver {
		  font-size: 12px;
		  font-weight: 600;
		  color: var(--dsw-primary, #2f6bff);
		  background: var(--dsw-bg-2, rgba(47,107,255,0.08));
		  border-radius: 4px;
		  padding: 1px 6px;
		}
		.dsh-gen-sec-body summary {
		  cursor: pointer;
		  font-size: 12px;
		  font-weight: 600;
		  color: var(--dsw-primary, #2f6bff);
		  padding: 2px 0;
		  user-select: none;
		}
		.dsh-gen-sec-body summary:hover { text-decoration: underline; }
		.dsh-gen-sec-content {
		  white-space: pre-wrap;
		  word-break: break-word;
		  font-size: 12px;
		  line-height: 1.75;
		  color: var(--dsw-text-1, #1f2329);
		  background: var(--dsw-bg-2, rgba(0,0,0,0.025));
		  border: 1px solid var(--dsw-border, #eef0f3);
		  border-radius: 6px;
		  padding: 10px 12px;
		  margin: 4px 0 2px;
		  max-height: 360px;
		  overflow-y: auto;
		}
		.dsh-gen-sec-empty { font-size: 11px; color: var(--dsw-text-4, #c9cdd4); }
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
		`,(document.head??document.documentElement).appendChild(e)}const B=[],V=`__dshGenomeClient`;function H(){if(window[V]!==void 0)try{window[V].dispose()}catch{}try{z();let e=I(),t=a(e),n=L(e);window[V]={dispose:()=>{try{t(),n()}catch{}}},console.log(`[dashboard-genome] client applied — 侧栏「自主进化」入口就绪`)}catch(e){console.error(`[dashboard-genome] client half failed to start:`,e)}}exports.apply=H,exports.inject=B,exports.name=`@pi-investment/dashboard-genome/client`;
			return module.exports;
		}
	});

