window.__ModuleLoader__.load({
		id: "dsh-pmboard",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");const t=`dsh-panel-activate`;function n(){return document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`)??void 0}function r(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}function i(e){let{panelName:r,activeAttr:i,otherActiveAttrs:a,pollMs:o=3e4,pauseOnHidden:s=!1,dispatchTarget:c=`window`,listenTarget:l=`window`,buildContainer:u,onMount:d,onPoll:f,onOpen:p,onClose:m}=e,h=!1,g,_,v,y=!1,b=()=>{if(g!==void 0||y)return;let e=n();if(e===void 0)return;let t=u();e.appendChild(t),g=t,v=d(t)??void 0},x=new MutationObserver(()=>{b()});x.observe(document.body,{childList:!0,subtree:!0}),b();let S=()=>{if(!(h||y)){h=!0,b();for(let e of a)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(i,``),(c===`document`?document:window).dispatchEvent(new CustomEvent(t,{detail:r})),D(),p?.()}},C=()=>{!h||y||(h=!1,document.documentElement.removeAttribute(i),O(),m?.())},w=()=>{h?C():S()},T=()=>h,E=()=>{h&&f()},D=()=>{O(),_=window.setInterval(E,o)},O=()=>{_!==void 0&&(clearInterval(_),_=void 0)},k=()=>{document.hidden?O():h&&D()};s&&document.addEventListener(`visibilitychange`,k);let A=t=>{if(!h)return;let n=t.target;if(n===null||g!==void 0&&(g===n||g.contains(n)))return;let r=`[data-`+e.prefix+`-entry]`;n.closest(r)===null&&C()};document.addEventListener(`click`,A,!0);let j=e=>{let t=e.detail;t!==void 0&&t!==r&&h&&C()},M=l===`document`?document:window;return M.addEventListener(t,j),{open:S,close:C,toggle:w,isActive:T,dispose:()=>{y||(y=!0,O(),s&&document.removeEventListener(`visibilitychange`,k),document.removeEventListener(`click`,A,!0),M.removeEventListener(t,j),x.disconnect(),v?.(),g?.remove(),g=void 0)}}}function a(e){let{page:t,total:n,totalItems:r,pageAttr:i,prevLabel:a=`‹ 上一页`,nextLabel:o=`下一页 ›`}=e;if(n<=1)return``;let s=Math.min(Math.max(1,t),n),c=e=>`<button type="button" class="tpg-num`+(e===s?` act`:``)+`"`+(e===s?` aria-current="page"`:``)+` `+i+`="`+e+`">`+e+`</button>`,l=[];if(n<=7)for(let e=1;e<=n;e++)l.push(c(e));else{let e=[1,s-1,s,s+1,n].filter(e=>e>=1&&e<=n).sort((e,t)=>e-t),t=[];for(let n of e)t.includes(n)||t.push(n);let r=0;for(let e of t)r!==0&&e-r>1&&l.push(`<span class="tpg-gap">…</span>`),l.push(c(e)),r=e}return`<button type="button" class="tpg-arr" `+i+`="`+(s-1)+`"`+(s<=1?` disabled`:``)+`>`+a+`</button><span class="tpg-nums">`+l.join(``)+`</span><button type="button" class="tpg-arr" `+i+`="`+(s+1)+`"`+(s>=n?` disabled`:``)+`>`+o+`</button><span class="tpg-cnt">第 `+s+`/`+n+` 页 · 共 `+r+` 条</span>`}const o=`dsh-pmboard`,s=`项目看板`,c=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`,`data-dsh-bbd-active`,`data-dsh-gen-active`,`data-dsh-exec-active`],l={draft:`立项`,brainstorming:`需求分析`,planning:`技术设计`,decomposing:`拆分`,implementing:`实施`,accepting:`验收`,done:`完成`,archived:`归档`,canceled:`取消`},u={todo:`待办`,in_progress:`进行中`,integrating:`联调`,testing:`测试`,in_review:`验收`,done:`完成`,canceled:`取消`},d={doc:`文档`,ui:`UI`,analysis:`分析`,implement:`实施`,test:`测试`,review:`评审`,merge:`合并`},f={feature:`功能`,bug:`缺陷`,doc:`文档`,refactor:`重构`,spike:`调研`,chore:`杂项`},p=[`draft`,`brainstorming`,`planning`,`decomposing`,`implementing`,`accepting`];function m(e){let t=e.startsWith(`session-`)?e.slice(8):e;return`w-${(t.split(`-`)[0]??t).slice(0,8)}`}const h=e=>{let t=new Date(e),n=e=>String(e).padStart(2,`0`);return`${n(t.getMonth()+1)}-${n(t.getDate())} ${n(t.getHours())}:${n(t.getMinutes())}`};function g(e,t){return t===0?`0/0`:`${e}/${t}`}const _=new Set;function v(e,t){return t.has(e)}function y(e){let{sid:t,label:n,cls:i,kind:a,archived:o}=e,s=o?`${i} is-archived`:i,c=o?`${a}已归档（${r(t)}）：日志保留、侧栏不可见，点击查看说明`:`${a}（点击跳转到该会话）：${r(t)}`;return`<button type="button" class="${s}" data-action="jump-session" data-sid="${r(t)}" `+(o?`data-archived="true" `:``)+`title="${c}">${o?n+` · 已归档`:n}</button>`}function b(e,t=_){let n=e.sourceSessionId;return n?y({sid:n,label:`窗口 ${m(n)}`,cls:`dsh-pm-window`,kind:`立项来源窗口`,archived:v(n,t)}):``}function x(e,t=_){for(let n=e.length-1;n>=0;n--){let r=e[n].executions;for(let e=r.length-1;e>=0;e--){let n=r[e].sessionId;if(n)return y({sid:n,label:`会话 ${n.slice(0,12)}…`,cls:`dsh-pm-session`,kind:`执行会话`,archived:v(n,t)})}}return``}function S(e){if(!e)return``;let t=e.replace(/\r\n?/g,`
`).split(`
`),n=[],i=[],a=!1,o=[],s=!1,c=()=>{if(o.length===0)return;let e=s?`ol`:`ul`;n.push(`<`+e+`>`+o.map(e=>`<li>`+e+`</li>`).join(``)+`</`+e+`>`),o=[]},l=e=>e.replace(/`([^`]+)`/g,`<code>$1</code>`).replace(/\*\*([^*]+)\*\*/g,`<strong>$1</strong>`).replace(/(^|[^*])\*([^*\n]+)\*/g,`$1<em>$2</em>`).replace(/\[([^\]]+)\]\(([^)\s]+)\)/g,`<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>`);for(let e of t){let t=e.trimEnd();if(t.trim().startsWith("```")){c(),a?(n.push(`<pre><code>`+i.join(`
`)+`</code></pre>`),i=[],a=!1):a=!0;continue}if(a){i.push(r(t));continue}if(t.trim()===``){c();continue}let u=t.match(/^(#{1,6})\s+(.+)$/);if(u){c();let e=u[1].length;n.push(`<h`+e+`>`+l(r(u[2]))+`</h`+e+`>`);continue}let d=t.match(/^\s*[-*+]\s+(.+)$/);if(d){o.length>0&&s&&c(),s=!1,o.push(l(r(d[1])));continue}let f=t.match(/^\s*\d+[.)]\s+(.+)$/);if(f){o.length>0&&!s&&c(),s=!0,o.push(l(r(f[1])));continue}c(),n.push(`<p>`+l(r(t))+`</p>`)}return c(),a&&i.length>0&&n.push(`<pre><code>`+i.join(`
`)+`</code></pre>`),n.join(`
`)}function C(e){let t=e.createdBy,n=t?.kind??`human`;if(n===`human`)return{actor:`human`,text:`人`};if(n===`system`)return{actor:`system`,text:`系统`};let r=t?.sessionId;return{actor:`agent`,text:r!==void 0&&r.length>0?`窗口 `+m(r):`窗口`}}function w(e){return e.length===0?`<div class="dsh-pm-empty">暂无评论</div>`:`<div class="dsh-pm-comments">`+e.map(e=>{let t=C(e);return`
    <div class="dsh-pm-comment" data-actor="${t.actor}">
      <span class="dsh-pm-comment-meta"><span class="dsh-pm-comment-who" data-actor="${t.actor}">${r(t.text)}</span> · ${h(e.createdAt)}</span>
      <div class="dsh-pm-comment-body">${r(e.body)}</div>
    </div>`}).join(``)+`</div>`}function T(){return`<div class="dsh-pm-board"><div class="dsh-pm-empty">暂无数据 — 点击「+ 需求」创建第一个需求</div></div>`}function E(e){return`<div class="dsh-pm-board"><div class="dsh-pm-error">加载失败：${r(e)}</div></div>`}function D(e){let t=Math.floor(Math.max(0,e)/6e4);if(t<60)return t+` 分`;let n=Math.floor(t/60);return n<24?n+` 小时 `+t%60+` 分`:Math.floor(n/24)+` 天 `+n%24+` 小时`}function O(e){return e===`done`||e===`archived`||e===`canceled`}function k(e,t){return e.length>t?e.slice(0,t)+`…`:e}const A={draft:[`brainstorming`,`canceled`],brainstorming:[`planning`,`draft`,`canceled`],planning:[`decomposing`,`brainstorming`,`canceled`],decomposing:[`implementing`,`planning`,`canceled`],implementing:[`accepting`,`canceled`],accepting:[`archived`,`implementing`,`canceled`],done:[],canceled:[`draft`,`archived`],archived:[]},j={invalidInput:`invalid_input`,invalidTransition:`invalid_transition`,humanGate:`human_gate`,notBoundToWindow:`not_bound_to_window`,noBoundReq:`no_bound_req`,missingArtifact:`missing_artifact`,planNotApproved:`plan_not_approved`,alreadyDecomposed:`already_decomposed`,doneEvidenceMissing:`done_evidence_missing`,bulkClose:`bulk_close`,staleBuild:`stale_build`,versionMismatch:`version_mismatch`,storeInconsistent:`store_inconsistent`,migrationFailed:`migration_failed`};function M(e,t){return Object.assign(Error(t),{code:e})}function ee(e,t){return e.replace(/\{(\w+)\}/g,(n,r)=>{let i=t[r];if(i===void 0)throw M(j.invalidInput,`fmt 缺少变量 {${r}}：${e}`);return String(i)})}const te={brainstorming:[`requirement`],planning:[`plan`],decomposing:[`decomposition`],implementing:[`task_detail`],accepting:[`verification`],archived:[`archive`]},N={"brainstorming>planning":`requirement`,"planning>decomposing":`plan`,"decomposing>implementing":`decomposition`,"accepting>archived":`verification`};ee(`缺陷：根因与防回归写进 guides/（故障排查手册）或 architecture/（机制性根因）——规范没有单独的 known-issues 目录，别自创平行体系`,{});const ne={pending:`⬜ 待验`,passed:{pass:`✅ 通过`,fix:`🛠 改进（需修改）`,other:`❓ 其他`}.pass,failed:`❌ 不通过`};[`## 【阶段纪律 · 需求分析】（REQ-31e11f stage-prompts；REQ-2e9473 t18：superpowers 式方法论）`,``,`当前需求处于 brainstorming（需求分析/方案共创）阶段。**按检查表逐项执行**：`,``,`1. **探索项目上下文**：先读相关文件/文档/最近变更，建立事实基础再开口问。`,`2. **范围评估先行**：请求涉及多个独立子系统时，先帮用户拆子项目——不要先扎进细节。`,`3. **澄清提问（一次一个问题）**：用弹框逐个问关键问题，理解目的/约束/成功标准/边界情况；`,`   禁止一口气抛出全套方案。`,`4. **2-3 个方案对比**：给选项时必须 2-3 个 + 优缺点/成本/风险，标注推荐项与理由。`,`5. **分节呈现设计**：需求文档分节写，每节先请用户确认再写下一节（禁止一次性全文）。`,`6. **写需求文档**：产出 requirement.md（docs/requirements/REQ-xxxxxx/，头部带 REQ id）；`,`   过程产物（原型 html 等）落进需求目录即自动登记（W4）。`,`7. **文档自查**：占位符/矛盾/模糊/范围蔓延逐项过完再提交。`,"8. **用户审阅文档**：调 `reqboard_ask_confirm`（target=artifact, kind=requirement）弹框请人确认——","   肯定答复自动落章并推进到 planning（先 `reqboard_requirement_submit` 登记产物）。",`9. **HARD-GATE**：文档未经确认不得进入技术设计/实现动作——"太简单不用走流程"是反模式，`,`   文档可以短但不能跳（代码级也会拦：artifact_not_confirmed）。`].join(`
`),[`## 【阶段纪律 · 技术设计】（REQ-31e11f stage-prompts；REQ-2e9473 t18/W7：代码层面的设计，产物是一套文档）`,``,`当前需求处于 planning（技术设计）阶段。本阶段回答**代码层面"怎么做"**：`,``,`1. **数据层**：是否需要改表/改 schema？改动清单与迁移方式。`,`2. **设计模式与框架选型**：用什么模式、为什么；优先现成框架/库减少自研`,`   （框架质量优于自写），给出选型对比。`,`3. **代码规范**：本需求涉及的命名/分层/错误处理约束。`,`4. **UI 与前端**：界面设计、实现方式/框架、排版与样式方案。`,`5. **测试用例内容**：测什么、怎么测（可执行的断言，不是"功能正常"）。`,`6. **产物是一套文档**（不是一个文件）：按主题分（如 design/architecture.md、`,`   design/ui.md、design/test-cases.md；规模小可合一），路径写进计划摘要。`,`7. **不做**：工作流划分与工作量预估属**拆分阶段**；不写实现代码；`,`   **不产出最终任务 DAG**（W7 边界：任务卡在 decomposing 阶段创作）。`,`8. **提交前自查**：占位符（TBD/待定）/矛盾/模糊/范围蔓延逐项过完；`,"   然后 `reqboard_plan_submit`（tasks 可省略）提交。","9. **计划批准走弹框**：调 `reqboard_ask_confirm`（target=plan）请人批准——",`   用户点批准即自动落章并推进到 decomposing（看板「批准计划」同样有效）。`].join(`
`),[`## 【阶段纪律 · 拆分】（REQ-31e11f stage-prompts；REQ-2e9473 t18/W7：变更盘点 + 任务卡创作）`,``,`当前需求处于 decomposing（拆分）阶段。本阶段把技术设计转成可执行任务 DAG：`,``,`1. **代码层面变更盘点**（对照需求文档 + 技术设计一套）：**新增**哪些接口/功能/文件、`,`   **修改**哪些（精确到模块/函数）、**删除**哪些——写进 decomposition.md。`,`2. **工作流划分 + 工作量预估**（从技术设计移入本阶段）。`,`3. **任务卡四要素**（每张卡必须齐全，缺一拒落库）：做什么（title/description）＋`,`   怎么做（implementation：改哪些文件/步骤/验证方式）＋怎么算完（可证伪 acceptance）＋依赖。`,"4. **落库**：`reqboard_decompose`（技术设计未含任务表时**必须传 tasks**——本工具即创作口；",`   薄卡会被代码级拒绝：缺 implementation 或 acceptance 空话）。`,"5. **拆分确认门**：调 `reqboard_ask_confirm`（target=artifact, kind=decomposition）弹框请人确认",`   任务粒度与实施卡质量——确认后自动推进到 implementing（人确认是"批了 A 落库 B"的防线）。`,`6. **禁止**：与技术设计矛盾时**退回技术设计改计划**（重新 plan_submit 并重新批准），`,`   不在拆分阶段二次创作设计；不落薄卡。`].join(`
`),[`## 【阶段纪律 · 实施】（REQ-31e11f stage-prompts；REQ-2e9473 t18/W7：文档驱动执行）`,``,`当前需求处于 implementing（照任务卡执行）阶段。本阶段纪律：`,``,`1. **开工先写实施文档**：基于需求文档 + 技术设计一套 + 拆分文档，产出`,`   implementation.md（步骤/顺序/每步验证方式）——agent 看文档执行，不凭记忆。`,"2. **按任务卡执行，不二次创作**：开工时 `reqboard_task_move(to=in_progress)` 会返回",`   任务卡全文（含实施方案 implementation）——照着做，不临时改需求/加功能/扩范围。`,"3. **完成即 `reqboard_task_report` 汇报**：做了什么/改了哪些文件/下一步——",`   结构化汇报追加到任务卡文档（开工说明书+完工记录双角色）；files_changed 会自动`,`   上浮到需求级产物清单（W4）。`,`4. **done 凭证门**：无汇报、无真实工具动作、60s 内连环关闭、页面插件未构建 → 代码级拒绝。`,`5. **优先新窗口或 subagent 分担上下文**；零会话历史时凭产物链`,`   （requirement.md → 技术设计 → decomposition.md → tasks/t-xxx.md）接续。`,`6. **收尾生成验收文档**：全部任务 done 前，汇总各任务汇报与证据，生成验收单内容`,`   （reqboard_verify_submit）——需求随后自动进入 accepting。`,"7. **遇门用弹框**：需人拍板（范围变更/方案取舍）用 `reqboard_ask_confirm`；","   普通信息征询用 `ask_user_question`。"].join(`
`),[`## 【阶段纪律 · 验收】（REQ-31e11f stage-prompts）`,``,`当前需求处于 accepting（验收）阶段。本阶段纪律：`,``,`1. **证据先行**：提交验收材料（reqboard_verify_submit）时，evidence 必须是`,`   可复核的命令+输出摘要 / 测试报告路径 / 截图路径——禁止"功能正常"这类空话；`,`   引用的路径必须真实存在（编造证据路径被代码级拒绝）。`,`2. **生成逐项验收单**：verify_submit 会产出结构化验收单（每任务验收标准 + 需求级标准，`,`   逐项带证据）——人**逐项打勾**（通过/不通过+意见），不是一句话总结。`,`3. **人看着证据决定过不过**：全部通过 → 人工门「验收通过」归档；有不通过项 → 需求自动`,`   打回 implementing 并为每个未过项生成返工任务（承接意见）。`,`4. **断点续验**：验收可被问题打断——挂起修复后重新提交，v2 只含未过项（已过项不重验）。`,`   被退回返工 → 按人意见修复后重交验收材料。`,"5. **把人请到桌前要用弹框**：用 `reqboard_ask_confirm`（target=artifact, kind=verification）",`   请人审核（附结论与证据摘要）。验收通过仍是人工决定——看板「验收通过」是并行通道。`].join(`
`),[`## 【阶段纪律 · 归档】（REQ-31e11f stage-prompts）`,``,`当前需求处于 archived（归档）阶段。本阶段纪律：`,``,`0. **归档已自动完成，本阶段是材料补齐（REQ-9f4a44）**：需求由「验收通过」直接进入`,"   archived，**无需任何人再点归档**；请立即用 `reqboard_archive_submit` 补齐归档材料",`   （目录/文档清单/合并去向/索引条目/说明书更新点），并确保 mergedInto 里的结论**真的写进了**`,`   对应项目文档。看板会以「归档材料待补」标记未补齐的需求。`,``,`1. **按分类核对文档清单**：不同需求类型（category）的必填文档与合并去向`,`   由 ARCHIVE_DOC_RULES 规定——feature→architecture/guides、bug→guides/`,`   architecture（根因与防回归）、refactor→adr/architecture、spike→rfcs/`,`   architecture/strategy-research、doc→docs/、chore→work-logs。`,`2. **合并去向必须真实写入**：归档材料里写了的 mergedInto，必须真的把那部分`,`   结论写进对应的项目文档——归档不是挪目录，是把产出并进项目文档。`,`3. **金字塔生长**：feature/refactor/spike 必须申报 manualUpdates（更新了哪份`,`   文档的哪一节、多了什么认知）；bug/doc/chore 写 manualNote 说明即可。`,`4. **索引条目**：indexEntry 一句话说清这次需求解决了什么，进归档索引供检索。`,`5. **归档无需人工门（REQ-9f4a44）**：验收通过即已归档，材料补齐是收尾动作；`,'   不再需要"请人点归档"。若材料内容有取舍需要人拍板，用 `ask_user_question` 发起。'].join(`
`);const re=[`draft`,`brainstorming`,`planning`,`decomposing`,`implementing`,`accepting`,`archived`];[...re];function ie(e){let t=e.startsWith(`session-`)?e.slice(8):e;return`w-${(t.split(`-`)[0]??t).slice(0,8)}`}const P=re,F={feature:{stages:P,confirmGates:Object.keys(N),note:`全流水线，五门全开`},bug:{stages:[`draft`,`planning`,`decomposing`,`implementing`,`accepting`,`archived`],confirmGates:[`planning>decomposing`,`decomposing>implementing`,`accepting>archived`],note:`免需求分析门：业务文档+复现定位即上下文，并入修复方案产物`},refactor:{stages:[`draft`,`planning`,`decomposing`,`implementing`,`accepting`,`archived`],confirmGates:[`planning>decomposing`,`decomposing>implementing`,`accepting>archived`],note:`免需求分析：现状+目标态并入技术设计`},spike:{stages:[`draft`,`implementing`,`accepting`,`archived`],confirmGates:[`accepting>archived`],note:`研究即实施，产物=研究报告`},doc:{stages:[`draft`,`implementing`,`accepting`,`archived`],confirmGates:[`accepting>archived`],note:`写作即实施`},chore:{stages:[`draft`,`implementing`,`accepting`,`archived`],confirmGates:[`accepting>archived`],note:`最简流程`}};function I(e){return e===void 0?F.feature:F[e]??F.feature}function ae(e,t,n){let r=`${t}>${n}`;if(I(e).confirmGates.includes(r))return N[r]}function L(e,t){let n=e.statusHistory;if(n!==void 0&&n.length>0)return n;let r=[{status:t,at:e.createdAt,by:{kind:`human`},reason:`创建`,inferred:!0}];return e.status!==void 0&&e.status!==t&&e.updatedAt!==void 0&&r.push({status:e.status,at:Math.max(e.updatedAt,e.createdAt),by:e.updatedBy??{kind:`human`},reason:`按 updatedAt 回填（当时无事件留痕）`,inferred:!0}),r}function oe(e,t,n,i,a){let o=L(e,i),s=new Map;o.forEach((e,t)=>{s.has(e.status)||s.set(e.status,t)});let c=o.map((e,t)=>({e,i:t})).filter(e=>!t.includes(e.e.status)).map(e=>e.e.status),l=(e,t)=>{if(t===void 0)return`<div class="dsh-pm-tl-row pending" data-status="`+e+`"><span class="dsh-pm-tl-label">`+(n[e]??e)+`</span><span class="dsh-pm-tl-time">—</span><span class="dsh-pm-tl-dur"></span></div>`;let i=o[t],s=o[t+1],c=t===o.length-1,l=(s?.at??a)-i.at,u=c?O(i.status)?``:`已停留 `+D(l):`停留 `+D(l),d=i.by.kind+(i.by.sessionId===void 0?``:` `+m(i.by.sessionId));return`<div class="dsh-pm-tl-row`+(c?` current`:``)+`" data-status="`+r(i.status)+`"><span class="dsh-pm-tl-label">`+(n[e]??e)+`</span><span class="dsh-pm-tl-time">`+r(h(i.at))+`</span><span class="dsh-pm-tl-dur">`+r(u)+`</span><span class="dsh-pm-tl-by">`+r(d)+`</span>`+(i.inferred===!0?`<span class="dsh-pm-tl-inferred" title="历史回填：老记录无事件留痕，由创建时间与评论反推">回填</span>`:``)+`</div>`},u=t.map(e=>l(e,s.get(e))).join(``)+c.map(e=>l(e,s.get(e))).join(``),d=o[0].at,f=o[o.length-1],p=(O(f.status)?f.at:a)-d;return`<div class="dsh-pm-timeline">`+u+`<div class="dsh-pm-tl-total">创建 `+r(h(d))+(O(f.status)?` · 总耗时 `:` · 至今 `)+r(D(p))+`</div></div>`}function se(e,t){return oe(e,[...p,`archived`],l,`draft`,t)}function ce(e,t){return oe(e,ue,u,`todo`,t)}function le(e){let t=L(e,`draft`),n=new Map;for(let e of t)n.has(e.status)||n.set(e.status,e);let i=[...n.values()].map(e=>`<span class="dsh-pm-strip-item" data-status="`+r(e.status)+`">`+(l[e.status]??e.status)+` <b>`+r(h(e.at))+`</b></span>`);return i.length===0?``:`<div class="dsh-pm-strip">`+i.join(`<span class="dsh-pm-strip-arrow">→</span>`)+`</div>`}const ue=[`todo`,`in_progress`,`integrating`,`testing`,`in_review`,`done`],de=[`draft`,`brainstorming`,`decomposing`,`implementing`,`accepting`,`done`,`archived`];function fe(e,t){let n=L(e,`todo`),r=O(e.status);return n.map((i,a)=>{let o=n[a+1]?.at??(r?Math.max(e.updatedAt,i.at):t);return{status:i.status,from:i.at,to:o}})}function pe(e,t,n){if(t.length===0)return`<div class="dsh-pm-empty">尚未拆分任务</div>`;let i=[...t].sort((e,t)=>e.createdAt-t.createdAt),a=[n];for(let e of i)for(let t of L(e,`todo`))a.push(t.at);for(let t of L(e,`draft`))a.push(t.at);let o=Math.min(...a),s=Math.max(...a),c=Math.max(s-o,36e5),d=e=>190+(e-o)/c*620,f=34+i.length*22+10,p=[];p.push(`<svg class="dsh-pm-gantt" viewBox="0 0 822 `+f+`" width="100%" height="`+f+`" preserveAspectRatio="xMinYMin meet" role="img" aria-label="任务甘特图">`);for(let e=0;e<=4;e++){let t=o+c*e/4,n=d(t).toFixed(1);p.push(`<line class="dsh-pm-gantt-grid" x1="`+n+`" y1="26" x2="`+n+`" y2="`+(f-10)+`" />`),p.push(`<text class="dsh-pm-gantt-axis" x="`+n+`" y="20" text-anchor="middle">`+r(h(t))+`</text>`)}for(let t of L(e,`draft`)){if(!de.includes(t.status))continue;let n=d(t.at).toFixed(1);p.push(`<line class="dsh-pm-gantt-mile" data-status="`+r(t.status)+`" x1="`+n+`" y1="28" x2="`+n+`" y2="`+(f-10)+`">`),p.push(`<title>`+r(e.id+` `+(l[t.status]??t.status)+` `+h(t.at))+`</title></line>`)}if(i.forEach((e,t)=>{let i=34+t*22;p.push(`<text class="dsh-pm-gantt-rowlabel" x="6" y="`+(i+13)+`">`+r(k(e.id+` `+e.title,24))+`</text>`),p.push(`<rect class="dsh-pm-gantt-track" x="190" y="`+(i+4)+`" width="620" height="13" rx="3" />`);for(let t of fe(e,n)){let n=d(t.from),a=Math.max(2,d(t.to)-n);p.push(`<rect class="dsh-pm-gantt-bar" data-status="`+r(t.status)+`" x="`+n.toFixed(1)+`" y="`+(i+4)+`" width="`+a.toFixed(1)+`" height="13" rx="3">`),p.push(`<title>`+r(e.id+` `+e.title+`｜`+(u[t.status]??t.status)+` `+h(t.from)+` → `+h(t.to)+`（`+D(t.to-t.from)+`）`)+`</title></rect>`)}}),n>=o&&n<=s){let e=d(n).toFixed(1);p.push(`<line class="dsh-pm-gantt-now" x1="`+e+`" y1="28" x2="`+e+`" y2="`+(f-10)+`"><title>现在</title></line>`)}p.push(`</svg>`);let m=`<div class="dsh-pm-gantt-legend">`+ue.map(e=>`<span class="dsh-pm-gantt-legend-item"><i data-status="`+e+`"></i>`+u[e]+`</span>`).join(``)+`<span class="dsh-pm-gantt-legend-item"><i class="mile"></i>需求里程碑</span></div>`;return`<div class="dsh-pm-gantt-wrap">`+p.join(``)+`</div>`+m}function me(e,t){return`<table class="dsh-pm-ttable"><thead><tr><th>任务</th><th>标题</th><th>状态</th><th>阶段</th><th>端侧</th><th>依赖</th><th>创建</th><th>耗时</th></tr></thead><tbody>`+[...e].sort((e,t)=>e.createdAt-t.createdAt).map(e=>{let n=L(e,`todo`),i=n[0].at,a=n[n.length-1],o=n.find(e=>e.status===`done`)?.at,s=O(e.status)?`共 `+D((o??a.at)-i):`已用 `+D(t-i);return`<tr class="dsh-pm-trow" data-task="`+r(e.id)+`" data-action="open-task"><td class="dsh-pm-tid">`+r(e.id)+`</td><td class="dsh-pm-ttitle">`+r(e.title)+`</td><td><span class="dsh-pm-status" data-status="`+r(e.status)+`">`+(u[e.status]??e.status)+`</span></td><td>`+r(d[e.phase]??e.phase)+`</td><td>`+r(e.side)+`</td><td class="dsh-pm-tdeps">`+(e.dependsOn.length>0?r(e.dependsOn.join(` `)):`—`)+`</td><td>`+r(h(i))+`</td><td>`+r(s)+`</td></tr>`}).join(``)+`</tbody></table>`}function he(e,t=Date.now()){let n=e.requirements.map(t=>({req:t,tasks:e.tasks.filter(e=>e.requirementId===t.id)})).filter(e=>e.tasks.length>0).sort((e,t)=>t.req.updatedAt-e.req.updatedAt),i=`<div class="dsh-pm-head"><button type="button" class="dsh-pm-btn" data-action="back" title="返回泳道看板">← 看板</button><h1 class="dsh-pm-title">任务</h1><span class="dsh-pm-rev">`+e.tasks.length+` 个任务 · `+n.length+` 个需求 · rev `+e.revision+`</span><button type="button" class="dsh-pm-btn" data-action="refresh" title="刷新">刷新</button></div>`;if(n.length===0)return`<div class="dsh-pm-board">`+i+`<div class="dsh-pm-empty">还没有任务。两种来源：① 需求详情页点「+ 任务」人工建卡；② 窗口 agent 调用 reqboard_decompose 真拆分落库（推荐，含依赖 DAG）</div></div>`;let a=n.map(e=>{let n=e.tasks.filter(e=>e.status===`done`).length;return`<div class="dsh-pm-tasks-group"><div class="dsh-pm-tasks-group-head"><span class="dsh-pm-card-id">`+r(e.req.id)+`</span><span class="dsh-pm-status" data-status="`+r(e.req.status)+`">`+(l[e.req.status]??e.req.status)+`</span><span class="dsh-pm-tasks-group-title">`+r(e.req.title)+`</span><span class="dsh-pm-hint">`+n+`/`+e.tasks.length+` 完成</span><button type="button" class="dsh-pm-btn sm" data-action="open-req" data-req="`+r(e.req.id)+`">打开需求</button></div>`+le(e.req)+`<div class="dsh-pm-detail-section"><h3>甘特图</h3>`+pe(e.req,e.tasks,t)+`</div><div class="dsh-pm-detail-section"><h3>任务清单</h3>`+me(e.tasks,t)+`</div></div>`}).join(``);return`<div class="dsh-pm-board">`+i+`<div class="dsh-pm-tasks-page">`+a+`</div></div>`}const ge={requirement:{icon:`📄`,label:`需求文档`},ui:{icon:`🎨`,label:`UI 文档`},proposal:{icon:`📐`,label:`设计文档`},plan:{icon:`📝`,label:`实施计划`},decomposition:{icon:`🧩`,label:`拆分方案`},task_detail:{icon:`🗂️`,label:`任务卡`},verification:{icon:`✅`,label:`验收材料`},archive:{icon:`📦`,label:`归档材料`},retro:{icon:`🔁`,label:`复盘`},notes:{icon:`📒`,label:`其他`}};function R(e){let t=e===void 0?-1:P.indexOf(e);return t<0?P.length:t}function _e(e){let t=[],n=new Set,r=(e,r)=>{let i=(r??``).trim();if(!i||n.has(i))return;n.add(i);let a=ge[e];t.push({icon:a?.icon??`📒`,label:a?.label??e,path:i})},i=[...e.artifacts??[]].sort((e,t)=>R(e.stage)-R(t.stage));for(let e of i)r(e.kind,e.path);e.docLinks?.requirement&&r(`requirement`,e.docLinks.requirement),e.docLinks?.ui&&r(`ui`,e.docLinks.ui),e.docLinks?.proposal&&r(`proposal`,e.docLinks.proposal);for(let r of e.docLinks?.extras??[]){let e=(r.path??``).trim();!e||n.has(e)||(n.add(e),t.push({icon:`🎁`,label:r.label||`成果文件`,path:e}))}e.plan?.path&&r(`plan`,e.plan.path);for(let t of e.archive?.docs??[])r(t.kind,t.path);return t}function ve(e){let t=_e(e);return t.length===0?`<div class="dsh-pm-empty">暂无文档记录。窗口 agent 可用 <code>reqboard_archive_submit</code> 提交文档清单，或通过需求更新接口填充 docLinks（requirement/ui/proposal）。</div>`:`<ul class="dsh-pm-doc-list">`+t.map(e=>`<li data-doc-path="`+r(e.path)+`"><span class="dsh-pm-doc-icon">`+e.icon+`</span><span class="dsh-pm-doc-label">`+r(e.label)+`</span><button type="button" class="dsh-pm-doc-path" data-action="open-doc" data-path="`+r(e.path)+`">`+r(e.path)+`</button></li>`).join(``)+`</ul>`}function ye(e){return e.status===`accepting`?e.verification===void 0?`<span class="dsh-pm-flag verify-pending" title="验收态但还没提交验收材料">待验收材料</span>`:`<span class="dsh-pm-flag verify-pending" title="验收材料已提交，等人工审核">待人工审核</span>`:``}function be(e){return e.status===`done`?e.archive===void 0?`<span class="dsh-pm-flag archive-pending" title="已完成，等窗口准备归档材料">待归档材料</span>`:`<span class="dsh-pm-flag archive-pending" title="归档材料已备，等人点归档">待归档</span>`:``}function xe(e){let t=e.verification;if(t===void 0)return`<div class="dsh-pm-block is-empty">`+(e.status===`implementing`||e.status===`accepting`?`窗口尚未提交验收材料。人工审核前需要证据：窗口用 <code>reqboard_verify_submit</code> 提交「做了什么 + 怎么验的 + 看到什么结果」。`:`尚未进入验收阶段。`)+`</div>`;let n=t.decision===`pass`?`<span class="dsh-pm-review" data-state="pass">人工审核通过 `+r(t.reviewedAt===void 0?``:h(t.reviewedAt))+`</span>`:t.decision===`rework`?`<span class="dsh-pm-review" data-state="rework">已退回返工 `+r(t.reviewedAt===void 0?``:h(t.reviewedAt))+`</span>`:`<span class="dsh-pm-review" data-state="pending">待人工审核</span>`,i=e.status===`accepting`?`<span class="dsh-pm-hint">请在详情头「本阶段操作」条点「验收通过」或「退回返工」</span>`:``,a=t.evidence.map(e=>`<li>`+r(e)+`</li>`).join(``);return`<div class="dsh-pm-block"><div class="dsh-pm-block-head">`+n+`<span class="dsh-pm-hint">提交 `+r(h(t.submittedAt))+`</span>`+i+`</div><div class="dsh-pm-block-summary">`+r(t.summary)+`</div><ul class="dsh-pm-evidence">`+a+`</ul>`+(t.reviewNote===void 0?``:`<div class="dsh-pm-block-note">审核意见：`+r(t.reviewNote)+`</div>`)+`</div>`}function Se(e){let t=e.archive;if(t===void 0)return`<div class="dsh-pm-block is-empty">`+(e.status===`done`?`窗口尚未准备归档材料。归档不是挪目录：窗口用 <code>reqboard_archive_submit</code> 提交需求目录、文档清单、合并去向（只允许既有规范目录：docs/ 或 agent-dh/docs/ 下的 adr|architecture|guides|rfcs|work-logs|strategy-research）与一句话索引条目，人再点归档；必填文档与合并去向按需求类型限定，规范见 agent-dh/docs/architecture/requirement-archive.md。`:`归档在需求完成（done）后进行；不同需求类型的必填文档与合并去向见 agent-dh/docs/architecture/requirement-archive.md。`)+`</div>`;let n=t.archivedAt===void 0?`<span class="dsh-pm-review" data-state="pending">待归档（材料已备）</span>`:`<span class="dsh-pm-review" data-state="pass">已归档 `+r(h(t.archivedAt))+`</span>`,i=e.status===`done`&&t.archivedAt===void 0?`<span class="dsh-pm-hint">请在详情头「本阶段操作」条点「归档」</span>`:``,a=t.docs.map(e=>`<li><span class="dsh-pm-doc-kind">`+r(Ce[e.kind]??e.kind)+`</span> <code>`+r(e.path)+`</code></li>`).join(``),o=t.mergedInto.map(e=>`<li><code>`+r(e)+`</code></li>`).join(``);return`<div class="dsh-pm-block"><div class="dsh-pm-block-head">`+n+`<code class="dsh-pm-block-path">`+r(t.dir)+`</code><span class="dsh-pm-hint">材料提交 `+r(h(t.submittedAt))+`</span>`+i+`</div><div class="dsh-pm-block-summary">索引条目：`+r(t.indexEntry)+`</div><div class="dsh-pm-doc-group"><span class="dsh-pm-hint">需求目录内的文档</span><ul class="dsh-pm-doc-list">`+a+`</ul></div><div class="dsh-pm-doc-group"><span class="dsh-pm-hint">合并进的项目文档</span><ul class="dsh-pm-doc-list">`+o+`</ul></div>`+we(t)+`</div>`}const Ce={requirement:`需求说明`,plan:`实施计划`,verification:`验收材料`,retro:`复盘`,notes:`其他`};function we(e){let t=e.manualUpdates??[];return t.length===0?e.manualNote===void 0?``:`<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">项目说明书更新</span><div class="dsh-pm-block-summary">无（`+r(e.manualNote)+`）</div></div>`:`<div class="dsh-pm-doc-group"><span class="dsh-pm-hint">项目说明书更新（金字塔向上生长）</span><ul class="dsh-pm-doc-list">`+t.map(e=>`<li><code>`+r(e.path)+`</code><span class="dsh-pm-doc-kind">`+r(e.section)+`</span><span>`+r(e.summary)+`</span></li>`).join(``)+`</ul></div>`}const Te={requirement:`需求文档`,plan:`实施计划`,decomposition:`拆分方案`,task_detail:`任务卡`,verification:`验收材料`,archive:`归档材料`};function Ee(e){let t=I(e.category),n=[];for(let r of t.confirmGates){let t=N[r];if(t===void 0)continue;let i=(e.artifacts??[]).find(e=>e.kind===t);i===void 0?n.push({kind:t,status:`missing`}):i.confirmedAt===void 0?n.push({kind:t,status:`pending`,artifact:i}):n.push({kind:t,status:`confirmed`,artifact:i})}return n}function De(e){let t=A[e.status];if(t!==void 0&&t.length!==0)for(let n of t){let t=ae(e.category,e.status,n);if(t!==void 0)return t}}function Oe(e){let t=Ee(e);return t.length===0?``:`<div class="dsh-pm-artifact-chips">`+t.map(t=>{let n=Te[t.kind]??t.kind;return t.status===`confirmed`?`<span class="dsh-pm-artifact-chip confirmed" title="`+r(n)+`已确认">✓ `+r(n)+`</span>`:t.status===`pending`?`<button type="button" class="dsh-pm-artifact-chip pending" data-action="confirm-artifact" data-id="`+r(e.id)+`" data-kind="`+r(t.kind)+`" title="点击确认`+r(n)+`">⏳ `+r(n)+`</button>`:`<span class="dsh-pm-artifact-chip missing" title="`+r(n)+`缺失">✗ `+r(n)+`</span>`}).join(``)+`</div>`}function ke(e){let t=De(e);if(t===void 0)return``;let n=(e.artifacts??[]).find(e=>e.kind===t);if(n===void 0||n.confirmedAt!==void 0)return``;let i=Te[t]??t;return`<button type="button" class="dsh-pm-btn sm primary dsh-pm-confirm-artifact" data-action="confirm-artifact" data-id="`+r(e.id)+`" data-kind="`+r(t)+`" title="一键确认`+r(i)+`，放行下一阶段">确认产物</button>`}function Ae(e){let t=I(e.category),n=[];for(let e of t.stages){let t=te[e];t!==void 0&&n.push(...t)}let r=(e.artifacts??[]).length,i=n.length,a=Ee(e).filter(e=>e.status===`pending`).length;if(i===0&&a===0)return``;let o=[];return i>0&&o.push(`产物 `+r+`/`+i),a>0&&o.push(a+` 门待确认`),`<div class="dsh-pm-artifact-derived">`+o.join(` · `)+`</div>`}function je(e,t,n=_){let{req:i,tasks:a,doneCount:o,totalCount:s,readyIds:c,blocked:l}=e,u=s>0?Math.round(o/s*100):0,d=i.category?`<span class="dsh-pm-cat" data-cat="${i.category}">${f[i.category]??i.category}</span>`:``,p=Pe(i)+ye(i)+be(i),m=l?`<span class="dsh-pm-flag blocked">阻塞</span>`:``,h=i.paused?`<span class="dsh-pm-flag paused">暂停</span>`:``,v=c.length>0?`<span class="dsh-pm-flag ready">${c.length} ready</span>`:``,y=Ne(i,t),S=b(i,n)+x(a,n),C=Me(i),w=Oe(i),T=ke(i),E=Ae(i);return`
    <div class="dsh-pm-card${l?` is-blocked`:``}${i.status===`done`?` is-archived`:``}" data-req="${r(i.id)}" data-action="open-req">
      <div class="dsh-pm-card-top">
        <span class="dsh-pm-card-id">${r(i.id)}</span>
        ${d}${p}${m}${h}${v}
      </div>
      <div class="dsh-pm-card-title">${r(i.title)}</div>
      <div class="dsh-pm-card-progress">
        <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${u}%"></div></div>
        <span class="dsh-pm-card-pct">${g(o,s)}</span>
      </div>
      ${w}
      ${E}
      ${y}
      ${S}
      ${T}
      ${C}
    </div>`}function Me(e){let t=(t,n,i)=>{let a=i?.primary===!0?`dsh-pm-btn sm primary`:`dsh-pm-btn sm`,o=i?.title===void 0?``:` title="${r(i.title)}"`;return`<button type="button" class="${a}" data-action="move-req" data-to="${t}" data-id="${r(e.id)}"${o}>${n}</button>`},n=``;switch(e.status){case`draft`:n=t(`brainstorming`,`→ 需求分析`,{primary:!0,title:`进入需求分析；窗口接手开工时会自动进入`})+t(`canceled`,`取消`,{title:`取消该需求（仅人可操作）`});break;case`brainstorming`:n=t(`planning`,`→ 技术设计`,{primary:!0,title:`方案谈定 → 进入技术设计阶段（计划在此阶段提交待人批准）`})+t(`draft`,`退回`,{title:`退回立项`});break;case`planning`:n=t(`decomposing`,`→ 拆分`,{primary:!0,title:`计划获批后落库任务卡；未获批会被代码级拒绝`})+t(`brainstorming`,`退回重谈`,{title:`方案要改 → 退回需求分析`});break;case`decomposing`:n=t(`implementing`,`→ 实施`,{primary:!0,title:`进入实施；任务开工时系统会自动推进`});break;case`implementing`:n=t(`accepting`,`→ 验收`,{primary:!0,title:`进入验收；任务全部完成时系统会自动推进`});break;case`accepting`:n=t(`archived`,`→ 归档`,{primary:!0,title:`验收通过并归档（归集文档）`});break;case`done`:n=``;break;default:n=``}return n.length===0?``:`<div class="dsh-pm-card-actions">${n}</div>`}function Ne(e,t){let n=L(e,`draft`),i=n[0],a=n[n.length-1],o=[`创建 `+h(i.at)];return a.status!==i.status&&o.push((l[a.status]??a.status)+` `+h(a.at)),O(a.status)||o.push(`已停留 `+D(t-a.at)),`<div class="dsh-pm-card-time">`+r(o.join(` · `))+`</div>`}function Pe(e){let t=e.plan;return t===void 0?``:t.approvedAt===void 0?t.rejectedAt===void 0?`<span class="dsh-pm-flag plan-pending" title="实施计划已提交，等待人批准后才能拆分">计划待批</span>`:`<span class="dsh-pm-flag plan-rejected" title="实施计划被退回，待重写">计划被退</span>`:`<span class="dsh-pm-flag plan-ok" title="实施计划已批准，可拆分落库">计划已批</span>`}function Fe(e){return e.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`).map(t=>{let n=e.tasks.filter(e=>e.requirementId===t.id);return{req:t,tasks:n,doneCount:n.filter(e=>e.status===`done`).length,totalCount:n.length,readyIds:e.ready[t.id]??[],blocked:t.blocked||n.some(e=>e.blocked)}})}function z(e,t=Date.now(),n=`lanes`,i={},a=_){let o=Fe(e),s=p.map(e=>{let n=e===`accepting`?o.filter(e=>e.req.status===`accepting`||e.req.status===`done`):o.filter(t=>t.req.status===e),r=n.map(e=>je(e,t,a)).join(``);return`
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
    </div>`,f=n===`list`?Be(e,t,i,a):`<div class="dsh-pm-lanes">${s}</div>`;return`
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
    </div>`}const B=[10,20,50];function V(e){return e===`updated`||e===`created`||e===`progress`?`desc`:`asc`}const Ie=[{key:`stage`,label:`阶段`},{key:`progress`,label:`进度`},{key:`updated`,label:`最近更新`},{key:`created`,label:`创建时间`},{key:`title`,label:`名称`}],Le={implementing:0,accepting:1,decomposing:2,planning:3,brainstorming:4,draft:5,done:6};function Re(e){return e.totalCount>0?e.doneCount/e.totalCount:0}function ze(e){switch(e){case`stage`:return(e,t)=>(Le[e.req.status]??99)-(Le[t.req.status]??99);case`progress`:return(e,t)=>Re(e)-Re(t);case`created`:return(e,t)=>e.req.createdAt-t.req.createdAt;case`title`:return(e,t)=>e.req.title.localeCompare(t.req.title,`zh-Hans-CN`);default:return(e,t)=>e.req.updatedAt-t.req.updatedAt}}function Be(e,t=Date.now(),n={},r=_){let i=n.sortKey??`stage`,o=n.sortDir??V(i),s=n.pageSize!==void 0&&B.includes(n.pageSize)?n.pageSize:10,c=Fe(e),l=c.filter(e=>e.req.status!==`done`&&e.req.status!==`archived`),u=c.filter(e=>e.req.status===`done`||e.req.status===`archived`),d=ze(i),f=o===`asc`?1:-1,p=(e,t)=>d(e,t)*f||t.req.updatedAt-e.req.updatedAt;l.sort(p),u.sort(p);let m=[...l,...u],h=Ve(i,o,c.length,l.length,u.length,s);if(m.length===0)return`<div class="dsh-pm-list">${h}<div class="dsh-pm-list-empty">暂无进行中的需求</div></div>`;let g=Math.max(1,Math.ceil(m.length/s)),v=Math.min(Math.max(1,n.page??1),g),y=m.slice((v-1)*s,v*s),b=l.length,x=(v-1)*s,S=[];for(let e=0;e<y.length;e++){let n=x+e;l.length>0&&(n===0||n===x&&n<b)&&S.push(`<tr class="dsh-pm-list-grouphead" data-group="active"><td colspan="8">进行中 ${l.length}${n>0?`（续）`:``}</td></tr>`),u.length>0&&(n===b||n===x&&n>=b)&&S.push(`<tr class="dsh-pm-list-grouphead" data-group="done"><td colspan="8">已完成 ${u.length}${n>b?`（续）`:``}</td></tr>`),S.push(He(y[e],t,r))}let C=m.length>s?`<div class="dsh-pm-pager">${a({page:v,total:g,totalItems:m.length,pageAttr:`data-pmpage`})}</div>`:``;return`<div class="dsh-pm-list">${h}<table class="dsh-pm-table"><thead><tr><th>ID</th><th>标题</th><th>分类</th><th>状态</th><th>进度</th><th>负责人</th><th>更新时间</th><th>操作</th></tr></thead><tbody>${S.join(``)}</tbody></table>${C}</div>`}function Ve(e,t,n,r,i,a){return`
    <div class="dsh-pm-list-toolbar">
      <span class="dsh-pm-list-toolbar-label">排序</span>
      ${Ie.map(({key:n,label:r})=>{let i=n===e;return`<button type="button" class="dsh-pm-sortbtn${i?` active`:``}" data-action="list-sort" data-key="${n}" title="按${r}排序（再点一次切换升降序）">${r}${i?t===`asc`?` ↑`:` ↓`:``}</button>`}).join(``)}
      <span class="dsh-pm-list-toolbar-gap"></span>
      <span class="dsh-pm-list-toolbar-label">每页</span>
      <select class="dsh-pm-pagesize" data-action="list-size" title="每页条数">${B.map(e=>`<option value="${e}"${e===a?` selected`:``}>${e}</option>`).join(``)}</select>
      <span class="dsh-pm-list-count">共 ${n} 条 · 进行中 ${r} · 已完成 ${i}</span>
    </div>`}function He(e,t,n=_){let{req:i,tasks:a,doneCount:o,totalCount:s,blocked:c}=e,u=s>0?Math.round(o/s*100):0,d=a.filter(e=>e.status!==`todo`&&e.status!==`done`&&e.status!==`canceled`).length,p=i.category?`<span class="dsh-pm-cat" data-cat="${i.category}">${f[i.category]??i.category}</span>`:``,g=c?`<span class="dsh-pm-flag blocked">阻塞</span>`:``,v=i.sourceSessionId,b=v!==void 0&&v.length>0&&n.has(v),x=v!==void 0&&v.length>0?y({sid:v,label:m(v),cls:`dsh-pm-window`,kind:`立项来源窗口`,archived:b}):`<span class="dsh-pm-list-nowindow">人工建卡</span>`,S=i.status===`archived`&&i.archive===void 0?`<span class="dsh-pm-chip is-warn">归档材料待补</span>`:``,C=`dsh-pm-list-row`+(c?` is-blocked`:``)+(i.status===`done`||i.status===`archived`?` is-archived`:``),w=v!==void 0&&v.length>0&&!b?`<button type="button" class="dsh-pm-btn sm" data-action="jump-session" data-sid="${r(v)}" title="跳转到来源会话">会话</button>`:``;return`
      <tr class="${C}" data-req="${r(i.id)}" data-action="open-req">
        <td><span class="dsh-pm-card-id">${r(i.id)}</span></td>
        <td class="dsh-pm-td-title">
          <span class="dsh-pm-list-title" data-action="open-req" data-req="${r(i.id)}">${r(i.title)}</span>
          ${g}${S}
        </td>
        <td>${p}</td>
        <td><span class="dsh-pm-status-badge" data-status="${i.status}">${l[i.status]}</span></td>
        <td class="dsh-pm-td-progress">
          <div class="dsh-pm-list-progress">
            <div class="dsh-pm-card-bar"><div class="dsh-pm-card-bar-fill" style="width:${u}%"></div></div>
            <span class="dsh-pm-list-pct">${u}%${d>0?`（${d} 进行中）`:``}</span>
          </div>
        </td>
        <td>${x}</td>
        <td><span class="dsh-pm-list-when">${h(i.updatedAt)}</span></td>
        <td><div class="dsh-pm-list-actions">${Me(i)}${w}</div></td>
      </tr>`}function Ue(e,t){let n=e.filter(e=>e.status===`pending`),i=t.requirements.filter(e=>e.status!==`archived`&&e.status!==`canceled`),a=n.map(e=>{let t=e.suggestedAction===`create_req`&&!e.suggestedTargetId,n=e.suggestedTargetId?`${e.suggestedAction===`bind_req`?`绑定需求`:e.suggestedAction===`bind_task`?`绑定任务`:`新建需求`} ${r(e.suggestedTargetId)}`:e.suggestedAction===`create_req`?`新建需求${e.suggestedCategory?` · ${f[e.suggestedCategory]??e.suggestedCategory}`:``}`:``,i=t?`
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
    </div>`}const We={draft:{label:`立项`,color:`#9aa4b2`,order:0},brainstorming:{label:`需求分析`,color:`#f0a020`,order:1},planning:{label:`技术设计`,color:`#c2255c`,order:2},decomposing:{label:`拆分`,color:`#8e44ad`,order:3},implementing:{label:`实施`,color:`#4a7dff`,order:4},accepting:{label:`验收`,color:`#17a2b8`,order:5},done:{label:`完成`,color:`#28a745`,order:6},archived:{label:`归档`,color:`#28a745`,order:7}},Ge=[`draft`,`brainstorming`,`planning`,`decomposing`,`implementing`,`accepting`,`done`,`archived`];function Ke(e){return We[e]?.order??-1}function qe(e){let t=Ke(e);return`<div class="dsh-pm-progress-dots">${Ge.map(e=>{let{label:n,order:i}=We[e];return`
        <div class="dsh-pm-dot-wrapper ${i<t?`completed`:i===t?`current`:``}">
          <div class="dsh-pm-dot"></div>
          <span class="dsh-pm-dot-label">${r(n)}</span>
        </div>`}).join(``)}</div>`}function Je(){return`
    <div class="dsh-pm-tabs">
      <button type="button" class="dsh-pm-tab active" data-action="switch-tab" data-tab="overview">📋 概览</button>
      <button type="button" class="dsh-pm-tab" data-action="switch-tab" data-tab="execution">⚙️ 执行</button>
      <button type="button" class="dsh-pm-tab" data-action="switch-tab" data-tab="timeline">📅 时间线</button>
      <button type="button" class="dsh-pm-tab" data-action="switch-tab" data-tab="archive">📦 归档</button>
    </div>`}function Ye(e,t,n,i,a){return`
    <!-- 📋 概览 Tab（默认显示；REQ-6f39b5 对齐 prototype：描述 → 当前阶段高亮卡 → 文档）-->
    <div class="dsh-pm-tab-content active" data-tab-content="overview">
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">📄 需求描述</h3>
        <div class="dsh-pm-section-content">
          ${e.description?`<div class="dsh-pm-md">${S(e.description)}</div>`:`<div class="dsh-pm-empty">暂无描述</div>`}
        </div>
      </div>
      <details class="dsh-pm-fold" open>
        <summary class="dsh-pm-section-title">🎯 当前阶段详情</summary>
        <div class="dsh-pm-stage-current">
          <div class="dsh-pm-stage-current-title">${l[e.status]}（${e.status}）</div>
          <div class="dsh-pm-stage-detail" id="dsh-pm-stage-detail-container"></div>
        </div>
      </details>
      <details class="dsh-pm-fold">
        <summary class="dsh-pm-section-title">📁 文档记录</summary>
        <div class="dsh-pm-section-content">${ve(e)}</div>
      </details>
    </div>

    <!-- ⚙️ 执行 Tab（REQ-6f39b5 严格对齐 prototype：统计卡片 + DAG + 任务表格）-->
    <div class="dsh-pm-tab-content" data-tab-content="execution">
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">总任务</div><div class="dsh-pm-stat-value">${t.length}</div></div>
        <div class="dsh-pm-stat dsh-pm-stat-success"><div class="dsh-pm-stat-label">已完成</div><div class="dsh-pm-stat-value">${t.filter(e=>e.status===`done`).length}</div></div>
        <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">进行中</div><div class="dsh-pm-stat-value">${t.filter(e=>e.status===`in_progress`).length}</div></div>
        <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">待办</div><div class="dsh-pm-stat-value">${t.filter(e=>e.status===`todo`).length}</div></div>
      </div>
      ${n}
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">📋 任务列表</h3>
        ${et(t)}
      </div>
    </div>

    <!-- 📅 时间线 Tab -->
    <div class="dsh-pm-tab-content" data-tab-content="timeline">
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">📅 状态变更记录</h3>
        <div class="dsh-pm-section-content">${se(e,a)}</div>
      </div>
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">💬 评论<span class="dsh-pm-fold-count">${e.comments.length} 条</span></h3>
        <div class="dsh-pm-section-content">
          ${i}
          <div class="dsh-pm-comment-form" data-actor="human">
            <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论（以「人」身份记录）…" />
            <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="req" data-id="${r(e.id)}">发送</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 📦 归档 Tab -->
    <div class="dsh-pm-tab-content" data-tab-content="archive">
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">✅ 验收（人工审核）</h3>
        <div class="dsh-pm-section-content">${xe(e)}</div>
      </div>
      <div class="dsh-pm-section">
        <h3 class="dsh-pm-section-title">📦 归档（文档合并）</h3>
        <div class="dsh-pm-section-content">${Se(e)}</div>
      </div>
    </div>`}function Xe(e,t,n=Date.now(),i=_){let a=t.filter(t=>t.requirementId===e.id),o=$e(a),s=w(e.comments),c=Ze(e.status),u=Qe(e);return`
    <div class="dsh-pm-detail" data-detail-req="${r(e.id)}">
      <div class="dsh-pm-detail-head">
        <button type="button" class="dsh-pm-btn" data-action="back" title="返回看板">← 看板</button>
        <span class="dsh-pm-card-id">${r(e.id)}</span>
        <span class="dsh-pm-status" data-status="${e.status}">${l[e.status]}</span>
        ${e.blocked?`<span class="dsh-pm-flag blocked">阻塞</span>`:``}
        ${b(e,i)}
        <span class="dsh-pm-detail-updated">${h(e.updatedAt)}</span>
        <h1 class="dsh-pm-detail-title">${r(e.title)}</h1>
        ${qe(e.status)}
      </div>
      ${u}
      ${c}
      ${Je()}
      ${Ye(e,a,o,s,n)}
    </div>`}function Ze(e){let t={draft:`已立项：窗口接手开工后自动进入需求分析，人可在上方操作条手动催办。`,brainstorming:`需求分析中：窗口 agent 会自行推进到技术设计，人可在上方操作条确认方案或退回立项。`,planning:`技术设计中：计划提交后请在上方操作条点「批准计划」——批准前拆分会被告代码级拒绝。`,decomposing:`拆分中：任务落库/开工后系统自动推进到实施，人可在上方操作条确认拆分。`,implementing:`实施中：任务全部完成时自动进入验收，人可在上方操作条提交验收。`,accepting:`验收中：看完验收材料后，在上方操作条点「验收通过」或「退回返工」。`,done:`已完成（历史状态）：验收通过现已直接归档，此状态仅存在于旧记录。`}[e];return t===void 0?``:`<div class="dsh-pm-gate">`+t+`</div>`}function Qe(e){let t=[],n=(n,i,a,o=!1)=>{let s=o?`dsh-pm-btn primary`:`dsh-pm-btn`;t.push(`<button type="button" class="`+s+`" data-action="`+n+`" data-id="`+r(e.id)+`" title="`+r(a)+`">`+i+`</button>`)},i=(n,i,a,o=!1)=>{let s=o?`dsh-pm-btn primary`:`dsh-pm-btn`;t.push(`<button type="button" class="`+s+`" data-action="move-req" data-to="`+n+`" data-id="`+r(e.id)+`" title="`+r(a)+`">`+i+`</button>`)};switch(e.status){case`draft`:i(`brainstorming`,`→ 需求分析`,`进入需求分析；窗口接手开工时会自动进入`,!0),i(`canceled`,`取消`,`取消该需求（仅人可操作）`);break;case`brainstorming`:i(`planning`,`→ 技术设计`,`方案谈定 → 进入技术设计；请提交计划并待批准`,!0),i(`draft`,`退回立项`,`方案要重谈 → 退回立项`);break;case`planning`:i(`decomposing`,`→ 拆分`,`计划获批后落库任务卡；未获批会被代码级拒绝`,!0),i(`brainstorming`,`退回重谈`,`方案要改 → 退回需求分析`);break;case`decomposing`:i(`implementing`,`→ 实施`,`确认拆分，进入实施；任务开工时系统会自动推进`,!0);break;case`implementing`:i(`accepting`,`→ 验收`,`提交验收；任务全部完成时系统会自动推进`,!0)}return e.plan!==void 0&&e.plan.approvedAt===void 0&&(n(`plan-approve`,`批准计划`,`批准实施计划，解锁 reqboard_decompose 拆分`,!0),n(`plan-reject`,`退回计划`,`退回实施计划（窗口按理由重写）`)),e.status===`accepting`&&e.verification!==void 0&&(n(`verify-pass`,`验收通过`,`人工审核通过，需求进入完成`,!0),n(`verify-rework`,`退回返工`,`退回返工（需填写意见）`)),e.status===`done`&&e.archive!==void 0&&e.archive.archivedAt===void 0&&n(`archive-req`,`归档`,`归档：把产出并进项目文档`,!0),t.length===0?``:`<div class="dsh-pm-action-bar" data-req="`+r(e.id)+`"><span class="dsh-pm-action-bar-label">本阶段操作</span>`+t.join(``)+`</div>`}function $e(e){if(e.length===0)return`<div class="dsh-pm-empty">暂无任务</div>`;let t=new Map,n=new Map(e.map(e=>[e.id,e])),i=(e,r)=>{if(t.has(e.id))return t.get(e.id);if(r.has(e.id))return 0;r.add(e.id);let a=e.dependsOn.filter(e=>n.has(e)),o=a.length===0?0:1+Math.max(...a.map(e=>i(n.get(e),r)));return t.set(e.id,o),o};e.forEach(e=>i(e,new Set));let a=Math.max(...t.values()),o=Array.from({length:a+1},()=>[]);return e.forEach(e=>o[t.get(e.id)].push(e)),`<div class="dsh-pm-dag"><div class="dsh-pm-dag-title">🔀 任务依赖关系</div><div class="dsh-pm-dag-layers">`+o.map((e,t)=>`
    <div class="dsh-pm-dag-layer">
      <span class="dsh-pm-dag-layer-label">L${t}</span>
      ${e.map(e=>`
        <span class="dsh-pm-dag-node" data-status="${e.status}" data-action="open-task" data-task="${r(e.id)}" title="${r(e.title)}">
          ${r(e.id)} ${r(e.title.slice(0,20))}${e.title.length>20?`…`:``}
        </span>`).join(``)}
    </div>`).join(``)+`</div></div>`}function et(e){if(e.length===0)return`<div class="dsh-pm-empty">暂无任务</div>`;let t=e=>e===`done`?`✓`:e===`in_progress`?`◐`:e===`todo`?`○`:`◐`;return`
    <table class="dsh-pm-task-table">
      <thead><tr><th>状态</th><th>任务</th><th>阶段</th><th>依赖</th><th>负责人</th><th>操作</th></tr></thead>
      <tbody>${e.map(e=>{let n=e.dependsOn.length>0?e.dependsOn.map(e=>r(e)).join(`,`):`-`,i=e.claimedBy!==void 0&&e.claimedBy.length>0?m(e.claimedBy):`-`;return`
      <tr data-action="open-task" data-task="${r(e.id)}">
        <td><span class="dsh-pm-task-status ${e.status}">${t(e.status)} ${u[e.status]}</span></td>
        <td>${r(e.title)}</td>
        <td>${d[e.phase]??e.phase}</td>
        <td>${n}</td>
        <td>${i}</td>
        <td><span class="dsh-pm-link">查看</span></td>
      </tr>`}).join(``)}</tbody>
    </table>`}function tt(e){let t=e.executions[e.executions.length-1],n=[],i=[],a={defined:0,total:0};if(t?.evidence&&t.evidence.forEach(e=>{e.match(/\.(md|txt|pdf|html)$/i)&&n.push(e),e.match(/^(GET|POST|PUT|DELETE|PATCH)\s+\//)&&i.push(e);let t=e.match(/(\d+)\/(\d+)\s*.*?completed/i);t&&(a.defined=parseInt(t[1],10),a.total=parseInt(t[2],10))}),i.length===0&&e.description){let t=e.description.match(/(GET|POST|PUT|DELETE|PATCH)\s+\/[^\s\n]+/g);t&&i.push(...t)}let o=a.total>0?Math.round(a.defined/a.total*100):0,s=n.length>0?`
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
    ${l}`}function nt(e){let t=e.executions[e.executions.length-1],n=[],i=[],a={};if(t?.evidence&&t.evidence.forEach(e=>{if(e.match(/\.(fig|sketch|xd|png|jpg|svg)$/i)&&n.push(e),e.includes(`component`)||e.includes(`组件`)){let t=e.replace(/components?[:\s]*/i,``).split(/[,，]/).map(e=>e.trim());i.push(...t)}let t=e.match(/^(color|font|spacing|radius)[:\s]+(.+)/i);t&&(a[t[1].toLowerCase()]=t[2].trim())}),i.length===0&&e.description){let t=e.description.match(/组件[：:]\s*([^\n]+)/);if(t){let e=t[1].split(/[,，、]/).map(e=>e.trim());i.push(...e)}}let o=n.length>0?`
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
    ${c}`}function rt(e){let t=e.executions[e.executions.length-1],n=``,i=[],a=[],o=[];if(t?.evidence&&t.evidence.forEach(e=>{e.match(/^recommended?[:\s]+/i)&&(n=e.replace(/^recommended?[:\s]+/i,``).trim());let t=e.match(/^(.+?)[:：]\s*(?:(\d+)\/5|([⭐★]+))/);if(t){let e=t[1].trim(),n=t[2]?parseInt(t[2],10):t[3]?.length||0;i.push({name:e,score:n})}e.match(/^risk[:\s]+/i)&&a.push(e.replace(/^risk[:\s]+/i,``).trim()),e.match(/^https?:\/\//)&&o.push(e)}),!n&&e.description){let t=e.description.match(/推荐[方案]?[：:]\s*([^\n]+)/);t&&(n=t[1].trim())}let s=i.length>0?`
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
    ${u}`}function it(e){let t=0,n=0,i=0,a=0,o=[],s=e.executions[e.executions.length-1];s?.evidence&&s.evidence.forEach(e=>{let r=e.match(/(\d+)\s*passed.*?(\d+)\s*failed.*?(\d+)\s*skipped/i);r&&(n=parseInt(r[1],10),i=parseInt(r[2],10),a=parseInt(r[3],10),t=n+i+a)}),s?.error&&s.error.split(`
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
    </div>`:``}`}function at(e){let t=e.comments.filter(e=>e.createdBy?.kind===`agent`||e.createdBy?.kind===`human`),n=e.executions[e.executions.length-1],i=!1,a=`待评审`,o=[],s=[];n?.evidence&&n.evidence.forEach(e=>{(e.toLowerCase().includes(`approved`)||e.toLowerCase().includes(`通过`))&&(i=!0,a=`已批准`),(e.toLowerCase().includes(`rejected`)||e.toLowerCase().includes(`退回`))&&(a=`已退回`),(e.startsWith(`✓`)||e.startsWith(`✅`))&&s.push(e.replace(/^[✓✅]\s*/,``));let t=e.match(/^(.+?):(\d+)\s*\[(\w+)\]\s*(.+)/);t&&o.push({file:t[1],line:t[2],severity:t[3],message:t[4],resolved:!1})});let c={low:`低`,medium:`中`,high:`高`},l={low:`#28a745`,medium:`#f0a020`,high:`#dc3545`},u=s.length>0?`
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
      ${w(t)}
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
    ${f}`}function ot(e){let t=e.executions[e.executions.length-1],n=`未知`,i=`main`,a=0,o=0,s=0,c=0,l=`进行中`,u=[],d=[];t?.evidence&&t.evidence.forEach(e=>{let t=e.match(/(.+?)\s*(?:→|->|-)\s*(.+)/);t&&(n=t[1].trim(),i=t[2].trim());let r=e.match(/(\d+)\s*commits?/i);r&&(a=parseInt(r[1],10));let f=e.match(/(\d+)\s*files?\s*changed/i);f&&(o=parseInt(f[1],10));let p=e.match(/\+(\d+)\s*-(\d+)/);p&&(s=parseInt(p[1],10),c=parseInt(p[2],10)),(e.toLowerCase().includes(`merged`)||e.toLowerCase().includes(`合并成功`))&&(l=`✅ 合并成功`),e.toLowerCase().includes(`conflict`)&&(l=`⚠️ 存在冲突`);let m=e.match(/conflict:\s*(.+?)\s*-\s*(.+)/i);m&&u.push({file:m[1].trim(),description:m[2].trim(),resolution:`待解决`});let h=e.match(/^([✓✅❌⏳])\s*(.+?):\s*(.+)/);if(h){let e=h[1]===`✓`||h[1]===`✅`?`pass`:h[1]===`❌`?`fail`:`pending`;d.push({name:h[2].trim(),status:e,details:h[3].trim()})}});let f=u.length>0?`
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
    ${p}`}function st(e){let t=e.title.toLowerCase();if(t.includes(`拆分`)||t.includes(`decompose`))return`decompose`;if(e.status===`integrating`||t.includes(`集成`)||t.includes(`联调`))return`merge`;switch(e.phase){case`doc`:return`doc`;case`ui`:return`ui`;case`analysis`:return`analysis`;case`implement`:return`implement`;case`test`:return`test`;case`review`:return`review`;case`merge`:return`merge`;default:return`generic`}}const ct={decompose:`🔀`,implement:`⚙️`,test:`🧪`,review:`👀`,merge:`🔀`,doc:`📝`,ui:`🎨`,analysis:`🔍`,generic:`📋`},lt={decompose:`拆分任务`,implement:`实施任务`,test:`测试任务`,review:`评审任务`,merge:`合并任务`,doc:`文档任务`,ui:`UI设计`,analysis:`分析任务`,generic:`任务`};function ut(e,t,n=Date.now(),i=[],a=_){let o=st(e),s=ct[o],c=lt[o],l=dt(e,o,t,i),d=ft(e,n,a);return`
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
    </div>`}function dt(e,t,n,r){switch(t){case`decompose`:return pt(e,n,r);case`implement`:return mt(e);case`test`:return it(e);case`review`:return at(e);case`merge`:return ot(e);case`doc`:return tt(e);case`ui`:return nt(e);case`analysis`:return rt(e);default:return``}}function ft(e,t,n=_){let i=e.executions.map(e=>`
    <div class="dsh-pm-exec" data-outcome="${e.outcome}">
      <span class="dsh-pm-exec-outcome">${e.outcome}</span>
      <span>${h(e.startedAt)}</span>
      ${e.sessionId?y({sid:e.sessionId,label:`会话 ${e.sessionId.slice(0,12)}…`,cls:`dsh-pm-session`,kind:`执行会话`,archived:n.has(e.sessionId)}):``}
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
        ${ce(e,t)}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>执行记录（${e.executions.length}）</h3>
        ${i||`<div class="dsh-pm-empty">暂无执行</div>`}
      </div>
      <div class="dsh-pm-detail-section">
        <h3>评论（${e.comments.length}）</h3>
        ${w(e.comments)}
        <div class="dsh-pm-comment-form" data-actor="human">
          <input type="text" class="dsh-pm-input" data-role="comment-input" placeholder="写评论（以「人」身份记录）…" />
          <button type="button" class="dsh-pm-btn" data-action="add-comment" data-target="task" data-id="${r(e.id)}">发送</button>
        </div>
      </div>
    </details>`}function pt(e,t,n){if(!t)return`<div class="dsh-pm-detail-section"><div class="dsh-pm-empty">需求数据不可用</div></div>`;let i=n.filter(e=>e.requirementId===t.id),a=i.length,o=i.filter(e=>e.status===`done`).length,s={};return i.forEach(e=>{let t=e.side===`frontend`?`UI 轨道`:e.side===`backend`?`后端轨道`:e.side===`doc`?`文档轨道`:`全栈轨道`;s[t]||(s[t]=[]),s[t].push(e)}),`
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
      ${$e(i)}
    </div>`}function mt(e){let t=[],n=e.executions[e.executions.length-1];n?.evidence&&n.evidence.forEach(e=>{let n=e.match(/^(.+?)\s*\(?\+(\d+)(?:,\s*-(\d+))?\)?$/);n&&t.push({path:n[1].trim(),added:parseInt(n[2],10),deleted:parseInt(n[3]||`0`,10)})});let i=t.reduce((e,t)=>e+t.added,0),a=t.reduce((e,t)=>e+t.deleted,0),o=t.length>0?t.map(e=>`
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
    </div>`}const ht=8e3;var gt=class extends Error{code;constructor(e,t){super(e),this.code=t}};async function _t(e){let t=await e;if(!t.ok)throw new gt(`HTTP `+t.status);let n=await t.json().catch(()=>({}));if(n.success!==!0)throw new gt(n.error??`API 返回失败`,n.code);return n.data}const H=e=>_t(fetch(e,{signal:AbortSignal.timeout(ht)})),U=(e,t)=>_t(fetch(e,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify(t),signal:AbortSignal.timeout(ht)})),vt=()=>H(`/dashboard/api/reqboard/`),yt=()=>H(`/dashboard/api/reqboard/triage`);function bt(e){return U(`/dashboard/api/reqboard/req/create`,e)}function xt(e){return U(`/dashboard/api/reqboard/req/move`,e)}function St(e){return U(`/dashboard/api/reqboard/req/plan/approve`,e)}function Ct(e){return U(`/dashboard/api/reqboard/req/plan/reject`,e)}function wt(e){return U(`/dashboard/api/reqboard/req/verify/pass`,e)}function Tt(e){return U(`/dashboard/api/reqboard/req/verify/rework`,e)}function Et(e){return U(`/dashboard/api/reqboard/req/verdicts`,e)}function Dt(e){return U(`/dashboard/api/reqboard/req/archive`,e)}function Ot(e){return H(`/dashboard/api/reqboard/requirements/`+encodeURIComponent(e)+`/stages`)}function kt(e){return U(`/dashboard/api/reqboard/req/artifact/confirm`,e)}function At(e){return U(`/dashboard/api/reqboard/task/create`,e)}function jt(e){return U(`/dashboard/api/reqboard/comment`,e)}function Mt(e){return U(`/dashboard/api/reqboard/triage/confirm`,e)}function Nt(e){return U(`/dashboard/api/reqboard/triage/rebind`,e)}function Pt(e){return U(`/dashboard/api/reqboard/triage/reject`,e)}function Ft(e){let t=new EventSource(`/dashboard/api/reqboard/events`);return t.onmessage=t=>{try{let n=JSON.parse(t.data);e(n.revision,n.kind)}catch{}},()=>t.close()}function It(e){return encodeURIComponent(e).replace(/%3A/gi,`:`)}function Lt(e){return e.split(`/`).map(It).join(`/`)}function Rt(e,t){let n=t.replace(/\\/g,`/`).replace(/^(?:\.\/)+/,``);return`dsh-resource://file/session/${It(e)}/${Lt(n)}`}function zt(e){let t=e?.sidebarRight;if(!(typeof t!=`object`||!t))return t}function Bt(){try{let e=window,t=(e.__dshPmSessions??e.__dshPmCtx?.sessions)?.list?.getSnapshot?.(),n=t?.current??t?.currentSessionId;if(typeof n==`string`&&n.length>0)return n}catch{}}function Vt(e,t,n){if(typeof n!=`string`||n.length===0)return console.error(`[dsh-pmboard] open-doc: 取不到会话 id，无法构造 session 地址`,{path:t}),!1;let r=zt(e);if(r===void 0||typeof r.openResource!=`function`)return console.error(`[dsh-pmboard] open-doc: ctx.sidebarRight 不可用（官方右侧栏未加载）`,{path:t}),!1;let i=Rt(n,t);try{return r.openResource(i),!0}catch(e){return console.error(`[dsh-pmboard] open-doc: openResource 调用失败`,{address:i,error:String(e)}),!1}}function W(){let e=()=>window;return{getSessions:()=>{try{let t=e().__dshPmSessions??e().__dshPmCtx?.sessions;if(t&&typeof t.open==`function`&&t.list)return t}catch{}},getWorkspaces:()=>{try{let t=e().__dshPmWorkspaces??e().__dshPmCtx?.workspaces;if(t&&t.list)return t}catch{}}}}function Ht(e=W()){try{let t=e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[];return new Set(t)}catch{return new Set}}async function Ut(e,t){let n=e.getSessions();if(n===void 0)return`unavailable`;let r=e=>{try{return n.list.getSnapshot().byId[e]!==void 0}catch{return!1}};if(r(t))return(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`);try{await n.refresh()}catch{}return r(t)?(e.getWorkspaces()?.list.getSnapshot().archivedSessionIds??[]).includes(t)?`archived`:(n.open(t),`opened`):`missing`}const Wt={draft:`立项`,brainstorming:`需求分析`,planning:`技术设计`,decomposing:`拆分`,implementing:`实施`,accepting:`验收`,archived:`归档`},Gt={requirement:`需求文档`,plan:`实施计划`,decomposition:`拆分方案`,task_detail:`任务卡`,verification:`验收材料`,archive:`归档材料`},Kt=[`requirement`,`plan`,`decomposition`,`task_detail`,`verification`,`archive`],qt={todo:`待开始`,in_progress:`开发中`,integrating:`联调中`,testing:`测试中`,in_review:`待评审`,done:`已完成`,canceled:`已取消`},Jt={todo:`○`,in_progress:`◐`,integrating:`◐`,testing:`◐`,in_review:`◐`,done:`✓`,canceled:`✕`};function G(e){let t=new Date(e),n=e=>String(e).padStart(2,`0`);return t.getFullYear()+`-`+n(t.getMonth()+1)+`-`+n(t.getDate())+` `+n(t.getHours())+`:`+n(t.getMinutes())}function K(e,t=Date.now()){let n=t-e;if(n<6e4)return`刚刚`;if(n<36e5)return Math.floor(n/6e4)+` 分钟前`;if(n<864e5)return Math.floor(n/36e5)+` 小时前`;let r=new Date(e),i=e=>String(e).padStart(2,`0`);return n<1728e5?`昨天 `+i(r.getHours())+`:`+i(r.getMinutes()):i(r.getMonth()+1)+`-`+i(r.getDate())}function q(e,t){return e.length>t?e.slice(0,t)+`…`:e}function J(e){if(e===void 0)return``;if(e.kind===`human`)return`人`;if(e.kind===`system`)return`系统`;let t=e.sessionId;return typeof t!=`string`||t.length===0?`Agent`:t.startsWith(`session-`)?ie(t):`sub `+ie(t)}function Yt(e){let t=e.executions??[],n=t.length>0?t[t.length-1].sessionId:e.claimedBy;return J(n===void 0?void 0:{kind:`agent`,sessionId:n})}function Xt(e){let t=e.executions??[],n=t.filter(e=>e.outcome===`failed`).length;if(e.status===`done`){let e=[...t].reverse().find(e=>e.outcome===`succeeded`&&e.endedAt!==void 0),n=e?.endedAt===void 0?``:G(e.endedAt);return{text:(n.length>0?n+` `:``)+`完成`,failed:!1}}if(e.status===`in_progress`||e.status===`integrating`||e.status===`testing`){let r=[...t].reverse().find(e=>e.outcome===`running`),i=r===void 0?``:`（`+K(r.startedAt)+`开始）`,a=n>0?` · 失败 `+n+` 次`:``;return{text:(qt[e.status]??e.status)+i+a,failed:n>0}}return n>0?{text:`失败 `+n+` 次`,failed:!0}:{text:qt[e.status]??e.status,failed:!1}}const Zt=e=>{let t=e.body,n=[t.sourceWindow?`来源窗口 `+t.sourceWindow:``,t.createdAt?G(t.createdAt):``].filter(e=>e.length>0).join(` · `);return`<div class="dsh-pm-sn-body" data-stage="draft"><div class="dsh-pm-sn-req-title">`+r(t.title)+(t.category?` <span class="dsh-pm-sn-dim">（`+r(t.category)+`）</span>`:``)+`</div>`+(t.description?`<div class="dsh-pm-sn-text">`+r(t.description)+`</div>`:`<div class="dsh-pm-sn-empty">暂无描述</div>`)+(n.length>0?`<div class="dsh-pm-sn-dim">`+r(n)+`</div>`:``)+`</div>`},Qt=e=>{let t=e.body.comments??[];return t.length===0?`<div class="dsh-pm-sn-body" data-stage="brainstorming"><div class="dsh-pm-sn-empty">暂无评论</div></div>`:`<div class="dsh-pm-sn-body" data-stage="brainstorming">`+t.map(e=>{let t=J(e.createdBy);return`<div class="dsh-pm-sn-comment"><div class="dsh-pm-sn-comment-who" data-actor="`+r(e.createdBy?.kind??`agent`)+`">`+r(t)+`</div><div class="dsh-pm-sn-comment-text">`+r(e.body)+`</div></div>`}).join(``)+`</div>`},$t=e=>{let t=e.body;if(!t.plan)return`<div class="dsh-pm-sn-body" data-stage="planning"><div class="dsh-pm-sn-empty">尚未提交实施计划</div></div>`;let n=t.plan,i=n.approvedAt===void 0?n.rejectedAt===void 0?`提交：`+G(n.submittedAt)+` · 待批准`:`退回：`+G(n.rejectedAt)+(n.rejectedReason?` · `+n.rejectedReason:``):`批准：`+(n.approvedBy?.kind===`human`?`人`:`Agent`)+` · `+G(n.approvedAt);return`<div class="dsh-pm-sn-body" data-stage="planning">`+(n.summary?`<div class="dsh-pm-sn-text">`+r(n.summary)+`</div>`:``)+`<div class="dsh-pm-sn-dim">`+n.tasks.length+` 个任务 · `+r(i)+`</div></div>`};function en(e){let t=new Map(e.map(e=>[e.id,e])),n=new Map;function r(e){if(n.has(e))return n.get(e);let i=t.get(e);if(!i||!i.dependsOn||i.dependsOn.length===0)return n.set(e,0),0;let a=1+Math.max(...i.dependsOn.map(e=>r(e)));return n.set(e,a),a}for(let t of e)r(t.id);let i=new Map;for(let t of e){let e=n.get(t.id)??0;i.has(e)||i.set(e,[]),i.get(e).push(t)}return i}const tn=e=>{let t=e.body.tasks??[];if(t.length===0)return`<div class="dsh-pm-sn-body" data-stage="decomposing"><div class="dsh-pm-sn-empty">尚未拆分任务</div></div>`;let n=en(t),i=[];for(let[e,t]of[...n.entries()].sort((e,t)=>e[0]-t[0])){let n=e===0?`第 1 层 · 无依赖`:`第 `+(e+1)+` 层`+(t.length>1?` · `+t.length+` 个可并行`:``),a=t.map(e=>`<div class="dsh-pm-sn-dag-task"><span class="dsh-pm-sn-task-id">`+r(e.id)+`</span><span class="dsh-pm-sn-text">`+r(e.title)+`</span></div>`).join(``);i.push(`<div class="dsh-pm-sn-dag-layer"><div class="dsh-pm-sn-dag-label">`+r(n)+`</div>`+a+`</div>`)}return`<div class="dsh-pm-sn-body" data-stage="decomposing">`+i.join(``)+`</div>`},nn=e=>{let t=e.body,n=t.tasks??[];if(n.length===0)return`<div class="dsh-pm-sn-body" data-stage="implementing"><div class="dsh-pm-sn-empty">暂无执行任务</div></div>`;let i=n.filter(e=>e.status===`in_progress`||e.status===`integrating`||e.status===`testing`),a=n.filter(e=>e.status===`done`),o=n.filter(e=>e.status===`todo`||e.status===`in_review`),s=e=>{let t=Jt[e.status]??`○`,n=Yt(e),a=Xt(e),o=(i.includes(e)?` is-current`:``)+(a.failed?` is-failed`:``),s=[e.id,n,a.text].filter(e=>e.length>0).join(` · `),c=e.cardDoc?` · <button type="button" class="dsh-pm-sn-doc" data-action="open-doc" data-path="`+r(e.cardDoc)+`">任务卡</button>`:``;return`<div class="dsh-pm-sn-task`+o+`" data-status="`+r(e.status)+`"><div class="dsh-pm-sn-task-line1"><span class="dsh-pm-sn-task-glyph">`+t+`</span><span class="dsh-pm-sn-task-title">`+r(e.title)+`</span></div><div class="dsh-pm-sn-task-line2">`+r(s)+c+`</div></div>`},c=[];i.length>0&&c.push(`<div class="dsh-pm-sn-group"><div class="dsh-pm-sn-group-label is-active">进行中 `+i.length+` 个</div>`+i.map(s).join(``)+`</div>`),a.length>0&&c.push(`<div class="dsh-pm-sn-group"><div class="dsh-pm-sn-group-label">已完成 `+a.length+` 个</div>`+a.map(s).join(``)+`</div>`),o.length>0&&c.push(`<div class="dsh-pm-sn-group"><div class="dsh-pm-sn-group-label">待开始 `+o.length+` 个</div>`+o.map(s).join(``)+`</div>`);let l=Object.entries(t.byWindow??{}),u=l.length>1?`<div class="dsh-pm-sn-dim">窗口分工：`+l.map(([e,t])=>r(e)+` `+t.length+` 任务`).join(` · `)+`</div>`:``;return`<div class="dsh-pm-sn-body" data-stage="implementing">`+c.join(``)+u+`</div>`};function rn(e,t){let n=t.sheet;if(n===void 0||n.items.length===0)return``;let i=e.requirementId??``,a={...ne},o=n.items.map(e=>{let t=e.status!==`pending`,n=e.source.kind===`requirement`?`requirement`:e.source.taskId;return`<div class="dsh-pm-vitem" data-item-id="`+r(e.id)+`" data-source="`+r(n)+`"><div class="dsh-pm-vitem-head"><span class="dsh-pm-vitem-badge">`+(a[e.status]??r(e.status))+`</span><span class="dsh-pm-vitem-src">`+r(e.source.kind===`requirement`?`需求级`:e.source.taskId)+`</span></div><div class="dsh-pm-sn-text">`+r(q(e.criterion,200))+`</div>`+(t?e.opinion?`<div class="dsh-pm-sn-warn">意见：`+r(q(e.opinion,200))+`</div>`:``:`<div class="dsh-pm-vitem-actions"><label><input type="radio" name="verdict-`+r(e.id)+`" value="passed"> 通过</label><label><input type="radio" name="verdict-`+r(e.id)+`" value="failed"> 不通过</label><input type="text" class="dsh-pm-vitem-opinion" placeholder="不通过时填意见（必填）"></div>`)+`</div>`}).join(``),s=n.items.every(e=>e.status!==`pending`);return`<div class="dsh-pm-vsheet" data-req="`+r(i)+`" data-version="`+n.version+`"><div class="dsh-pm-sn-label">验收单 v`+n.version+(n.reworkOnly===!0?`（返工续验：只含未过项）`:``)+` · 共 `+n.items.length+` 项</div>`+o+(s?`<div class="dsh-pm-sn-dim">本轮已裁决完毕：全部通过请点上方「验收通过」归档；有未过项已自动打回返工。</div>`:`<button type="button" class="dsh-pm-btn sm primary" data-action="submit-verdicts" data-req="`+r(i)+`" data-version="`+n.version+`">提交裁决</button>`)+`</div>`}const an={draft:{renderBody:Zt},brainstorming:{renderBody:Qt},planning:{renderBody:$t},decomposing:{renderBody:tn},implementing:{renderBody:nn},accepting:{renderBody:e=>{let t=e.body;if(!t.verification)return`<div class="dsh-pm-sn-body" data-stage="accepting"><div class="dsh-pm-sn-empty">尚未提交验收材料</div></div>`;let n=t.verification,i=rn(e,n),a=(n.evidence??[]).slice(0,5),o=a.map(e=>`<div class="dsh-pm-sn-line"><span class="dsh-pm-sn-text">- `+r(q(e,140))+`</span></div>`).join(``);return`<div class="dsh-pm-sn-body" data-stage="accepting">`+(n.summary?`<div class="dsh-pm-sn-text">`+r(n.summary)+`</div>`:``)+i+(a.length>0?`<div class="dsh-pm-sn-label">证据（`+(n.evidence??[]).length+` 条）</div>`+o:``)+(n.reviewNote?`<div class="dsh-pm-sn-warn">审核意见：`+r(q(n.reviewNote,200))+`</div>`:``)+`</div>`}},archived:{renderBody:e=>{let t=e.body;if(!t.archive)return`<div class="dsh-pm-sn-body" data-stage="archived"><div class="dsh-pm-sn-empty">暂无归档材料</div></div>`;let n=t.archive,i=(n.mergedInto?.length??0)>0?`<div class="dsh-pm-sn-dim">合并去向：`+(n.mergedInto??[]).map(e=>`<button type="button" class="dsh-pm-sn-doc" data-action="open-doc" data-path="`+r(e)+`">`+r(e)+`</button>`).join(` · `)+`</div>`:``;return`<div class="dsh-pm-sn-body" data-stage="archived"><div class="dsh-pm-sn-text">归档目录：`+r(n.dir)+`</div>`+(n.indexEntry?`<div class="dsh-pm-sn-text">`+r(n.indexEntry)+`</div>`:``)+i+`</div>`}}};function on(e){return e.length===0?``:`<div class="dsh-pm-sn-label">动态</div>`+e.slice(-5).reverse().map(e=>{let t=J(e.by),n=e.reason!==void 0&&e.reason.length>0?e.reason:Wt[e.status]??e.status,i=e.inferred===!0?` <span class="dsh-pm-sn-dim">(回填)</span>`:``;return`<div class="dsh-pm-sn-comment"><div class="dsh-pm-sn-comment-who">`+r([t,K(e.at)].filter(e=>e.length>0).join(` · `))+i+`</div><div class="dsh-pm-sn-comment-text">`+r(n)+`</div></div>`}).join(``)}function sn(e){let t=e.artifacts??[],n=te[e.stage]??[];if(t.length===0&&n.length===0)return``;let i=new Map;for(let e of t){let t=i.get(e.kind)??[];t.push(e),i.set(e.kind,t)}let a=[];for(let e of Kt){let t=i.get(e);if(!t||t.length===0)continue;let n=Gt[e]??e;if(e===`task_detail`){a.push(`<span class="dsh-pm-trace-node" data-kind="`+r(e)+`"><span class="dsh-pm-sn-dim">`+r(n)+`×`+t.length+`</span></span>`);continue}for(let i of t)a.push(`<span class="dsh-pm-trace-node" data-kind="`+r(e)+`"><button type="button" class="dsh-pm-sn-doc dsh-pm-trace-path" data-action="open-doc" data-path="`+r(i.path)+`">`+r(n)+`</button></span>`)}let o=new Set(t.map(e=>e.kind));for(let e of n)if(!o.has(e)){let t=Gt[e]??e;a.push(`<span class="dsh-pm-trace-node is-missing" data-kind="`+r(e)+`"><span class="dsh-pm-sn-doc is-missing">`+r(t)+`（缺失）</span></span>`)}return a.length===0?``:`<div class="dsh-pm-trace-chain">`+a.join(`<span class="dsh-pm-trace-arrow">→</span>`)+`</div>`}function cn(e){if(!e.enabled)return`本分类跳过`;switch(e.stage){case`draft`:return`已立项`;case`brainstorming`:{let t=e.body.comments?.length??0;return t>0?t+` 条评论`:`需求分析`}case`planning`:{let t=e.body;return t.plan?t.plan.approvedAt===void 0?t.plan.rejectedAt===void 0?`计划待批准`:`计划被退回`:`计划已批准`:`待提交计划`}case`decomposing`:{let t=e.body.tasks?.length??0;return t>0?t+` 个任务`:`待拆分`}case`implementing`:{let t=e.body.tasks??[],n=t.length;if(n===0)return`暂无任务`;let r=t.filter(e=>e.status===`done`).length,i=t.find(e=>e.status===`in_progress`||e.status===`integrating`||e.status===`testing`),a=r+`/`+n+` 完成`;return n-r>0&&(a+=` · 剩 `+(n-r)+` 个`),i!==void 0&&(a+=` · 进行中 `+i.id),a}case`accepting`:{let t=e.body;return t.verification?t.verification.decision===`pass`?`验收通过`:t.verification.decision===`rework`?`验收被退回返工`:`待人工审核`:`待提交验收材料`}case`done`:return;case`archived`:return`已归档`}}function ln(e,t={}){let n=e.enabled?t.state??`current`:`skipped`,i=cn(e),a=e.timeline.length>0?e.timeline[e.timeline.length-1].at:void 0,o=e.pendingConfirmation?`<div class="dsh-pm-sn-warn">⚠ 有产物待人工确认</div>`:``,s=e.stage===`done`?void 0:an[e.stage],c=e.enabled?s?s.renderBody(e):`<div class="dsh-pm-sn-empty">未知阶段</div>`:`<div class="dsh-pm-sn-body" data-stage="`+r(e.stage)+`"><div class="dsh-pm-sn-empty">该阶段在当前分类流程中不适用</div></div>`;return`<div class="dsh-pm-stage-panel dsh-pm-sn" data-stage="`+r(e.stage)+`" data-state="`+n+`"><div class="dsh-pm-sn-head"><span class="dsh-pm-sn-title">`+r(i)+`</span>`+(a===void 0?``:`<span class="dsh-pm-sn-time">`+r(K(a))+`</span>`)+`</div>`+sn(e)+o+c+on(e.timeline)+`</div>`}function un(e,t){let n=e.stages.find(e=>e.stage===t);if(n===void 0||!n.enabled)return`skipped`;let r=P.indexOf(e.currentStage),i=P.indexOf(t);return r>=0&&i<r?`done`:i===r?`current`:`pending`}function dn(e,t){let n=e.stages.find(e=>e.stage===t)??e.stages[0];return n===void 0?`<div class="dsh-pm-sn-empty">未知节点</div>`:ln(n,{state:un(e,n.stage)})}const Y=`dsh-pmboard:view`;function fn(){try{return sessionStorage.getItem(Y)===`list`?`list`:`lanes`}catch{return`lanes`}}function pn(e){try{sessionStorage.setItem(Y,e)}catch{}}const mn=`dsh-pmboard:list`,hn=[`stage`,`progress`,`updated`,`created`,`title`];function gn(){let e={sortKey:`stage`,sortDir:`asc`,pageSize:10};try{let t=sessionStorage.getItem(mn);if(t===null)return e;let n=JSON.parse(t),r=typeof n.sortKey==`string`&&hn.includes(n.sortKey)?n.sortKey:e.sortKey;return{sortKey:r,sortDir:n.sortDir===`asc`||n.sortDir===`desc`?n.sortDir:V(r),pageSize:typeof n.pageSize==`number`&&B.includes(n.pageSize)?n.pageSize:10}}catch{return e}}function _n(e,t){let n=t.length>18?t.slice(0,18)+`…`:t;switch(e){case`archived`:return`该会话已归档（`+n+`）：日志保留、侧栏不可见，无法跳转`;case`missing`:return`该会话不在当前会话列表（`+n+`）：可能已删除或不在当前工作区`;case`unavailable`:return`会话服务暂不可用（页面注入未就绪），请刷新页面后重试`;case`opened`:return``;default:return`会话跳转结果未知：`+String(e)}}function vn(){return{openBoard:()=>{},closeBoard:()=>{},toggleBoard:()=>{},getSnapshot:()=>({boardOpen:!1}),refresh:()=>{}}}function yn(e){let t,n=[],r={kind:`board`},a=fn(),s=gn(),l=s.sortKey,u=s.sortDir,d=s.pageSize,f=1,p,m,h,g=()=>({sortKey:l,sortDir:u,page:f,pageSize:d}),_=()=>Ht(),v=()=>{try{sessionStorage.setItem(mn,JSON.stringify({sortKey:l,sortDir:u,pageSize:d}))}catch{}},y=e=>{m!==void 0&&m.querySelectorAll(`[data-action="load-stage"]`).forEach(t=>{e!==void 0&&t.dataset.stage===e?t.setAttribute(`data-active`,`true`):t.removeAttribute(`data-active`)})},b=()=>{if(m===void 0)return;if(t===void 0){m.innerHTML=T();return}let e=r;switch(e.kind){case`board`:m.innerHTML=z(t,Date.now(),a,g(),_());break;case`req`:{let n=t.requirements.find(t=>t.id===e.reqId);m.innerHTML=n?Xe(n,t.tasks,Date.now(),_()):z(t,Date.now(),a,g(),_()),n?(y(p),D(),O(n.id,n.status)):r={kind:`board`};break}case`task`:{let n=t.tasks.find(t=>t.id===e.taskId),i=n?t.requirements.find(e=>e.id===n.requirementId):void 0;m.innerHTML=n?ut(n,i,Date.now(),t.tasks,_()):z(t,Date.now(),a,g(),_()),n||(r={kind:`board`});break}case`tasks`:m.innerHTML=he(t);break;case`triage`:m.innerHTML=Ue(n,t)}},x=async()=>{try{let[e,r]=await Promise.all([vt(),yt()]);t=e,n=r.pending,b()}catch(e){m!==void 0&&(m.innerHTML=E(String(e)))}},S=()=>{h?.(),h=Ft(()=>{x()})},C=e=>{let i=e.target,o=i.closest(`[data-pmpage]`);if(o!==null&&t!==void 0){let e=Number(o.dataset.pmpage);Number.isFinite(e)&&e>=1&&(f=e,b());return}let s=i.closest(`[data-action]`);if(s!==null&&t!==void 0)switch(s.dataset.action??``){case`refresh`:x();return;case`switch-view`:{let e=s.dataset.view;(e===`lanes`||e===`list`)&&(a=e,pn(e),r={kind:`board`},b());return}case`list-sort`:{let e=s.dataset.key;if(e===void 0||!hn.includes(e))return;e===l?u=u===`asc`?`desc`:`asc`:(l=e,u=V(e)),f=1,v(),b();return}case`open-doc`:{let e=s.dataset.path;e&&Vt(window.__dshPmCtx,e,Bt());return}case`switch-tab`:{let e=i.closest(`.dsh-pm-tab`);if(!e)return;let t=e.dataset.tab;if(!t)return;let n=e.closest(`.dsh-pm-detail`);if(!n)return;n.querySelectorAll(`.dsh-pm-tab`).forEach(e=>{e.classList.remove(`active`)}),e.classList.add(`active`),n.querySelectorAll(`.dsh-pm-tab-content`).forEach(e=>{e.classList.remove(`active`)});let r=n.querySelector(`.dsh-pm-tab-content[data-tab-content="${t}"]`);r&&r.classList.add(`active`);return}case`load-stage`:{let e=s.dataset.req,t=s.dataset.stage;e&&t&&(p=t,y(t),O(e,t));return}case`confirm-artifact`:{let e=s.dataset.id,t=s.dataset.kind;e&&t&&kt({id:e,kind:t}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`submit-verdicts`:{let e=s.dataset.req,t=Number(s.dataset.version),n=s.closest(`.dsh-pm-vsheet`);if(!e||!Number.isFinite(t)||n===null)return;let r=[];if(n.querySelectorAll(`.dsh-pm-vitem`).forEach(e=>{let t=e.dataset.itemId;if(t===void 0)return;let n=e.querySelector(`input[type="radio"]:checked`);if(n===null)return;let i=e.querySelector(`.dsh-pm-vitem-opinion`)?.value.trim()??``;r.push({itemId:t,status:n.value===`passed`?`passed`:`failed`,...i.length>0?{opinion:i}:{}})}),r.length===0){window.alert(`请先逐项选择 通过/不通过`);return}Et({id:e,version:t,verdicts:r}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`new-req`:{let e=window.prompt(`需求标题`);e&&e.trim()&&bt({title:e.trim()}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`open-req`:s.dataset.req&&(p=void 0,r={kind:`req`,reqId:s.dataset.req},b());return;case`open-task`:s.dataset.task&&(r={kind:`task`,taskId:s.dataset.task},b());return;case`open-tasks`:p=void 0,r={kind:`tasks`},b();return;case`new-task`:{let e=s.dataset.id;if(!e)return;let t=window.prompt(`任务标题`);t&&t.trim()&&At({requirementId:e,title:t.trim(),phase:`implement`,side:`fullstack`}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`back`:p=void 0,r={kind:`board`},b();return;case`back-req`:p=void 0,r={kind:`req`,reqId:s.dataset.req??``},b();return;case`move-req`:{let e=s.dataset.id??(r.kind===`req`?r.reqId:void 0),t=s.dataset.to;e&&t&&xt({id:e,to:t,actor:`human`,reason:s.dataset.id?`看板泳道卡面操作`:`需求详情页操作`}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`add-comment`:{let e=(m?.querySelector(`[data-role="comment-input"]`))?.value.trim();e&&s.dataset.target&&s.dataset.id&&jt({target:s.dataset.target,id:s.dataset.id,body:e,actor:`human`}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`jump-session`:{let e=s.dataset.sid;if(!e)return;if(s.dataset.archived===`true`){window.alert(_n(`archived`,e));return}Ut(W(),e).then(t=>{let n=_n(t,e);n!==``&&window.alert(n)}).catch(e=>window.alert(`会话跳转失败：`+String(e)));return}case`verify-pass`:{let e=s.dataset.id;e&&wt({id:e}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`verify-rework`:{let e=s.dataset.id;if(!e)return;let t=window.prompt(`退回返工的意见（窗口会按它整改）`);if(t===null)return;Tt({id:e,note:t.trim()||`（未填意见）`}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`archive-req`:{let e=s.dataset.id;e&&Dt({id:e}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`plan-approve`:{let e=s.dataset.id;e&&St({id:e}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`plan-reject`:{let e=s.dataset.id;if(!e)return;let t=window.prompt(`退回理由（窗口会按它重写计划）`);if(t===null)return;Ct({id:e,reason:t.trim()||`（未填理由）`}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`triage-confirm`:{let e=s.dataset.triage;if(!e)return;let t=n.find(t=>t.id===e);if(t?.suggestedAction===`bind_req`&&t.suggestedTargetId)Mt({triageId:e,action:`bind_req`,targetId:t.suggestedTargetId}).then(()=>x()).catch(e=>window.alert(String(e)));else{let t=s.closest(`.dsh-pm-triage`),n=t?.querySelector(`[data-role="triage-title"]`)?.value.trim(),r=t?.querySelector(`[data-role="triage-category"]`)?.value;Mt({triageId:e,action:`create_req`,...n?{title:n}:{},...r?{category:r}:{}}).then(()=>x()).catch(e=>window.alert(String(e)))}return}case`triage-rebind`:{let e=m?.querySelector(`.dsh-pm-rebind-host`);e&&(e.style.display=`flex`,e.dataset.triage=s.dataset.triage??``);return}case`triage-rebind-confirm`:{let e=m?.querySelector(`.dsh-pm-rebind-host`),t=e?.dataset.triage,n=e?.querySelector(`[data-role="rebind-select"]`);t&&n?.value&&Nt({triageId:t,targetId:n.value}).then(()=>x()).catch(e=>window.alert(String(e)));return}case`triage-reject`:{let e=s.dataset.triage;e&&Pt({triageId:e}).then(()=>x()).catch(e=>window.alert(String(e)));return}}},w=e=>{let t=e.target;if(t===null||typeof t.closest!=`function`)return;let n=t.closest(`[data-action="list-size"]`);if(n!==null){let e=Number(n.value);if(!B.includes(e))return;d=e,f=1,v(),b();return}},D=async()=>{if(m===void 0)return;let e=m.querySelectorAll(`[data-doc-path]`);await Promise.all(Array.from(e).map(async e=>{let t=e.dataset.docPath;if(!t)return;let n=!1;try{n=(await(await fetch(`/dashboard/api/reqboard/file?path=`+encodeURIComponent(t))).json()).success===!0}catch{n=!1}if(!n){e.classList.add(`is-missing`),e.setAttribute(`title`,`文件不存在（未落盘或路径错误）`);let t=e.querySelector(`[data-action="open-doc"]`);t&&(t.removeAttribute(`data-action`),t.classList.add(`dsh-pm-doc-missing`))}}))},O=async(e,t)=>{let n=document.getElementById(`dsh-pm-stage-detail-container`);if(n!==null){n.innerHTML=`<div class="dsh-pm-empty">详情加载中…</div>`;try{let r=await fetch(`/dashboard/api/reqboard/requirements/`+encodeURIComponent(e)+`/stages`,{signal:AbortSignal.timeout(8e3)});if(!r.ok){n.innerHTML=`<div class="dsh-pm-empty">详情暂不可用（HTTP `+r.status+`）</div>`;return}let i=await r.json();n.innerHTML=i.success===!0&&i.data!==void 0?dn(i.data,t):`<div class="dsh-pm-empty">详情暂不可用</div>`}catch(e){n.innerHTML=`<div class="dsh-pm-empty">详情加载失败：`+String(e)+`</div>`}}},k=i({prefix:`dsh-pm`,panelName:o,activeAttr:`data-dsh-pm-active`,otherActiveAttrs:c,pollMs:2e4,pauseOnHidden:!0,buildContainer:()=>{let e=document.createElement(`div`);return e.dataset.dshPmView=``,e.className=`dsh-pm-view`,e},onMount:e=>(m=e,e.addEventListener(`click`,C),e.addEventListener(`change`,w),x(),S(),()=>{e.removeEventListener(`click`,C),e.removeEventListener(`change`,w),h?.(),h=void 0,m=void 0}),onPoll:()=>{x()},onOpen:()=>{x()}}),A=e;return A.openBoard=k.open,A.closeBoard=k.close,A.toggleBoard=k.toggle,A.getSnapshot=()=>({boardOpen:k.isActive()}),A.refresh=()=>{x()},()=>{k.dispose()}}const bn=`dsh-pmboard/footer-action.css`,X=`dsh-pmboard:open-board`,xn={draft:`立项`,brainstorming:`需求分析`,planning:`技术设计`,decomposing:`拆分`,implementing:`实施中`,accepting:`待验收`,done:`完成`},Sn=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function Cn(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${bn}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=bn,e.textContent=`
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
`,document.head.appendChild(e)}function wn(t){let{wide:n}=t,r=s,[i,a]=(0,e.useState)(!1),[o,c]=(0,e.useState)(null),[l,u]=(0,e.useState)(null),d=(0,e.useRef)(0),f=(0,e.useRef)(null),p=(0,e.useRef)(null),m=(0,e.useRef)(new Set),h=(0,e.useCallback)(async e=>{if(!(!e&&d.current>0&&Date.now()-d.current<15e3))try{let e=await(await fetch(`/dashboard/api/reqboard/requirements/summary`,{signal:AbortSignal.timeout(8e3)})).json().catch(()=>({}));e.success===!0?(m.current=Ht(),c(e.data?.requirements??[]),u(null),d.current=Date.now()):u(e.error??`加载失败`)}catch(e){u(String(e))}},[]),g=(0,e.useCallback)(()=>{p.current!==null&&(window.clearTimeout(p.current),p.current=null),!i&&(f.current=window.setTimeout(()=>{a(!0),h(!1)},120))},[i,h]),_=(0,e.useCallback)(()=>{f.current!==null&&(window.clearTimeout(f.current),f.current=null),p.current=window.setTimeout(()=>a(!1),200)},[]),v=(0,e.useCallback)(e=>{let t=e.sourceSessionId;if(t===null||t.length===0||m.current.has(t)){window.dispatchEvent(new CustomEvent(X,{detail:{open:!0}}));return}Ut(W(),t).then(e=>{e===`archived`?window.alert(`该会话已归档（日志保留，侧栏不可见）`):e===`missing`?window.alert(`该会话不在当前列表（可能已删除）`):e===`unavailable`&&window.alert(`会话服务暂不可用，已打开项目看板`),e!==`opened`&&window.dispatchEvent(new CustomEvent(X,{detail:{open:!0}}))})},[]),y=(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-reqboard-foot wide`:`dsh-reqboard-foot rail`,title:`${r}（悬停查看进行中需求）`,"aria-label":r,onClick:()=>{window.dispatchEvent(new CustomEvent(X,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},Sn),(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-label`,key:`l`},r)]:(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},Sn));if(!i)return(0,e.createElement)(`div`,{className:`dsh-reqboard-foot-wrap${n?``:` rail`}`,onMouseEnter:g,onMouseLeave:_},y);let b=o===null?(0,e.createElement)(`div`,{className:`dsh-reqboard-empty`},l===null?`加载中…`:`加载失败：${l}`):o.length===0?(0,e.createElement)(`div`,{className:`dsh-reqboard-empty`},`暂无进行中的需求`):o.map(t=>{let n=Number.isFinite(t.percentage)?t.percentage:0,r=t.sourceSessionId,i=r!==null&&r.length>0,a=i&&m.current.has(r);return(0,e.createElement)(`button`,{key:t.id,type:`button`,className:`dsh-reqboard-item${a?` is-archived`:``}`,title:a?`${t.id}《${t.title}》— 来源会话 ${r} 已归档，无法跳转（点击打开看板）`:i?`${t.id}《${t.title}》— 点击跳转到会话 ${r}`:`${t.id}《${t.title}》— 人工建卡，无来源会话（点击打开看板）`,onClick:()=>v(t)},(0,e.createElement)(`div`,{className:`dsh-reqboard-item-top`,key:`top`},[(0,e.createElement)(`span`,{className:`dsh-reqboard-item-title`,key:`t`},`${t.id} ${t.title}`),(0,e.createElement)(`span`,{className:`dsh-reqboard-badge`,"data-status":t.status,key:`b`},xn[t.status]??t.status)]),(0,e.createElement)(`div`,{className:`dsh-reqboard-item-meta`,key:`meta`},[t.windowCode===null?(0,e.createElement)(`span`,{key:`w`},`人工建卡`):(0,e.createElement)(`span`,{className:`dsh-reqboard-win${a?` is-archived`:``}`,key:`w`,title:a?`该会话已归档`:void 0},t.windowCode),(0,e.createElement)(`span`,{key:`s`},t.tasksTotal>0?`${t.tasksTotal} 任务${t.tasksActive>0?` · ${t.tasksActive} 进行中`:``}`:`未拆分`),(0,e.createElement)(`span`,{className:`dsh-reqboard-jump${a?` is-archived`:``}`,key:`j`},a?`已归档`:i?`跳转 →`:`看板 →`)]),(0,e.createElement)(`div`,{className:`dsh-reqboard-bar`,key:`bar`},[(0,e.createElement)(`span`,{className:`dsh-reqboard-bar-track`,key:`tr`},(0,e.createElement)(`i`,{className:`dsh-reqboard-bar-fill`,style:{width:`${n}%`}})),(0,e.createElement)(`span`,{className:`dsh-reqboard-bar-num`,key:`n`},`${t.tasksDone}/${t.tasksTotal}`)]))}),x=(0,e.createElement)(`div`,{className:`dsh-reqboard-drop`,onMouseEnter:g,onMouseLeave:_},[(0,e.createElement)(`div`,{className:`dsh-reqboard-drop-head`,key:`h`},[(0,e.createElement)(`span`,{key:`a`},`进行中需求`),(0,e.createElement)(`span`,{className:`n`,key:`b`},o===null?``:String(o.length))]),b,(0,e.createElement)(`div`,{className:`dsh-reqboard-drop-foot`,key:`f`},[(0,e.createElement)(`span`,{key:`l`},`点击条目跳转会话`),(0,e.createElement)(`button`,{key:`r`,type:`button`,onClick:()=>{h(!0)}},`刷新`)])]);return(0,e.createElement)(`div`,{className:`dsh-reqboard-foot-wrap${n?``:` rail`}`,onMouseEnter:g,onMouseLeave:_},[y,x])}const Z=[{key:`draft`,label:`立项`},{key:`brainstorming`,label:`需求分析`},{key:`planning`,label:`技术设计`},{key:`decomposing`,label:`拆分`},{key:`implementing`,label:`实施`},{key:`accepting`,label:`验收`},{key:`archived`,label:`归档`}],Q={draft:`立项`,brainstorming:`需求分析`,planning:`技术设计`,decomposing:`拆分`,implementing:`实施中`,accepting:`待验收`,done:`完成`,archived:`归档`,canceled:`已取消`};function Tn(e){if(typeof e==`string`&&e.length>0)return e;try{let e=window,t=(e.__dshPmSessions??e.__dshPmCtx?.sessions)?.list?.getSnapshot?.(),n=t?.current??t?.currentSessionId;if(typeof n==`string`&&n.length>0)return n}catch{}}function En(e,t){return t<0?`pending`:e<t?`done`:e===t?`current`:`pending`}function Dn(t){let n=t?.sessionId,[r,i]=(0,e.useState)(null),[a,o]=(0,e.useState)(!1),[s,c]=(0,e.useState)(null),[l,u]=(0,e.useState)(null),[d,f]=(0,e.useState)(!1),[p,m]=(0,e.useState)(``),h=(0,e.useRef)(null),g=(0,e.useRef)(void 0);(0,e.useEffect)(()=>{let e=!0,t=async()=>{let t=Tn(n);if(t===void 0){e&&(g.current=void 0,i(null));return}t!==g.current&&(g.current=t,e&&i(null));try{let n=await fetch(`/dashboard/api/reqboard/session/${encodeURIComponent(t)}/progress`,{signal:AbortSignal.timeout(8e3)});if(!n.ok)return;let r=await n.json();if(!e)return;i(r.success===!0?r.data??null:null)}catch{}};t();let r=window.setInterval(()=>{t()},15e3);return()=>{e=!1,window.clearInterval(r)}},[n]),(0,e.useEffect)(()=>{if(!a)return;let e=e=>{let t=h.current;t!==null&&!t.contains(e.target)&&o(!1)};return document.addEventListener(`mousedown`,e),()=>document.removeEventListener(`mousedown`,e)},[a]);let _=r?.requirement?.id,v=r?.requirement?.updatedAt;(0,e.useEffect)(()=>{if(!a||_===void 0){u(null);return}let e=!0;return f(!0),m(``),Ot(_).then(t=>{e&&u(t)}).catch(t=>{e&&m(t.message)}).finally(()=>{e&&f(!1)}),()=>{e=!1}},[a,_,v]),(0,e.useEffect)(()=>{let e=e=>{let t=e.target.closest(`[data-action="open-doc"]`);if(t===null)return;e.preventDefault(),e.stopPropagation();let r=t.getAttribute(`data-path`);r!==null&&r.length!==0&&Vt(window.__dshPmCtx,r,Tn(n))};return document.addEventListener(`click`,e),()=>document.removeEventListener(`click`,e)},[n]);let y=r?.requirement;if(r===null||r.hasRequirement!==!0||y==null)return null;let b=r.progress?.done??0,x=r.progress?.total??0,S=y.status??`draft`,C=Z.findIndex(e=>e.key===S),w=y.title??`（未命名需求）`,T=r.closed===!0,E=y.category??`feature`,D=F[E]??F.feature,O=new Set(Z.filter(e=>!D.stages.includes(e.key)).map(e=>e.key)),k=[];Z.forEach((t,n)=>{let r=En(n,C),i=s===t.key,a=O.has(t.key);k.push((0,e.createElement)(`div`,{key:`n-${t.key}`,className:`dsh-pm-flow-node`,"data-state":a?`skipped`:r,"data-selected":i?`true`:void 0,title:a?`本分类（${E}）跳过「${t.label}」`:void 0,onClick:e=>{e.stopPropagation(),c(t.key),o(!0)}},[(0,e.createElement)(`span`,{key:`d`,className:`dsh-pm-flow-dot`},a?`—`:r===`done`?`✓`:r===`current`?`●`:n+1),(0,e.createElement)(`span`,{key:`l`,className:`dsh-pm-flow-label`},t.label)])),n<Z.length-1&&k.push((0,e.createElement)(`div`,{key:`l-${t.key}`,className:`dsh-pm-flow-link`,"data-state":n<C?`done`:`pending`}))});let A=(0,e.createElement)(`div`,{key:`flow`,className:`dsh-pm-cprog-inline${T?` is-closed`:``}`,title:`${y.id??``}《${w}》${Q[S]??S}${T?`（本会话最近完成）`:``} · 点击节点查看详情`,"aria-expanded":a},[(0,e.createElement)(`div`,{key:`f`,className:`dsh-pm-flow`},k),(0,e.createElement)(`span`,{key:`c`,className:`dsh-pm-cprog-inline-count`},x>0?`${b}/${x}`:Q[S]??S)]);if(!a)return(0,e.createElement)(`div`,{className:`dsh-pm-cprog`,ref:h},A);let j=(0,e.createElement)(`div`,{key:`panel`,className:`dsh-pm-cprog-detail-panel`},[(0,e.createElement)(`div`,{key:`h`,className:`dsh-pm-cprog-panel-head`},[(0,e.createElement)(`span`,{key:`t`,className:`dsh-pm-cprog-panel-title`},`${y.id??``} · ${w}`),(0,e.createElement)(`span`,{key:`s`,className:`dsh-pm-status-badge`,"data-status":S},Q[S]??S)]),T?(0,e.createElement)(`div`,{key:`closed`,className:`dsh-pm-cprog-panel-note`},`本会话已无进行中需求 —— 以上是最近关联的需求（已完成/已归档），可作为「这个会话做了什么」的回顾。`):null,(0,e.createElement)(`div`,{key:`ov`,className:`dsh-pm-cprog-sec`},[d&&l===null?(0,e.createElement)(`div`,{key:`ld`,className:`dsh-pm-cprog-empty`},`详情加载中…`):p.length>0&&l===null?(0,e.createElement)(`div`,{key:`er`,className:`dsh-pm-cprog-empty`},`详情暂不可用：`+p):l===null?(0,e.createElement)(`div`,{key:`ne`,className:`dsh-pm-cprog-empty`},`暂无详情`):(0,e.createElement)(`div`,{key:`ovr`,className:`dsh-pm-cprog-stage-detail`,dangerouslySetInnerHTML:{__html:dn(l,s??l.currentStage)}})]),(0,e.createElement)(`div`,{key:`ft`,className:`dsh-pm-cprog-foot`},[(0,e.createElement)(`button`,{key:`open`,type:`button`,className:`dsh-pm-btn sm`,onClick:()=>{window.dispatchEvent(new CustomEvent(X,{detail:{open:!0}}))}},`打开项目看板`),(0,e.createElement)(`button`,{key:`rf`,type:`button`,className:`dsh-pm-btn sm`,onClick:()=>{o(!1),c(null)}},`收起`)])]);return(0,e.createElement)(`div`,{className:`dsh-pm-cprog`,ref:h},[A,j])}const $=`dsh-pmboard/styles.css`;function On(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${$}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=$,e.textContent=`
/* ================================================================== */
/* pmboard 设计 token（REQ-31e11f Step2/3）—— 后续全部 pmboard 样式引用此处 */
/* ================================================================== */
:root {
  /* 尺寸 */
  --pm-btn-h: 28px;         /* 按钮/分段控件统一高度（对齐 .dsh-pm-btn） */
  --pm-btn-h-sm: 24px;      /* 卡面紧凑按钮 */
  --pm-radius: 10px;
  --pm-radius-sm: 7px;
  --pm-radius-pill: 999px;
  --pm-gap: 8px;
  --pm-gap-sm: 4px;
  --pm-gap-lg: 12px;
  /* 阴影 / 线条 / 底色 */
  --pm-shadow-card: 0 1px 2px rgba(0,0,0,.06);
  --pm-shadow-hover: 0 4px 14px rgba(0,0,0,.10);
  --pm-line: var(--dsw-border, rgba(128,128,128,.18));
  --pm-line-strong: rgba(128,128,128,.28);
  --pm-bg-soft: var(--dsw-bg-secondary, rgba(128,128,128,.06));
  /* 8 类节点状态色（与泳道点/甘特条/阶段面板同源，勿各自另立色值） */
  --pm-c-draft: #9aa4b2;
  --pm-c-brainstorming: #f0a020;
  --pm-c-planning: #c2255c;
  --pm-c-decomposing: #8e44ad;
  --pm-c-implementing: #4a7dff;
  --pm-c-accepting: #17a2b8;
  --pm-c-done: #28a745;
  --pm-c-archived: #6c757d;
  --pm-c-danger: #dc3545;
  --pm-c-warn: #b07800;
}

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
.dsh-pm-empty { padding: 8px 0; color: var(--dsw-text-secondary, #999); font-size: 12px; }
.dsh-pm-error { padding: 32px; text-align: center; color: #d33; font-size: 13px; }

/* ---- 泳道 ---- */
.dsh-pm-lanes {
  display: flex; gap: var(--pm-gap-lg); padding: 16px 20px 20px;
  flex: 1; overflow-x: auto; align-items: flex-start;
}
/* REQ-6f39b5：泳道容器对齐 lanes-prototype —— 白底卡片式、定宽、无顶部色条 */
.dsh-pm-lane {
  flex: none; min-width: 320px; max-width: 340px;
  background: var(--dsw-bg-primary, #fff);
  border: 1px solid var(--pm-line);
  border-radius: 12px; padding: 0;
  display: flex; flex-direction: column;
  box-shadow: 0 2px 8px rgba(0,0,0,.08);
  max-height: calc(100vh - 200px);
}
.dsh-pm-lane[data-lane="draft"] { --pm-stage: var(--pm-c-draft); }
.dsh-pm-lane[data-lane="brainstorming"] { --pm-stage: var(--pm-c-brainstorming); }
.dsh-pm-lane[data-lane="planning"] { --pm-stage: var(--pm-c-planning); }
.dsh-pm-lane[data-lane="decomposing"] { --pm-stage: var(--pm-c-decomposing); }
.dsh-pm-lane[data-lane="implementing"] { --pm-stage: var(--pm-c-implementing); }
.dsh-pm-lane[data-lane="accepting"] { --pm-stage: var(--pm-c-accepting); }
.dsh-pm-lane[data-lane="done"] { --pm-stage: var(--pm-c-done); }
.dsh-pm-lane[data-lane="archived"] { --pm-stage: var(--pm-c-archived); }
.dsh-pm-lane-head {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 20px; border-bottom: 2px solid var(--pm-line);
  flex-shrink: 0;
}
.dsh-pm-lane-dot {
  width: 10px; height: 10px; border-radius: 50%; flex: none;
  box-shadow: 0 0 0 3px rgba(128,128,128,.14);
}
.dsh-pm-lane-cards:empty::after {
  content: '暂无需求'; display: block; text-align: center;
  padding: 18px 0; font-size: 11px; color: var(--dsw-text-secondary, #999);
  border: 1px dashed var(--pm-line); border-radius: var(--pm-radius-sm);
}
.dsh-pm-lane-dot[data-status="draft"] { background: #9aa4b2; }
.dsh-pm-lane-dot[data-status="brainstorming"] { background: #f0a020; }
.dsh-pm-lane-dot[data-status="planning"] { background: #c2255c; }
.dsh-pm-lane-dot[data-status="decomposing"] { background: #8e44ad; }
.dsh-pm-lane-dot[data-status="implementing"] { background: #4a7dff; }
.dsh-pm-lane-dot[data-status="accepting"] { background: #17a2b8; }
.dsh-pm-lane-dot[data-status="done"] { background: #28a745; }
.dsh-pm-lane-title { font-size: 13px; font-weight: 600; color: var(--dsw-text-primary, #333); letter-spacing: .2px; }
.dsh-pm-lane-count {
  font-size: 11px; color: var(--dsw-text-secondary, #888); margin-left: auto;
  min-width: 20px; text-align: center; padding: 1px 7px;
  background: rgba(128,128,128,.12); border-radius: var(--pm-radius-pill);
  font-variant-numeric: tabular-nums;
}
.dsh-pm-lane-cards { display: flex; flex-direction: column; gap: 10px; min-height: 24px; padding: 12px; flex: 1; overflow-y: auto; }

/* ---- 需求卡片 ---- */
/* REQ-6f39b5：卡片对齐 lanes-prototype —— 简洁白卡、无左色条、蓝框 hover */
.dsh-pm-card {
  background: var(--dsw-bg-primary, #fff);
  border: 1px solid var(--pm-line);
  border-radius: 8px; padding: 12px;
  cursor: pointer; display: flex; flex-direction: column; gap: 8px;
  transition: box-shadow .2s ease, transform .2s ease, border-color .2s ease;
}
.dsh-pm-card:hover {
  border-color: var(--dsw-accent, #4a7dff);
  box-shadow: 0 4px 12px rgba(74,125,255,.12); transform: translateY(-2px);
}
.dsh-pm-card.is-blocked {
  border-color: var(--pm-c-danger);
}
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
.dsh-pm-card-title { font-size: 13px; font-weight: 600; color: var(--dsw-text-primary, #111827); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.dsh-pm-card-progress { display: flex; align-items: center; gap: 8px; }
.dsh-pm-card-bar { flex: 1; height: 4px; border-radius: 2px; background: rgba(128,128,128,.15); overflow: hidden; }
.dsh-pm-card-bar-fill { height: 100%; background: linear-gradient(90deg, #4a7dff, #28a745); border-radius: 2px; transition: width .3s; }
.dsh-pm-card-pct { font-size: 11px; color: var(--dsw-text-secondary, #999); flex: none; }
/* 卡面操作行：按钮复用全站 .dsh-pm-btn 体系（与页头「刷新/+需求」、详情页闸门同款），
   只加紧凑尺寸变体，避免看板内出现第二套按钮视觉。 */
.dsh-pm-card-actions { display: flex; gap: 6px; margin-top: 4px; padding-top: 8px; border-top: 1px solid var(--pm-line); }
.dsh-pm-card-actions .dsh-pm-btn { flex: 1; text-align: center; }

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
/* REQ-6f39b5：详情头垂直分行（对齐 prototype.html）——
   第一行 meta（返回/ID/状态/窗口/时间），第二行大标题，第三行 8 态进度点 */
.dsh-pm-detail-head { display: flex; align-items: center; gap: 10px; flex: none; flex-wrap: wrap; }
.dsh-pm-detail-head .dsh-pm-detail-title { flex-basis: 100%; margin-top: 2px; }
.dsh-pm-detail-head .dsh-pm-progress-dots { flex-basis: 100%; margin: 8px 0 0; padding: 4px 0 0; }
.dsh-pm-status {
  font-size: 11px; padding: 2px 10px; border-radius: 10px;
  background: rgba(128,128,128,.12); color: var(--dsw-text-primary, #444);
}
.dsh-pm-status[data-status="implementing"] { background: rgba(74,125,255,.15); color: #4a7dff; }
.dsh-pm-status[data-status="done"] { background: rgba(40,167,69,.15); color: #28a745; }
.dsh-pm-status[data-status="accepting"] { background: rgba(23,162,184,.15); color: #17a2b8; }
.dsh-pm-detail-updated { font-size: 12px; color: var(--dsw-text-secondary, #999); margin-left: auto; }
.dsh-pm-detail-title { margin: 0; font-size: 24px; font-weight: 700; color: var(--dsw-text-primary, #111827); }
.dsh-pm-detail-desc { font-size: 14px; color: var(--dsw-text-secondary, #555); white-space: pre-wrap; }
.dsh-pm-detail-section { display: flex; flex-direction: column; gap: 8px; }
.dsh-pm-detail-section h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--dsw-text-primary, #333); }
.dsh-pm-gate {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; border-radius: 8px;
  background: rgba(240,160,32,.1); border: 1px solid rgba(240,160,32,.3);
  font-size: 13px; color: #8a5a00;
}

/* ---- DAG（REQ-6f39b5 对齐 prototype：白底卡片容器 + 标题）---- */
.dsh-pm-dag {
  background: var(--dsw-bg-primary, #fff); border: 1px solid var(--pm-line);
  border-radius: 8px; padding: 20px; margin-bottom: 8px;
}
.dsh-pm-dag-title { font-size: 14px; font-weight: 600; color: var(--dsw-text-primary, #111827); margin-bottom: 16px; }
.dsh-pm-dag-layers { display: flex; flex-direction: column; gap: 12px; }
.dsh-pm-dag-layer { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dsh-pm-dag-layer-label { font-size: 11px; color: var(--dsw-text-secondary, #999); width: 24px; flex: none; font-weight: 600; font-family: ui-monospace, monospace; }
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
/* ---- 任务表格（REQ-6f39b5 对齐 prototype dsh-pm-task-table）---- */
.dsh-pm-task-table { width: 100%; border-collapse: collapse; background: var(--dsw-bg-primary, #fff); border-radius: 8px; overflow: hidden; }
.dsh-pm-task-table th {
  background: var(--dsw-bg-secondary, #f9fafb); padding: 12px; text-align: left;
  font-size: 12px; font-weight: 600; color: var(--dsw-text-secondary, #6b7280);
  text-transform: uppercase; border-bottom: 1px solid var(--pm-line);
}
.dsh-pm-task-table td { padding: 14px 12px; border-bottom: 1px solid var(--pm-line); font-size: 14px; }
.dsh-pm-task-table tbody tr { cursor: pointer; transition: background .2s; }
.dsh-pm-task-table tbody tr:hover { background: var(--dsw-bg-secondary, #f9fafb); }
.dsh-pm-task-status { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; white-space: nowrap; }
.dsh-pm-task-status.todo { background: rgba(156,163,175,.12); color: #6b7280; }
.dsh-pm-task-status.in_progress, .dsh-pm-task-status.integrating, .dsh-pm-task-status.testing, .dsh-pm-task-status.in_review { background: rgba(74,125,255,.12); color: #4a7dff; }
.dsh-pm-task-status.done { background: rgba(40,167,69,.12); color: #28a745; }
.dsh-pm-task-status.canceled { background: rgba(156,163,175,.12); color: #9ca3af; text-decoration: line-through; }
.dsh-pm-link { color: var(--dsw-accent, #4a7dff); font-size: 13px; cursor: pointer; }

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


/* ========================================================================
   REQ-6f39b5：8 态进度点 + 4 Tab 分组
   ======================================================================== */

/* 8 态进度点 */
.dsh-pm-progress-dots {
  display: flex; gap: 16px; align-items: flex-start;
  margin: 20px 0; padding: 12px 0;
}
.dsh-pm-dot-wrapper {
  display: flex; flex-direction: column; align-items: center; gap: 8px; flex: 1;
}
.dsh-pm-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--dsw-border, #ddd); opacity: 0.4; transition: all 0.3s;
}
.dsh-pm-dot-wrapper.completed .dsh-pm-dot {
  opacity: 1; background: #28a745;
}
.dsh-pm-dot-wrapper.current .dsh-pm-dot {
  width: 14px; height: 14px; opacity: 1; background: #4a7dff;
  box-shadow: 0 0 0 4px rgba(74,125,255,0.15);
}
.dsh-pm-dot-label {
  font-size: 11px; color: var(--dsw-text-secondary, #999);
  white-space: nowrap; text-align: center;
}
.dsh-pm-dot-wrapper.current .dsh-pm-dot-label {
  color: #4a7dff; font-weight: 600;
}
.dsh-pm-dot-wrapper.completed .dsh-pm-dot-label {
  color: #28a745; font-weight: 500;
}

/* Tab 导航 */
.dsh-pm-tabs {
  display: flex; gap: 4px;
  border-bottom: 2px solid var(--dsw-border, #eee);
  padding: 0 20px;
}
.dsh-pm-tab {
  padding: 12px 24px; border: none; background: none;
  color: var(--dsw-text-secondary, #666); font-size: 14px; font-weight: 500;
  cursor: pointer; border-bottom: 2px solid transparent;
  margin-bottom: -2px; transition: all 0.2s;
}
.dsh-pm-tab:hover {
  background: rgba(74,125,255,0.05);
  color: var(--dsw-text-primary, #333);
}
.dsh-pm-tab.active {
  color: #4a7dff; border-bottom-color: #4a7dff; font-weight: 600;
}

/* Tab 内容区 */
.dsh-pm-tab-content {
  padding: 24px; display: none;
}
.dsh-pm-tab-content.active {
  display: block;
}
/* REQ-6f39b5：当前阶段高亮卡（对齐 prototype .dsh-pm-stage-current）*/
.dsh-pm-stage-current {
  background: linear-gradient(135deg, rgba(74,125,255,.08) 0%, rgba(74,125,255,.02) 100%);
  border: 1px solid rgba(74,125,255,.2); border-radius: 10px; padding: 20px;
}
.dsh-pm-stage-current-title { font-size: 14px; color: var(--dsw-accent, #4a7dff); font-weight: 600; margin-bottom: 12px; }

/* REQ-6f39b5：任务统计卡片（对齐 prototype .dsh-pm-stats）*/
.dsh-pm-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 8px; }
.dsh-pm-stat {
  background: var(--dsw-bg-primary, #fff); border: 1px solid var(--pm-line);
  border-radius: 8px; padding: 16px;
}
.dsh-pm-stat-label { font-size: 12px; color: var(--dsw-text-secondary, #6b7280); margin-bottom: 8px; text-transform: uppercase; font-weight: 500; }
.dsh-pm-stat-value { font-size: 28px; font-weight: 700; color: var(--dsw-text-primary, #111827); }
.dsh-pm-stat-success .dsh-pm-stat-value { color: #28a745; }



/* REQ-6f39b5：验收泳道中的 done（历史完成）需求置灰显示 */
.dsh-pm-card.is-archived { opacity: 0.5; }
.dsh-pm-card.is-archived:hover { opacity: 0.75; }
/* ========================================================================
   REQ-6f39b5：列表视图表格化（对齐 list-prototype.html）
   ======================================================================== */
.dsh-pm-table { width: 100%; border-collapse: collapse; background: var(--dsw-bg-primary, #fff); border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.dsh-pm-table thead { background: var(--dsw-bg-secondary, #f9fafb); }
.dsh-pm-table th {
  padding: 12px 16px; text-align: left; font-size: 12px; font-weight: 600;
  color: var(--dsw-text-secondary, #6b7280); text-transform: uppercase;
  border-bottom: 2px solid var(--pm-line); white-space: nowrap;
}
.dsh-pm-table td {
  padding: 12px 16px; font-size: 13px; color: var(--dsw-text-primary, #374151);
  border-bottom: 1px solid var(--pm-line); vertical-align: middle;
}
.dsh-pm-table tbody tr.dsh-pm-list-row { cursor: pointer; transition: background .2s; }
.dsh-pm-table tbody tr.dsh-pm-list-row:hover { background: var(--dsw-bg-secondary, #f9fafb); }
.dsh-pm-table tbody tr.dsh-pm-list-row.is-archived { opacity: 0.5; }
.dsh-pm-table tbody tr.dsh-pm-list-row.is-archived:hover { opacity: 0.7; }
.dsh-pm-td-title { max-width: 380px; }
.dsh-pm-td-title .dsh-pm-list-title { font-weight: 600; color: var(--dsw-text-primary, #111827); cursor: pointer; }
.dsh-pm-td-title .dsh-pm-list-title:hover { color: var(--dsw-accent, #4a7dff); }
.dsh-pm-td-progress { min-width: 140px; }
.dsh-pm-td-progress .dsh-pm-list-progress { display: flex; align-items: center; gap: 8px; }
tr.dsh-pm-list-grouphead td {
  padding: 10px 16px; font-size: 12px; font-weight: 600;
  color: var(--dsw-text-secondary, #6b7280);
  background: var(--dsw-bg-secondary, #f9fafb);
  border-bottom: 1px solid var(--pm-line);
}
.dsh-pm-table .dsh-pm-list-actions { display: flex; gap: 6px; flex-wrap: nowrap; }
.dsh-pm-table .dsh-pm-list-actions .dsh-pm-card-actions { margin-top: 0; padding-top: 0; border-top: none; }
.dsh-pm-table .dsh-pm-list-actions .dsh-pm-btn { flex: none; }


.dsh-pm-section {
  margin-bottom: 24px;
}
.dsh-pm-section-title {
  font-size: 14px; font-weight: 600;
  color: var(--dsw-text-primary, #333);
  margin-bottom: 12px;
}
.dsh-pm-section-content {
  background: var(--dsw-bg-secondary, #f9fafb);
  border: 1px solid var(--dsw-border, #e5e7eb);
  border-radius: 8px; padding: 16px;
}

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

/* 流程图（横向时间线）：未到 / 当前 / 完成 / 跳过 四态配色统一，尺寸一致 */
.dsh-pm-flow { display: flex; align-items: stretch; gap: 0; overflow-x: auto; padding: 2px 0; }
.dsh-pm-flow-node {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  min-width: 58px; cursor: pointer; transition: transform .2s ease;
}
.dsh-pm-flow-node:hover { transform: translateY(-2px); }
.dsh-pm-flow-node[data-selected="true"] .dsh-pm-flow-dot {
  box-shadow: 0 0 0 3px rgba(74,125,255,.3);
  transform: scale(1.08);
}
.dsh-pm-flow-node[data-selected="true"] .dsh-pm-flow-label {
  font-weight: 700;
  color: #2f5fd0;
}
.dsh-pm-flow-dot {
  width: 22px; height: 22px; border-radius: 50%; flex: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; box-sizing: border-box;
  background: var(--pm-bg-soft); color: var(--dsw-text-secondary, #888);
  border: 1px solid var(--pm-line);
  transition: background .2s ease, box-shadow .2s ease, transform .2s ease;
}
/* 未到：空心灰 */
.dsh-pm-flow-node[data-state="pending"] .dsh-pm-flow-dot {
  background: transparent; border: 1px solid var(--pm-line-strong); color: var(--dsw-text-secondary, #999);
}
/* 完成：实心绿 + 对勾 */
.dsh-pm-flow-node[data-state="done"] .dsh-pm-flow-dot {
  background: var(--pm-c-done); border-color: var(--pm-c-done); color: #fff;
}
/* 当前：实心蓝 + 光环 */
.dsh-pm-flow-node[data-state="current"] .dsh-pm-flow-dot {
  background: var(--pm-c-implementing); border-color: var(--pm-c-implementing); color: #fff;
  box-shadow: 0 0 0 3px rgba(74,125,255,.25);
}
/* 跳过（本分类不适用）：虚线灰 + 降透明，与"未到"再区分一层 */
.dsh-pm-flow-node[data-state="skipped"] .dsh-pm-flow-dot {
  background: transparent; border: 1px dashed var(--pm-c-archived); color: var(--pm-c-archived); opacity: .7;
}
.dsh-pm-flow-label {
  font-size: 10px; color: var(--dsw-text-secondary, #999); white-space: nowrap;
  transition: color .2s ease, opacity .2s ease;
}
.dsh-pm-flow-node[data-state="pending"] .dsh-pm-flow-label { opacity: .75; }
.dsh-pm-flow-node[data-state="done"] .dsh-pm-flow-label { color: #1e7e34; }
.dsh-pm-flow-node[data-state="current"] .dsh-pm-flow-label { color: #2f5fd0; font-weight: 600; }
.dsh-pm-flow-node[data-state="skipped"] .dsh-pm-flow-label {
  color: var(--pm-c-archived); opacity: .55; text-decoration: line-through;
}
.dsh-pm-flow-link {
  width: 16px; height: 2px; border-radius: 1px; margin-top: 10px; flex: none;
  background: rgba(128,128,128,.22);
}
.dsh-pm-flow-link[data-state="done"] { background: rgba(40,167,69,.6); }

.dsh-pm-cprog-task { display: flex; align-items: flex-start; gap: 7px; font-size: 12px; line-height: 1.45; }
.dsh-pm-cprog-task-ico { flex: none; }
.dsh-pm-cprog-task-body { min-width: 0; }
.dsh-pm-cprog-task-title { color: var(--dsw-text-primary, #333); }
.dsh-pm-cprog-task[data-status="done"] .dsh-pm-cprog-task-title { color: var(--dsw-text-secondary, #999); text-decoration: line-through; }
.dsh-pm-cprog-task-meta { font-size: 10px; color: var(--dsw-text-secondary, #aaa); }
.dsh-pm-cprog-tl { display: flex; flex-direction: column; gap: 5px; font-size: 11px; }
.dsh-pm-cprog-tl-row { display: flex; gap: 8px; align-items: baseline; }
.dsh-pm-cprog-tl-time { color: var(--dsw-text-secondary, #aaa); font-variant-numeric: tabular-nums; flex: none; }

/* ------------------------------------------------------------------ 产物 chips + 确认按钮（REQ-31e11f t7） */

.dsh-pm-artifact-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.dsh-pm-artifact-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  border: none;
  cursor: default;
  line-height: 1.4;
}

.dsh-pm-artifact-chip.confirmed {
  background: rgba(40, 167, 69, .12);
  color: #28a745;
}

.dsh-pm-artifact-chip.pending {
  background: rgba(240, 160, 32, .15);
  color: #b07800;
  cursor: pointer;
}

.dsh-pm-artifact-chip.pending:hover {
  background: rgba(240, 160, 32, .25);
}

.dsh-pm-artifact-chip.missing {
  background: rgba(220, 53, 69, .12);
  color: #dc3545;
}

.dsh-pm-artifact-derived {
  font-size: 10px;
  color: var(--dsw-text-secondary, #999);
  margin-top: 4px;
}

.dsh-pm-confirm-artifact {
  margin-top: 6px;
  font-weight: 600;
}
.dsh-pm-cprog-tl-text { color: var(--dsw-text-primary, #444); }
.dsh-pm-cprog-empty { font-size: 12px; color: var(--dsw-text-secondary, #999); }
.dsh-pm-cprog-foot { display: flex; gap: 8px; }

/* ==================================================================== */
/* 阶段详情面板（stage-panel.ts，REQ-31e11f t6）                          */
/* 8 类节点视觉差异化：每类节点一个 --pm-stage 状态色 + 专属图标 + 专属底色  */
/* ==================================================================== */

/* v4: no box */
.dsh-pm-stage-panel { display: flex; flex-direction: column; gap: 4px; }
.dsh-pm-stage-panel[data-stage="draft"] { --pm-stage: var(--pm-c-draft); }
.dsh-pm-stage-panel[data-stage="brainstorming"] { --pm-stage: var(--pm-c-brainstorming); }
.dsh-pm-stage-panel[data-stage="planning"] { --pm-stage: var(--pm-c-planning); }
.dsh-pm-stage-panel[data-stage="decomposing"] { --pm-stage: var(--pm-c-decomposing); }
.dsh-pm-stage-panel[data-stage="implementing"] { --pm-stage: var(--pm-c-implementing); }
.dsh-pm-stage-panel[data-stage="accepting"] { --pm-stage: var(--pm-c-accepting); }
.dsh-pm-stage-panel[data-stage="done"] { --pm-stage: var(--pm-c-done); }
.dsh-pm-stage-panel[data-stage="archived"] { --pm-stage: var(--pm-c-archived); }
.dsh-pm-stage-panel.is-skipped {
  --pm-stage: var(--pm-c-archived);
  border-style: dashed; background: var(--pm-bg-soft); box-shadow: none;
}
.dsh-pm-stage-panel-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dsh-pm-stage-label {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 14px; font-weight: 600;
  padding: 3px 11px; border-radius: var(--pm-radius-pill);
  color: var(--pm-stage);
  background: rgba(128,128,128,.10);
  background: color-mix(in srgb, var(--pm-stage) 15%, transparent);
}
/* 8 类节点专属图标（不依赖文字也能分辨节点类型） */
.dsh-pm-stage-panel[data-stage="draft"] .dsh-pm-stage-label::before { content: '📌'; }
.dsh-pm-stage-panel[data-stage="brainstorming"] .dsh-pm-stage-label::before { content: '💡'; }
.dsh-pm-stage-panel[data-stage="planning"] .dsh-pm-stage-label::before { content: '📐'; }
.dsh-pm-stage-panel[data-stage="decomposing"] .dsh-pm-stage-label::before { content: '🧩'; }
.dsh-pm-stage-panel[data-stage="implementing"] .dsh-pm-stage-label::before { content: '⚙️'; }
.dsh-pm-stage-panel[data-stage="accepting"] .dsh-pm-stage-label::before { content: '🧪'; }
.dsh-pm-stage-panel[data-stage="done"] .dsh-pm-stage-label::before { content: '🎉'; }
.dsh-pm-stage-panel[data-stage="archived"] .dsh-pm-stage-label::before { content: '📦'; }
.dsh-pm-stage-skipped-badge {
  font-size: 11px; padding: 1px 9px; border-radius: var(--pm-radius-pill);
  color: var(--pm-c-archived); background: rgba(108,117,125,.14);
  border: 1px dashed rgba(108,117,125,.45);
}
/* v4: plain text flow, no box */
.dsh-pm-sn-body { display: flex; flex-direction: column; gap: 2px; }
.dsh-pm-stage-body-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--dsw-text-primary, #222); }
.dsh-pm-stage-desc { font-size: 13px; line-height: 1.7; color: var(--dsw-text-secondary, #555); white-space: pre-wrap; }
.dsh-pm-stage-meta { font-size: 12px; color: var(--dsw-text-secondary, #888); }
.dsh-pm-stage-category {
  align-self: flex-start;
  font-size: 11px; padding: 1px 8px; border-radius: var(--pm-radius-pill);
  background: rgba(74,125,255,.12); color: #2f5fd0;
}
.dsh-pm-stage-field { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.dsh-pm-stage-tasks { display: flex; flex-direction: column; gap: 6px; }
.dsh-pm-stage-comments { display: flex; flex-direction: column; gap: 6px; }
.dsh-pm-confirm-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-radius: var(--pm-radius-sm);
  background: rgba(240,160,32,.12); border: 1px solid rgba(240,160,32,.4);
  color: var(--pm-c-warn); font-size: 12px; font-weight: 500;
}

/* 产物区（必备产物缺失 = 红；已登记 = 中性卡） */
.dsh-pm-artifacts-section { display: flex; flex-direction: column; gap: 6px; }
.dsh-pm-artifacts-head { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.dsh-pm-artifacts-summary { font-size: 12px; font-weight: 600; color: var(--dsw-text-secondary, #888); }
.dsh-pm-artifacts-summary.is-warning { color: var(--pm-c-danger); }
.dsh-pm-artifacts-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.dsh-pm-artifacts-empty {
  padding: 10px 12px; text-align: center; font-size: 12px;
  color: var(--dsw-text-secondary, #999); background: var(--pm-bg-soft);
  border: 1px dashed var(--pm-line); border-radius: var(--pm-radius-sm);
}
.dsh-pm-artifact-item {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 6px 10px; border-radius: var(--pm-radius-sm);
  background: var(--pm-bg-soft); border: 1px solid transparent;
  font-size: 12px;
}
.dsh-pm-artifact-item.is-missing {
  background: rgba(220,53,69,.07); border-color: rgba(220,53,69,.32);
}
.dsh-pm-artifact-kind { font-size: 11px; color: var(--dsw-text-secondary, #888); min-width: 64px; flex: none; }
.dsh-pm-artifact-path {
  flex: 1; min-width: 0; text-align: left;
  font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px;
  color: var(--dsw-accent, #4a7dff); background: rgba(128,128,128,.10);
  border: none; border-radius: 4px; padding: 2px 6px; cursor: pointer;
  word-break: break-all;
}
.dsh-pm-artifact-path:hover { background: rgba(74,125,255,.14); text-decoration: underline; }
.dsh-pm-artifact-badge { font-size: 10px; padding: 1px 7px; border-radius: var(--pm-radius-pill); flex: none; }
.dsh-pm-artifact-badge.confirmed { background: rgba(40,167,69,.14); color: #1e7e34; }
.dsh-pm-artifact-badge.pending { background: rgba(240,160,32,.18); color: var(--pm-c-warn); }
.dsh-pm-artifact-meta {
  font-size: 11px; color: var(--dsw-text-secondary, #999);
  margin-left: auto; font-variant-numeric: tabular-nums;
}
.dsh-pm-artifact-missing {
  font-size: 11px; font-weight: 600; padding: 1px 7px;
  border-radius: var(--pm-radius-pill);
  background: rgba(220,53,69,.14); color: var(--pm-c-danger);
}
.dsh-pm-doc-link {
  display: inline-flex; align-items: center; gap: 4px; align-self: flex-start;
  height: var(--pm-btn-h-sm); padding: 0 10px;
  border: 1px solid rgba(74,125,255,.35); border-radius: var(--pm-radius-sm);
  background: rgba(74,125,255,.08); color: var(--dsw-accent, #4a7dff);
  font: inherit; font-size: 12px; line-height: 1; cursor: pointer;
}
.dsh-pm-doc-link:hover { background: rgba(74,125,255,.16); }
/* 文件不存在的文档按钮（board-mount 运行时加 .dsh-pm-doc-missing） */
.dsh-pm-artifact-path.dsh-pm-doc-missing,
.dsh-pm-trace-path.dsh-pm-doc-missing,
.dsh-pm-doc-path.dsh-pm-doc-missing {
  color: var(--dsw-text-secondary, #999);
  text-decoration: line-through; cursor: not-allowed;
  background: rgba(128,128,128,.06); border-color: var(--pm-line);
}

/* 产物追溯链：链式胶囊，箭头串联 */
.dsh-pm-trace-chain {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 8px 10px; border-radius: var(--pm-radius-sm);
  background: var(--pm-bg-soft); border: 1px dashed var(--pm-line);
  font-size: 12px;
}
.dsh-pm-trace-title { font-size: 11px; font-weight: 600; color: var(--dsw-text-secondary, #888); }
.dsh-pm-trace-node {
  display: inline-flex; align-items: center; gap: 5px; max-width: 100%;
  padding: 3px 9px; border-radius: var(--pm-radius-pill);
  background: var(--dsw-bg-primary, #fff); border: 1px solid var(--pm-line);
}
.dsh-pm-trace-label { font-size: 11px; color: var(--dsw-text-secondary, #888); flex: none; }
.dsh-pm-trace-arrow { color: var(--dsw-text-secondary, #bbb); font-weight: 600; }
.dsh-pm-trace-path {
  border: none; background: transparent; padding: 0; cursor: pointer;
  font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px;
  color: var(--dsw-accent, #4a7dff); max-width: 220px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  text-align: left;
}
.dsh-pm-trace-path:hover { text-decoration: underline; }

/* 任务 / 执行（拆分节点 vs 实施节点，共用行式卡片） */
.dsh-pm-task-ref-list, .dsh-pm-task-exec-list {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: 5px;
}
.dsh-pm-task-ref, .dsh-pm-task-exec {
  display: grid; grid-template-columns: 76px 1fr auto; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: var(--pm-radius-sm);
  background: var(--dsw-bg-primary, #fff); border: 1px solid var(--pm-line);
  border-left: 3px solid var(--pm-c-draft);
  font-size: 12px;
}
.dsh-pm-task-ref[data-status="in_progress"], .dsh-pm-task-exec[data-status="in_progress"] { border-left-color: var(--pm-c-implementing); }
.dsh-pm-task-ref[data-status="integrating"], .dsh-pm-task-exec[data-status="integrating"] { border-left-color: var(--pm-c-decomposing); }
.dsh-pm-task-ref[data-status="testing"], .dsh-pm-task-exec[data-status="testing"] { border-left-color: var(--pm-c-brainstorming); }
.dsh-pm-task-ref[data-status="in_review"], .dsh-pm-task-exec[data-status="in_review"] { border-left-color: var(--pm-c-accepting); }
.dsh-pm-task-ref[data-status="done"], .dsh-pm-task-exec[data-status="done"] { border-left-color: var(--pm-c-done); }
.dsh-pm-task-ref[data-status="canceled"], .dsh-pm-task-exec[data-status="canceled"] { border-left-color: var(--pm-c-danger); opacity: .6; }
.dsh-pm-task-ref-id { font-family: ui-monospace, monospace; font-size: 11px; color: var(--dsw-text-secondary, #999); }
.dsh-pm-task-ref-title {
  color: var(--dsw-text-primary, #333); min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dsh-pm-task-ref-status {
  justify-self: end; font-size: 11px; padding: 1px 8px;
  border-radius: var(--pm-radius-pill);
  background: rgba(128,128,128,.12); color: var(--dsw-text-secondary, #666);
}
.dsh-pm-task-claimed {
  grid-column: 1 / -1; font-size: 10px; color: var(--dsw-text-secondary, #888);
  font-family: ui-monospace, monospace;
}
.dsh-pm-by-window { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; padding: 2px 0; }
.dsh-pm-window-chip {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; padding: 2px 9px; border-radius: var(--pm-radius-pill);
  background: rgba(74,125,255,.10); color: var(--dsw-accent, #4a7dff);
  border: 1px solid rgba(74,125,255,.28);
  font-family: ui-monospace, monospace;
}

/* 节点时间线（stage-panel 内，与需求级 dsh-pm-tl-row 系列区分） */
.dsh-pm-timeline-list {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: 4px;
}
.dsh-pm-timeline-item {
  display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;
  padding: 5px 10px; border-radius: var(--pm-radius-sm);
  background: var(--pm-bg-soft); border-left: 3px solid var(--pm-line);
  font-size: 12px;
}
.dsh-pm-timeline-item:first-child { border-left-color: var(--pm-c-implementing); }
.dsh-pm-timeline-time {
  font-family: ui-monospace, monospace; font-size: 11px; flex: none;
  color: var(--dsw-text-secondary, #888); font-variant-numeric: tabular-nums;
}
.dsh-pm-timeline-actor {
  flex: none; font-size: 11px; padding: 1px 7px;
  border-radius: var(--pm-radius-pill);
  background: rgba(128,128,128,.12); color: var(--dsw-text-secondary, #666);
}
.dsh-pm-timeline-reason { color: var(--dsw-text-primary, #444); }
.dsh-pm-timeline-inferred { font-size: 10px; color: var(--pm-c-warn); }
.dsh-pm-timeline-empty {
  padding: 10px 12px; text-align: center; font-size: 12px;
  color: var(--dsw-text-secondary, #999); background: var(--pm-bg-soft);
  border: 1px dashed var(--pm-line); border-radius: var(--pm-radius-sm);
}

/* 验收节点 */
.dsh-pm-verify-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dsh-pm-verify-summary { font-size: 13px; line-height: 1.65; color: var(--dsw-text-primary, #333); white-space: pre-wrap; }
.dsh-pm-verify-evidence {
  font-size: 12px; color: var(--dsw-text-secondary, #666);
  background: var(--dsw-bg-primary, #fff); border: 1px dashed var(--pm-line);
  border-radius: var(--pm-radius-sm); padding: 6px 10px;
}
.dsh-pm-verify-badge { font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: var(--pm-radius-pill); }
.dsh-pm-verify-badge.pass { background: rgba(40,167,69,.15); color: #1e7e34; }
.dsh-pm-verify-badge.rework { background: rgba(220,53,69,.14); color: var(--pm-c-danger); }
.dsh-pm-verify-badge.pending { background: rgba(240,160,32,.16); color: var(--pm-c-warn); }

/* 归档节点 */
.dsh-pm-archive-docs {
  font-size: 12px; color: var(--dsw-text-secondary, #666);
  padding: 4px 9px; background: var(--dsw-bg-primary, #fff);
  border: 1px dashed var(--pm-line); border-radius: var(--pm-radius-sm);
}
.dsh-pm-archive-index {
  font-size: 12px; line-height: 1.6; color: var(--dsw-text-primary, #444);
  padding-left: 9px; border-left: 3px solid var(--pm-c-archived);
}
.dsh-pm-archive-merged {
  font-size: 11px; color: var(--dsw-text-secondary, #888);
  font-family: ui-monospace, monospace; word-break: break-all;
}

/* 技术设计节点：计划徽标 + 时间 */
.dsh-pm-plan-badge { font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: var(--pm-radius-pill); }
.dsh-pm-plan-badge.approved { background: rgba(40,167,69,.15); color: #1e7e34; }
.dsh-pm-plan-badge.rejected { background: rgba(220,53,69,.14); color: var(--pm-c-danger); }
.dsh-pm-plan-badge.pending { background: rgba(240,160,32,.16); color: var(--pm-c-warn); }
.dsh-pm-plan-time {
  font-size: 11px; color: var(--dsw-text-secondary, #999);
  font-family: ui-monospace, monospace; font-variant-numeric: tabular-nums;
}

/* 需求分析节点：评论列表 */
.dsh-pm-comment-list {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: 5px;
}
.dsh-pm-comment-list li {
  font-size: 12px; line-height: 1.6; color: var(--dsw-text-primary, #444);
  padding: 6px 10px; border-radius: var(--pm-radius-sm);
  background: var(--dsw-bg-primary, #fff); border: 1px solid var(--pm-line);
}

/* 折叠块：stage-panel / 会话进度面板里没有 .dsh-pm-detail 祖先，需自带一套基础样式
   （.dsh-pm-detail 内仍由上面的高特异性规则接管，看板详情页外观不变） */
details.dsh-pm-fold {
  border: 1px solid var(--pm-line); border-radius: var(--pm-radius);
  background: var(--dsw-bg-primary, #fff); margin-top: 2px;
}
details.dsh-pm-fold > summary {
  list-style: none; cursor: pointer; user-select: none;
  display: flex; align-items: center; gap: 8px;
  padding: 9px 12px; font-size: 13px; font-weight: 600;
  color: var(--dsw-text-primary, #333); background: var(--pm-bg-soft);
  border-radius: var(--pm-radius);
  transition: background .15s ease;
}
details.dsh-pm-fold > summary::-webkit-details-marker { display: none; }
details.dsh-pm-fold > summary::before {
  content: '▸'; font-size: 11px; color: var(--dsw-text-secondary, #999);
  transition: transform .15s ease;
}
details.dsh-pm-fold[open] > summary { border-radius: var(--pm-radius) var(--pm-radius) 0 0; }
details.dsh-pm-fold[open] > summary::before { transform: rotate(90deg); }
details.dsh-pm-fold > summary:hover { background: var(--dsw-hover, rgba(128,128,128,.1)); }
details.dsh-pm-fold > .dsh-pm-fold-body { padding: 10px 12px; border-top: 1px solid var(--pm-line); }

/* ==================================================================== */
/* 看板详情：阶段导航（分段控件）+ 阶段容器 + 任务表标题（view.ts）         */
/* ==================================================================== */

/* 立项/需求分析…导航：与 .dsh-pm-btn 同高/同圆角/同色板；做成分段控件 */
.dsh-pm-stage-nav {
  display: flex; flex-wrap: wrap; gap: 2px;
  padding: 3px; border: 1px solid var(--pm-line);
  border-radius: var(--pm-radius); background: var(--pm-bg-soft);
}
.dsh-pm-stage-nav-btn {
  flex: 1 1 auto; min-width: 64px;
  height: var(--pm-btn-h); padding: 0 12px;
  display: inline-flex; align-items: center; justify-content: center;
  border: none; border-radius: calc(var(--pm-radius) - 3px);
  background: transparent; color: var(--dsw-text-secondary, #777);
  font: inherit; font-size: 12px; line-height: 1; cursor: pointer;
  transition: background .15s ease, color .15s ease;
}
.dsh-pm-stage-nav-btn:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, #333); }
.dsh-pm-stage-nav-btn:active { background: rgba(74,125,255,.14); color: var(--dsw-accent, #4a7dff); }
.dsh-pm-stage-nav-btn.active,
.dsh-pm-stage-nav-btn[data-active="true"] {
  background: var(--dsw-accent, #4a7dff); color: #fff; font-weight: 600;
  box-shadow: var(--pm-shadow-card);
}
.dsh-pm-stage-detail,
.dsh-pm-stage-detail-container { display: block; min-height: 0; }
.dsh-pm-stage-detail:empty { display: none; }
/* 会话进度面板里的节点详情容器（renderStagePanel 复用） */
.dsh-pm-cprog-stage-detail { max-height: 340px; overflow: auto; margin-top: 4px; }
/* 任务总览表标题列 */
.dsh-pm-ttitle { font-size: 12px; color: var(--dsw-text-primary, #333); }

/* 属性锚（非 class，dom.ts：data-dsh-pm-active / data-dsh-pm-entry）——板容器基础约束 */
html[data-dsh-pm-active] .dsh-pm-board,
html[data-dsh-pm-entry] .dsh-pm-board { min-height: 0; }

/* 卡面操作行：同高按钮，间距统一 */
.dsh-pm-card-actions .dsh-pm-btn { margin: 0; }

/* 详情「本阶段操作」固定条（Step6 审批入口外置）：恒正面、粘顶可见 */
.dsh-pm-action-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 12px; border-radius: var(--pm-radius);
  background: var(--dsw-bg-primary, #fff);
  border: 1px solid rgba(74,125,255,.35);
  box-shadow: var(--pm-shadow-card);
  position: sticky; top: 0; z-index: 20;
}
.dsh-pm-action-bar-label { font-size: 11px; font-weight: 600; color: var(--dsw-text-secondary, #888); }
/* 评论作者（人 / 窗口 / 系统）用色区分 —— 人机协同双方可辨 */
.dsh-pm-comment-who { font-weight: 600; }
.dsh-pm-comment-who[data-actor="human"] { color: #2f5fd0; }
.dsh-pm-comment-who[data-actor="agent"] { color: #6f2f8c; }
.dsh-pm-comment-who[data-actor="system"] { color: var(--dsw-text-secondary, #999); font-weight: 500; }
/* 来源会话已归档：灰标不可跳 */
.dsh-pm-list-archived-note { font-style: italic; opacity: .85; }

/* ---- 单节点工作记录 v4（REQ-31e11f：纯文字监控面板） ---- */
.dsh-pm-sn { font-size: 12px; line-height: 1.7; color: var(--dsw-text-primary, #333); padding: 2px 0; }

/* 面板头 */
.dsh-pm-sn-head { display: flex; align-items: baseline; gap: 6px; padding-bottom: 10px; margin-bottom: 4px; border-bottom: 1px solid var(--pm-line, rgba(128,128,128,.12)); }
.dsh-pm-sn-glyph { flex: 0 0 14px; text-align: center; font-size: 12px; }
.dsh-pm-sn-glyph[data-state="done"] { color: #28a745; }
.dsh-pm-sn-glyph[data-state="current"] { color: #4a7dff; }
.dsh-pm-sn-glyph[data-state="pending"] { color: #ccc; }
.dsh-pm-sn-glyph[data-state="skipped"] { color: #ccc; }
.dsh-pm-sn-title { font-weight: 600; font-size: 13px; }
.dsh-pm-sn-time { margin-left: auto; font-size: 11px; color: var(--dsw-text-secondary, #aaa); font-variant-numeric: tabular-nums; }

/* 区块标签 */
.dsh-pm-sn-label { display: block; font-size: 10px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--dsw-text-secondary, #aaa); margin: 14px 0 4px; }

/* 文本层级 */
.dsh-pm-sn-req-title { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.dsh-pm-sn-text { color: var(--dsw-text-primary, #333); }
.dsh-pm-sn-clamp { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.dsh-pm-sn-dim { color: var(--dsw-text-secondary, #999); font-size: 11px; }
.dsh-pm-sn-empty { color: var(--dsw-text-secondary, #bbb); font-style: italic; }
.dsh-pm-sn-warn { color: #dc3545; font-size: 11.5px; margin-top: 6px; }

/* 行（评论/事件） */
.dsh-pm-sn-line { display: flex; align-items: baseline; gap: 8px; padding: 2px 0; }
.dsh-pm-sn-who { flex: 0 0 auto; font-size: 11px; color: var(--dsw-text-secondary, #999); min-width: 30px; }
.dsh-pm-sn-who[data-actor="human"] { color: #2f5fd0; }
.dsh-pm-sn-who[data-actor="agent"] { color: #6f2f8c; }
/* 评论：聊天式（谁在上，内容在下，全宽） */
.dsh-pm-sn-comment { padding: 6px 0; border-bottom: 1px solid rgba(128,128,128,.06); }
.dsh-pm-sn-comment:last-child { border-bottom: none; }
.dsh-pm-sn-comment-who { font-size: 11px; font-weight: 600; margin-bottom: 2px; }
.dsh-pm-sn-comment-who[data-actor="human"] { color: #2f5fd0; }
.dsh-pm-sn-comment-who[data-actor="agent"] { color: #6f2f8c; }
.dsh-pm-sn-comment-who[data-actor="system"] { color: var(--dsw-text-secondary, #999); font-weight: 500; }
.dsh-pm-sn-comment-text { font-size: 12px; line-height: 1.7; color: var(--dsw-text-primary, #333); }
/* DAG 层级（拆分节点） */
.dsh-pm-sn-dag-layer { margin-bottom: 8px; }
.dsh-pm-sn-dag-label { font-size: 10px; font-weight: 600; letter-spacing: 0.04em; color: var(--dsw-text-secondary, #aaa); margin-bottom: 2px; }
.dsh-pm-sn-dag-task { display: flex; align-items: baseline; gap: 8px; padding: 2px 0 2px 12px; }


.dsh-pm-sn-time2 { flex: 0 0 auto; font-size: 11px; color: var(--dsw-text-secondary, #aaa); font-variant-numeric: tabular-nums; min-width: 48px; }

/* 任务执行列表 */
.dsh-pm-sn-task { display: flex; align-items: baseline; gap: 8px; padding: 3px 0; }
.dsh-pm-sn-task-glyph { flex: 0 0 14px; text-align: center; font-size: 11px; }
.dsh-pm-sn-task[data-status="done"] .dsh-pm-sn-task-glyph { color: #28a745; }
.dsh-pm-sn-task-id { flex: 0 0 auto; font-size: 11px; color: var(--dsw-text-secondary, #aaa); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.dsh-pm-sn-task-title { flex: 1; min-width: 0; }
.dsh-pm-sn-task-meta { flex: 0 0 auto; font-size: 11px; color: var(--dsw-text-secondary, #999); font-variant-numeric: tabular-nums; text-align: right; }
.dsh-pm-sn-task.is-current .dsh-pm-sn-task-title { color: #4a7dff; font-weight: 500; }
.dsh-pm-sn-task.is-current .dsh-pm-sn-task-glyph { color: #4a7dff; }
.dsh-pm-sn-task.is-failed .dsh-pm-sn-task-meta { color: #dc3545; }

/* 任务状态分组（实施节点） */
.dsh-pm-sn-group { margin-bottom: 10px; }
.dsh-pm-sn-group-label { font-size: 10px; font-weight: 600; letter-spacing: 0.04em; color: var(--dsw-text-secondary, #aaa); margin-bottom: 4px; }
.dsh-pm-sn-group-label.is-active { color: var(--pm-c-implementing, #4a7dff); }

/* 任务两行结构 */
.dsh-pm-sn-task { padding: 4px 0; border-bottom: 1px solid rgba(128,128,128,.06); }
.dsh-pm-sn-task:last-child { border-bottom: none; }
.dsh-pm-sn-task-line1 { display: flex; align-items: baseline; gap: 6px; }
.dsh-pm-sn-task-line1 .dsh-pm-sn-task-glyph { flex: 0 0 14px; text-align: center; font-size: 11px; }
.dsh-pm-sn-task-line1 .dsh-pm-sn-task-title { flex: 1; min-width: 0; font-size: 12px; }
.dsh-pm-sn-task-line2 { padding-left: 20px; font-size: 11px; color: var(--dsw-text-secondary, #999); font-variant-numeric: tabular-nums; }
.dsh-pm-sn-task-line2 .dsh-pm-sn-doc { font-size: 11px; }


/* 产物文档已并入追溯链 */
.dsh-pm-sn-doc { background: none; border: none; padding: 0; font: inherit; font-size: 12px; color: #4a7dff; cursor: pointer; }
.dsh-pm-sn-doc:hover { text-decoration: underline; }
.dsh-pm-sn-doc.is-missing { color: #dc3545; cursor: default; }
.dsh-pm-sn-doc.is-missing:hover { text-decoration: none; }

/* 追溯链 */
.dsh-pm-trace-chain { margin-top: 10px; font-size: 11px; }
.dsh-pm-trace-chain .dsh-pm-sn-doc { font-size: 11px; }
.dsh-pm-trace-arrow { color: #ccc; margin: 0 3px; }
.dsh-pm-trace-node.is-missing { }


/* （REQ-ff20ca t6）文档弹窗样式已整套删除：文档打开统一走官方右侧栏。
   下面保留 .dsh-pm-md —— view.ts 仍用它渲染需求卡描述。 */
/* markdown 渲染（marked 输出） */
.dsh-pm-md h1, .dsh-pm-md h2, .dsh-pm-md h3, .dsh-pm-md h4 { margin: 14px 0 6px; font-weight: 600; line-height: 1.3; }
.dsh-pm-md h1 { font-size: 16px; } .dsh-pm-md h2 { font-size: 14px; } .dsh-pm-md h3 { font-size: 13px; } .dsh-pm-md h4 { font-size: 12px; }
.dsh-pm-md h1:first-child, .dsh-pm-md h2:first-child { margin-top: 0; }
.dsh-pm-md p { margin: 4px 0; }
.dsh-pm-md code { background: rgba(128,128,128,.12); padding: 1px 4px; border-radius: 3px; font-size: 11px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.dsh-pm-md pre { background: rgba(128,128,128,.08); padding: 10px 12px; border-radius: 6px; overflow-x: auto; margin: 8px 0; }
.dsh-pm-md pre code { background: none; padding: 0; font-size: 11px; line-height: 1.5; }
.dsh-pm-md ul, .dsh-pm-md ol { padding-left: 20px; margin: 4px 0; }
.dsh-pm-md li { margin: 2px 0; }
.dsh-pm-md li > ul, .dsh-pm-md li > ol { margin-top: 4px; margin-bottom: 0; }
.dsh-pm-md li > p { margin: 2px 0; }
.dsh-pm-md li > table { margin: 6px 0; }
.dsh-pm-md li > pre { margin: 6px 0; }
.dsh-pm-md table { border-collapse: collapse; margin: 8px 0; width: 100%; }
.dsh-pm-md th, .dsh-pm-md td { border: 1px solid var(--pm-line, rgba(128,128,128,.2)); padding: 4px 8px; font-size: 11px; text-align: left; }
.dsh-pm-md th { background: rgba(128,128,128,.08); font-weight: 600; }
.dsh-pm-md blockquote { border-left: 3px solid var(--pm-c-implementing, #4a7dff); padding-left: 10px; margin: 8px 0; color: var(--dsw-text-secondary, #666); }
.dsh-pm-md a { color: var(--pm-c-implementing, #4a7dff); }
.dsh-pm-md hr { border: none; border-top: 1px solid var(--pm-line, rgba(128,128,128,.15)); margin: 12px 0; }
.dsh-pm-md strong { font-weight: 600; }

/*WRAP_SENTINEL_NEXT_LINE_MUST_START_AT_COLUMN0*/
/*WRAP_SENTINEL_MARKER*/
`,document.head.appendChild(e)}const kn=[`slots`,`sessions`,`workspaces`,`sidebarRight`];function An(e){try{Cn(),On(),window.__dshReqboardClient?.dispose(),window.__dshPmCtx=e,window.__dshPmSessions=e.sessions,window.__dshPmWorkspaces=e.workspaces;let t=vn(),n=yn(t),r=e=>{e.detail?.open===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(X,r),window.__dshReqboardClient={dispose:()=>{window.removeEventListener(X,r),n(),t.closeBoard(),delete window.__dshPmCtx,delete window.__dshPmSessions,delete window.__dshPmWorkspaces}};let i=e.slots;if(i){try{i.inject(`sidebar.footer.action`,()=>i.register({name:`sidebar.footer.action`,id:o,order:110,label:s},wn))}catch(e){console.error(`[dsh-pmboard] Failed to register sidebar.footer.action:`,e)}try{i.inject(`conversation.session.header.utilities`,()=>i.register({name:`conversation.session.header.utilities`,id:`dsh-pmboard:progress`,order:5,inject:e=>({sessionId:e})},Dn))}catch(e){console.error(`[dsh-pmboard] Failed to register conversation.session.header.utilities:`,e)}}else console.warn(`[dsh-pmboard] ctx.slots unavailable`)}catch(e){console.error(`[dsh-pmboard] client half failed to start:`,e)}}exports.apply=An,exports.inject=kn,exports.name=`dsh-pmboard/client`;
			return module.exports;
		}
	});

