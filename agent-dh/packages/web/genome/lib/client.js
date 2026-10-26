window.__ModuleLoader__.load({
		id: "@pi-investment/dashboard-genome",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");function t(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function n(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}const r=new WeakMap;function i(e){r.set(e,e.innerHTML)}function a(e){let t=[],n=e;for(;n!==null&&t.length<5&&n!==document.body;)n.scrollHeight>n.clientHeight&&t.push({el:n,top:n.scrollTop}),n=n.parentElement;return t}function o(e,t){if(r.get(e)===t)return!1;let n=a(e);e.innerHTML=t;for(let e of n)e.el.scrollHeight>=e.top&&(e.el.scrollTop=e.top);return r.set(e,t),!0}const s=e=>String(e).padStart(2,`0`);function c(e){if(!e)return null;let t=new Date(String(e));return Number.isNaN(t.getTime())?null:t}function l(e,t){if(!e)return`—`;let n=c(e);if(!n)return String(e).slice(0,16).replace(`T`,` `);let r=new Date,i=n.getFullYear()===r.getFullYear()&&n.getMonth()===r.getMonth()&&n.getDate()===r.getDate(),a=s(n.getHours())+`:`+s(n.getMinutes());return t?.omitDateIfToday&&i?a:(t?.withYear?n.getFullYear()+`-`+s(n.getMonth()+1)+`-`+s(n.getDate()):s(n.getMonth()+1)+`-`+s(n.getDate()))+` `+a}function u(e){if(!e)return`—`;let t=c(e);return t?t.getFullYear()+`-`+s(t.getMonth()+1)+`-`+s(t.getDate()):String(e)}function d(e){return[`.`+e+`-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }`,`.`+e+`-toast.ok { background:#529b2e; }`,`.`+e+`-toast.err { background:#e64545; }`,`.`+e+`-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }`].join(`
`)}function f(e){let t=`dsh-toast-styles-`+e,n=document.getElementById(t);if(n!==null&&n.tagName===`STYLE`)return()=>n.remove();let r=document.createElement(`style`);return r.id=t,r.textContent=d(e),(document.head??document.documentElement).appendChild(r),()=>{document.getElementById(t)?.remove()}}function p(e,t,n,r=4200){let i=document.createElement(`div`);i.className=n+`-toast `+(t?`ok`:`err`),i.textContent=e,document.body.appendChild(i),window.setTimeout(()=>{i.classList.add(`out`),window.setTimeout(()=>i.remove(),350)},r)}function m(e){let{prefix:n,icon:r,label:i,title:a,controller:o}=e,s=n.replace(/-([a-z])/g,(e,t)=>t.toUpperCase())+`Entry`,c=`[data-`+n+`-entry]`,l,u=()=>{let e=document.createElement(`button`);return e.type=`button`,e.className=n+`-entry`,e.dataset[s]=``,e.setAttribute(`aria-label`,a),e.title=a,e.innerHTML=r+`<span class="`+n+`-entry-label">`+i+`</span>`,e.addEventListener(`click`,e=>{e.preventDefault(),e.stopPropagation(),o.toggle()}),e},d=()=>{let e=t();if(e===void 0)return!1;if(e.querySelector(c)!==null){let t=e.querySelector(c);return t!==void 0&&l===void 0&&(l=t),!0}let n=u(),r=e.querySelector(`[class*="logoRow"]`);return r!==null&&r.nextSibling!==null?e.insertBefore(n,r.nextSibling):e.prepend(n),l=n,!0};d();let f=new MutationObserver(()=>{(l===void 0||!document.contains(l)||l.parentElement===null)&&d()});f.observe(document.body,{childList:!0,subtree:!0});let p=window.setInterval(()=>{(l===void 0||!document.contains(l))&&d()},5e3),m=()=>{l?.setAttribute(`data-active`,o.isActive()?`true`:`false`)},h=window.setInterval(m,1e3);return m(),()=>{f.disconnect(),window.clearInterval(p),window.clearInterval(h),l?.remove(),l=void 0}}const h=`dsh-right-tab-host`,g=`dsh-right-tab-host-style`,_=`
.${h}{display:flex;flex-direction:column;height:100%;min-height:0;overflow:hidden}
.${h}>*{min-height:0}
.${h} .dsh-right-tab-error{padding:16px 18px;color:#b94a48;font:13px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
`;function v(){if(typeof document>`u`||document.getElementById(g)!==null)return;let e=document.createElement(`style`);e.id=g,e.textContent=_,document.head.appendChild(e)}function y(t){return function(n){let r=(0,e.useRef)(null);return(0,e.useEffect)(()=>{let e=r.current;if(e===null)return;let n;try{n=t.mount(e)}catch(n){console.error(`[page-kit] 右栏看板挂载失败 `+t.id+`:`,n);let r=document.createElement(`div`);r.className=`dsh-right-tab-error`,r.textContent=`看板加载失败：`+(n instanceof Error?n.message:String(n)),e.appendChild(r)}return()=>{try{typeof n==`function`&&n()}catch(e){console.error(`[page-kit] 右栏看板卸载清理失败 `+t.id+`:`,e)}}},[]),(0,e.createElement)(`div`,{ref:r,className:h,"data-right-tab":t.id})}}function b(e,t){let n=e??{},r=n.sidebarRightTabs,i=n.sidebarRight,a=n.slots;if(r===void 0||typeof r.register!=`function`)throw Error(`sidebarRightTabs 服务不可用（DSH 官方右侧栏未加载）`);if(i===void 0||typeof i.openTab!=`function`)throw Error(`sidebarRight 服务不可用（DSH 官方右侧栏未加载）`);v();let o=[];if(((e,t)=>{try{if(typeof n.effect==`function`){n.effect(e,t);return}let r=e();typeof r==`function`&&o.push(r)}catch(e){console.error(`[page-kit] 右栏注册失败 `+t+`:`,e)}})(()=>r.register({id:t.id,kind:t.kind,title:()=>t.title,keepMounted:!0}),`tab-type:`+t.id),a!==void 0&&typeof a.register==`function`){let e=y(t);try{typeof a.inject==`function`?a.inject(`sidebar.right.pane.tab`,()=>a.register({name:`sidebar.right.pane.tab`,key:t.id},e)):a.register({name:`sidebar.right.pane.tab`,key:t.id},e)}catch(e){console.error(`[page-kit] 右栏正文注册失败 `+t.id+`:`,e)}}else console.error(`[page-kit] slots 服务不可用，右栏正文未注册 `+t.id);let s=()=>{try{return i.openTab(t.kind),!0}catch(e){return console.error(`[page-kit] 右栏打开失败 `+t.kind+`:`,e),!1}},c=()=>{try{if(typeof i.isExpanded==`function`&&i.isExpanded()===!1||typeof i.active!=`function`)return!1;let e=i.active();return e!=null&&e.kind===t.kind}catch{return!1}},l=()=>{if(c())try{let e=i.active?.();e!=null&&e.id!==void 0&&i.close?.(e.id)}catch(e){console.error(`[page-kit] 右栏关闭失败 `+t.kind+`:`,e)}};return{open:s,toggle:()=>{c()?l():s()},close:l,isActive:c,dispose:()=>{l();for(let e of o.splice(0))try{e()}catch{}}}}function x(e){return m({prefix:`dsh-gen`,icon:`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/><circle cx="12" cy="12" r="3"/></svg>`,label:`自主进化`,title:`自主进化看板 (dashboard-genome) — 基因组/候选/一致性诊断`,controller:e})}function S(e,t,r){let i=t===void 0?``:` data-explain-item="${n(t)}"`,a=r===void 0?`AI 讲解：请当前 AI 介绍这是什么（讲解将出现在下方会话）`:`AI 讲解：${n(r)}（讲解将出现在下方会话）`;return`<button type="button" class="${t===void 0?`dsh-gen-explain`:`dsh-gen-explain sm`}" data-explain-module="${e}"${i} title="${a}">${t===void 0?`🤖 讲解`:`🤖`}</button>`}function C(e){return l(e)}function w(e){return u(e)}const T={constitution:`宪法`,principles:`决策原则`,rules:`操作规则`,lessons:`经验教训`},E={constitution:`交易宪法（不可修改）`,principles:`决策原则`,rules:`操作规则`,lessons:`经验教训`},D={update:`更新`,promote:`转正`,rollback:`回滚`},O={update:`up`,promote:`ok`,rollback:`bad`},k={watching:`观察中`,promoted:`已转正`,rejected:`已拒绝`,extended:`观察延期`,unknown:`未知`},A={watching:`wait`,promoted:`ok`,rejected:`bad`,extended:`wait`,unknown:`unk`},j=[{key:`all`,label:`全部`},{key:`watching`,label:`观察中`},{key:`due`,label:`待裁决`},{key:`promoted`,label:`已转正`},{key:`rejected`,label:`已回滚/拒绝`}];let M,N=`all`;function P(e,t){switch(t){case`all`:return!0;case`watching`:return e.status===`watching`&&!e.due;case`due`:return e.due===!0;case`promoted`:return e.status===`promoted`;case`rejected`:return e.status===`rejected`;case`extended`:return e.status===`extended`;default:return!0}}function F(e,t){return`<span class="dsh-gen-badge ${t}">${n(e)}</span>`}function I(e){let t=e.consistency,r=t.healthy?F(`🟢 一致性健康`,`ok`):F(`⚠️ ${t.issues.filter(e=>e.items.length>0).length} 项异常`,`bad`),i=e.candidates.length,a=e.candidates.filter(e=>e.status===`watching`).length,o=e.candidates.filter(e=>e.due).length;return`
  <div class="dsh-gen-ov">
    <div class="dsh-gen-ov-title">
      <span class="dsh-gen-ov-big">自主进化</span>
      <span class="dsh-gen-ov-sub">Autonomy 线 · 能力设计层可观测 — 回答「改了什么规则 / 什么在试运行何时出结果 / 进化链路有无卡住」</span>
    </div>
    <div class="dsh-gen-ov-stats">
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">基因组版本</span><span class="dsh-gen-stat-v dsh-gen-gv">${n(e.genomeVersion)}</span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">段</span><span class="dsh-gen-stat-v">${e.sections.length}<small>/4</small></span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">谱系事件</span><span class="dsh-gen-stat-v">${e.history.length}</span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">候选</span><span class="dsh-gen-stat-v">${i}<small> · 观察中 ${a}${o?` · <b class="dsh-gen-warn-txt">待裁决 ${o}</b>`:``}</small></span></div>
      <div class="dsh-gen-stat"><span class="dsh-gen-stat-k">一致性</span><span class="dsh-gen-stat-v">${r}</span></div>
    </div>
    <div class="dsh-gen-ov-meta">创建 ${w(e.createdAt)} · 最近更新 ${C(e.updatedAt)} · 核验 ${C(t.checkedAt)}</div>
  </div>`}function L(e){let t=e.id===`constitution`?F(`🔒 宪法层 · 锁定`,`lock`):F(`可进化`,`ev`),r=(e.content??``).trim(),i=r.length>0?`${r.length} 字 · `:``,a=r.length>0?`<details class="dsh-gen-sec-body"><summary>${i}全文 v${e.version??0}（点击展开）</summary><pre class="dsh-gen-sec-content">${n(r)}</pre></details>`:`<div class="dsh-gen-sec-empty">（sections/${String(e.id)}.md 缺失——genome 工具写入异常）</div>`,o=e.lastChange,s=o?`<details class="dsh-gen-exp"><summary><span class="dsh-gen-lc-head">最近：<b>${D[o.type??``]??n(o.type??``)}</b> @ ${n(o.genomeVersion??``)} · ${C(o.ts)}（点击展开理由）</span></summary><div class="dsh-gen-exp-body">${n(o.reason??`—`)}</div></details>`:`<div class="dsh-gen-lc-empty">无变更记录</div>`;return`
  <div class="dsh-gen-sec-card">
    <div class="dsh-gen-sec-head">
      <span class="dsh-gen-sec-name">${n(E[e.id]??e.id)}</span>
      <span class="dsh-gen-sec-ver">v${e.version??0}</span>
      ${t}
      ${S(`sections`,e.id,`${E[e.id]??e.id} 段是什么、当前版本要点与最近变更`)}
    </div>
    ${a}
    ${s}
  </div>`}function R(e){return`
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">② 段状态矩阵</span><span class="dsh-gen-block-s">4 个基因组段 · 版本与最近变更 · 点各段 🤖 可逐段讲解</span></div>
    <div class="dsh-gen-sec-grid">
      ${e.sections.map(L).join(``)}
    </div>
  </div>`}function z(e){if(e.items.length===0)return`<div class="dsh-gen-iss ok"><span class="dsh-gen-iss-id">${n(e.id)}</span><span class="dsh-gen-iss-t">${n(e.label)}</span><span class="dsh-gen-iss-r">✅ 通过</span>${S(`consistency`,e.id,`${e.label} 检查什么、为什么设计这道哨兵`)}</div>`;let t=e.items.map(e=>{let t=e,r=[];t.genomeVersion&&r.push(`g<code>${n(t.genomeVersion)}</code>`),t.section&&r.push(n(T[String(t.section)]??String(t.section))),t.sectionVersion&&r.push(`v${String(t.sectionVersion)}`),t.id&&r.push(`<code>${n(t.id)}</code>`),t.file&&r.push(`<code>${n(t.file)}</code>`),t.ts&&r.push(C(String(t.ts)));let i=t.reason?`<div class="dsh-gen-iss-reason">${n(t.reason)}</div>`:``;return`<div class="dsh-gen-iss-item">${r.join(` · `)}${i}</div>`}).join(``);return`
  <div class="dsh-gen-iss bad">
    <span class="dsh-gen-iss-id">${n(e.id)}</span>
    <span class="dsh-gen-iss-t">${n(e.label)}</span>
    <span class="dsh-gen-iss-r">❌ ${e.items.length} 项</span>
    ${S(`consistency`,e.id,`${e.label} 当前 ${e.items.length} 项异常是什么、该怎么处置`)}
  </div>
  <div class="dsh-gen-iss-desc">${n(e.description)}</div>
  ${t}`}function B(e){let t=e.consistency;return`
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">③ 一致性诊断</span><span class="dsh-gen-block-s">F1 哨兵可视化仪表 · 状态一致性核验（genome.json ↔ candidates.json）· 每条哨兵 🤖 可讲</span></div>
    <div class="dsh-gen-cons-head ${t.healthy?`ok`:`bad`}">${t.healthy?`C1/C2/C3 全部通过 — 登记与落库一致，gate 有案可裁`:`检测到 ${t.issues.filter(e=>e.items.length>0).length} 类异常（F1 哨兵规则，与 gate runConsistencyCheck 同源）`}</div>
    <div class="dsh-gen-iss-list">
      ${e.consistency.issues.map(z).join(``)}
    </div>
  </div>`}function V(e){let t=T[e.section]??e.section,r=e.due?`⏰ 已过观察期 · 待 gate 裁决`:k[e.status]??e.status,i=e.due?`due`:A[e.status]??`unk`,a=``;a=(e.status===`watching`||e.due)&&e.progress!==void 0?`
    <div class="dsh-gen-cand-bar">
      <div class="dsh-gen-cand-bar-in" style="width:${Math.round((e.progress??0)*100)}%"></div>
    </div>
    <div class="dsh-gen-cand-bar-meta">${w(e.createdAt)} → ${w(e.observeUntil)} · ${e.due?`已到期`:`余 ${e.remainingDays??0} 天`}</div>`:`<div class="dsh-gen-cand-bar-meta">${w(e.createdAt)}${e.observeUntil?` → ${w(e.observeUntil)}`:``}</div>`;let o=``;if(e.healthCheck){let t=e.healthCheck.passed?`✅ 结构健康`:`❌ 结构异常`,r=[];e.healthCheck.sizeDelta!==void 0&&r.push(`diff ${e.healthCheck.sizeDelta} 字符`),e.healthCheck.issues&&e.healthCheck.issues.length>0&&r.push(...e.healthCheck.issues);let i=r.length>0?`<div class="dsh-gen-cand-hc-extra">${r.map(e=>n(e)).join(`；`)}</div>`:``;o=`<div class="dsh-gen-cand-hc">${t}${e.healthCheck.checkedAt?` · ${C(e.healthCheck.checkedAt)} 核`:``}${i}</div>`}let s=e.note?`<div class="dsh-gen-cand-note">${n(e.note)}</div>`:``,c=e.mutationType?`<span class="dsh-gen-cand-mut">${n(e.mutationType)}</span>`:``,l=``,u=e.healthCheck?.ruleChanges;if(u&&(u.added?.length??0)+(u.removed?.length??0)>0){let e=[];for(let t of u.added??[])e.push(`<span class="dsh-gen-chg add">🆕 新增规则 ${n(t)}</span>`);for(let t of u.removed??[])e.push(`<span class="dsh-gen-chg rm">🗑 移除规则 ${n(t)}</span>`);l=`<div class="dsh-gen-cand-chg">${e.join(``)}</div>`}else e.healthCheck?.ruleChanges&&(l=`<div class="dsh-gen-cand-chg"><span class="dsh-gen-chg mod">✏️ 文本修正（无规则增删，见下方理由）</span></div>`);let d=e.due?`观察期已满 · 下一步：validation_gate 凭观察期表现裁决 → 转正为正式版 / 回滚`:e.status===`watching`?`试运行观察中 · ${e.remainingDays??`?`} 天后到期自动进入 gate 裁决（转正 / 回滚），此间正式版未被改动`:e.status===`promoted`?`已转正 · 此版本内容为正式版，持续生效中`:e.status===`rejected`?`已拒绝 · 内容未转正（如需可 genome_rollback 复原）`:``,f=d?`<div class="dsh-gen-cand-step">${n(d)}</div>`:``;return`
  <div class="dsh-gen-cand">
    <div class="dsh-gen-cand-head">
      <span class="dsh-gen-cand-sec">${n(t)}</span>
      <span class="dsh-gen-cand-gv">${n(e.genomeVersion)} · v${e.sectionVersion}</span>
      <span class="dsh-gen-cand-id"><code>${n(e.id)}</code></span>
      ${c}
      ${F(r,i)}
      ${S(`candidates`,e.id,`这条候选（${t} ${e.genomeVersion}）改了什么、解决什么问题、观察进度与下一步`)}
    </div>
    ${l}
    ${f}
    ${a}
    ${o}
    ${s}
  </div>`}function H(){return`<div class="dsh-gen-tabs">${j.map(e=>`<button type="button" class="dsh-gen-tab${e.key===N?` on`:``}" data-cand-filter="${e.key}">${n(e.label)}</button>`).join(``)}</div>`}function U(e){let t=e.candidates.filter(e=>P(e,N));return`<div class="dsh-gen-cand-list">${t.length===0?`<div class="dsh-gen-cand-empty">此筛选下无候选${e.candidates.length===0?`（candidates.json 暂无记录）`:``}</div>`:t.map(V).join(``)}</div>`}function W(e){return`
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">④ 候选生命周期流水线</span><span class="dsh-gen-block-s">genome_update(candidate) → 观察期 → validation_gate 裁决（转正 / 回滚）· 每个候选卡 🤖 可讲</span></div>
    ${H()}
    <div class="dsh-gen-cand-list-root">${U(e)}</div>
  </div>`}function G(e){return`
  <div class="dsh-gen-block">
    <div class="dsh-gen-block-h"><span class="dsh-gen-block-t">⑤ 谱系时间线</span><span class="dsh-gen-block-s">规则进化历史 · 谁在何时改了什么（genome_version 倒序）</span></div>
    ${e.history.length===0?`<div class="dsh-gen-tl-empty">无谱系记录</div>`:`<div class="dsh-gen-tl">${e.history.map(e=>{let t=D[e.type]??n(e.type),r=O[e.type]??`unk`,i=T[e.section]??e.section,a=e.stage?F(e.stage===`candidate`?`观察版`:`正式版`,e.stage===`candidate`?`wait`:`ev`):``,o=e.gitCommit?` <code>${n(e.gitCommit)}</code>`:``,s=e.reason?`<details class="dsh-gen-exp"><summary>理由</summary><div class="dsh-gen-exp-body">${n(e.reason)}</div></details>`:``;return`
      <div class="dsh-gen-tl-item">
        <div class="dsh-gen-tl-dot ${r}"></div>
        <div class="dsh-gen-tl-main">
          <div class="dsh-gen-tl-head">
            <span class="dsh-gen-tl-gv">${n(e.genomeVersion)}</span>
            ${F(t,r)}
            <span class="dsh-gen-tl-sec">${n(i)} v${e.sectionVersion}</span>
            ${a}
            <span class="dsh-gen-tl-ts">${C(e.ts)}</span>
            ${o}
          </div>
          ${s}
        </div>
      </div>`}).join(``)}</div>`}
  </div>`}async function K(e){if(e.disabled)return;let t=e.dataset.explainModule??``,n=e.dataset.explainItem??``,r=e.textContent??`🤖 讲解`;e.disabled=!0,e.classList.add(`loading`),e.textContent=`⏳…`;try{let r=`module=${encodeURIComponent(t)}${n?`&item=${encodeURIComponent(n)}`:``}`,i=await fetch(`/dashboard/api/genome/explain?${r}`,{headers:{Accept:`application/json`}}),a=await i.json();if(!i.ok||a.success===!1)throw Error(a.error??`HTTP ${i.status}`);e.classList.remove(`loading`),e.classList.add(`done`),e.textContent=`✓`,e.title=`讲解任务已投递给 AI 会话：收起看板后 AI 将介绍这一条是什么、有什么作用`}catch(t){e.classList.remove(`loading`),e.classList.add(`err`),e.textContent=`✗`,e.title=`失败：`+(t instanceof Error?t.message:String(t))}finally{window.setTimeout(()=>{e.disabled=!1,e.classList.remove(`done`,`err`,`loading`),e.textContent=r},3500)}}function q(e){return`${I(e)}${R(e)}${B(e)}${W(e)}${G(e)}`}function J(){let e=document.createElement(`div`);e.className=`dsh-gen-board`;let t=document.createElement(`div`);t.className=`dsh-gen-head`;let n=document.createElement(`button`);n.type=`button`,n.className=`dsh-gen-recheck`,n.title=`重新读取 genome.json / candidates.json 并重跑 C1/C2/C3 一致性核验`,n.innerHTML=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg><span>⟳ 重检</span>`;let r=document.createElement(`div`);r.className=`dsh-gen-meta`,r.textContent=`加载中…`,t.appendChild(r),t.appendChild(n);let a=document.createElement(`div`);return a.className=`dsh-gen-body`,a.addEventListener(`click`,e=>{let t=e.target;if(t===null)return;let n=t.closest(`[data-cand-filter]`);if(n!==null){if(M===void 0)return;N=n.dataset.candFilter??`all`;let e=a.querySelector(`.dsh-gen-tabs`),t=a.querySelector(`.dsh-gen-cand-list-root`);e!==null&&(e.outerHTML=H()),t!==null&&(t.innerHTML=U(M)),i(a);return}let r=t.closest(`[data-explain-module]`);if(r!==null){K(r);return}}),e.appendChild(t),e.appendChild(a),{root:e,refreshBtn:n,meta:r,head:t}}function Y(e,t){M=t;let n=e.root.querySelector(`.dsh-gen-body`);return n!==null&&o(n,q(t))}function X(e,t){let n=J();e.appendChild(n.root);let r,i=!1,a=!1,o,s=async(e=!1)=>{if(!(i||a)){i=!0;try{let e=await(await fetch(`/dashboard/api/genome`,{headers:{Accept:`application/json`}})).json();if(!e.success||e.data===void 0)throw Error(e.error??`接口失败`);if(a)return;r=e.data,Y(n,e.data)&&(n.meta.textContent=`刷新于 `+new Date().toLocaleTimeString()+` · 数据 `+(e.data.fetchedAt?new Date(e.data.fetchedAt).toLocaleTimeString():``))}catch(t){if(a)return;n.meta.textContent=`⚠️ 加载失败: `+(t instanceof Error?t.message:String(t)),!e&&r!==void 0&&Y(n,r)}finally{i=!1}}},c=()=>{s()};return n.refreshBtn?.addEventListener(`click`,c),s(!0),o=window.setInterval(()=>{a||document.hidden||t?.isActive&&!t.isActive()||s()},3e4),()=>{a=!0,o!==void 0&&(clearInterval(o),o=void 0),n.refreshBtn?.removeEventListener(`click`,c),n.root.remove()}}const Z=`@pi-investment/dashboard-genome/styles`;function Q(){if(document.getElementById(Z)!==null)return;let e=document.createElement(`style`);e.id=Z,e.textContent=`
/* ===== 板容器（右侧栏 tab 正文） ===== */
.dsh-gen-board {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  padding: 16px 20px 40px;
  overflow-y: auto;
  font-family: var(--dsw-font, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif);
  color: var(--dsw-text-1, #1f2329);
  background: transparent;
}
.dsh-gen-board code {
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
/* 条目级小按钮（段卡 / issue 行 / 候选卡内） */
.dsh-gen-explain.sm { padding: 1px 7px; font-size: 12px; flex: none; }
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
.dsh-gen-cand-chg { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 7px; }
.dsh-gen-chg { font-size: 11px; border-radius: 6px; padding: 2px 8px; }
.dsh-gen-chg.add { color: #0e8a3e; background: #e8f7ee; border: 1px solid #bfe8cd; }
.dsh-gen-chg.rm { color: #c41d1d; background: #fdf0f0; border: 1px solid #f3c9c9; }
.dsh-gen-chg.mod { color: #8a5a00; background: #fdf6e6; border: 1px solid #eeddb3; }
.dsh-gen-cand-step { font-size: 10px; color: var(--dsw-text-3, #8a8f99); margin-top: 5px; }
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
.dsh-gen-entry[data-active="true"] { background: color-mix(in srgb, var(--dsw-primary, #2f6bff) 14%, transparent); color: var(--dsw-primary, #2f6bff); }
.dsh-gen-entry[data-active="true"] svg { stroke: var(--dsw-primary, #2f6bff); }
.dsh-gen-entry svg { flex: none; stroke: var(--dsw-text-2, #4e5969); }
[data-sidebar-collapsed] .dsh-gen-entry,
[class*="_collapsed"] .dsh-gen-entry { justify-content: center; width: 36px; margin: 4px auto; padding: 7px 0; }
[data-sidebar-collapsed] .dsh-gen-entry .dsh-gen-entry-label,
[class*="_collapsed"] .dsh-gen-entry .dsh-gen-entry-label { display: none; }
`,(document.head??document.documentElement).appendChild(e)}const ee=[`sidebarRight`,`sidebarRightTabs`,`slots`],$=`__dshGenomeClient`;function te(e){if(window[$]!==void 0)try{window[$].dispose()}catch{}try{Q(),f(`dsh-gen`);let t=b(e,{id:`@pi-investment/dashboard-genome`,kind:`dashboard-genome`,title:`自主进化`,mount:e=>X(e,{isActive:()=>t.isActive()})}),n=x({isActive:()=>t.isActive(),toggle:()=>{if(t.isActive()){t.close();return}t.open()||p(`请先打开一个会话 —— 右侧栏需要有会话才能停靠看板`,!1,`dsh-gen`)}});window[$]={dispose:()=>{try{n(),t.dispose()}catch{}}},console.log(`[dashboard-genome] client applied — 侧栏「自主进化」入口就绪（右侧栏 tab）`)}catch(e){console.error(`[dashboard-genome] client half failed to start:`,e)}}exports.apply=te,exports.inject=ee,exports.name=`@pi-investment/dashboard-genome/client`;
			return module.exports;
		}
	});

