Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");function t(e){return String(e??``).replace(/[&<>"']/g,e=>({"&":`&amp;`,"<":`&lt;`,">":`&gt;`,'"':`&quot;`,"'":`&#39;`})[e]??e)}const n=e=>String(e).padStart(2,`0`);function r(e){if(!e)return null;let t=new Date(String(e));return Number.isNaN(t.getTime())?null:t}function i(e,t){if(!e)return`—`;let i=r(e);if(!i)return String(e).slice(0,16).replace(`T`,` `);let a=new Date,o=i.getFullYear()===a.getFullYear()&&i.getMonth()===a.getMonth()&&i.getDate()===a.getDate(),s=n(i.getHours())+`:`+n(i.getMinutes());return t?.omitDateIfToday&&o?s:(t?.withYear?i.getFullYear()+`-`+n(i.getMonth()+1)+`-`+n(i.getDate()):n(i.getMonth()+1)+`-`+n(i.getDate()))+` `+s}function a(e){return[`.`+e+`-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }`,`.`+e+`-toast.ok { background:#529b2e; }`,`.`+e+`-toast.err { background:#e64545; }`,`.`+e+`-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }`].join(`
`)}function o(e){let t=`dsh-toast-styles-`+e,n=document.getElementById(t);if(n!==null&&n.tagName===`STYLE`)return()=>n.remove();let r=document.createElement(`style`);return r.id=t,r.textContent=a(e),(document.head??document.documentElement).appendChild(r),()=>{document.getElementById(t)?.remove()}}function s(e,t,n,r=4200){let i=document.createElement(`div`);i.className=n+`-toast `+(t?`ok`:`err`),i.textContent=e,document.body.appendChild(i),window.setTimeout(()=>{i.classList.add(`out`),window.setTimeout(()=>i.remove(),350)},r)}const c=`dsh-right-tab-host`,l=`dsh-right-tab-host-style`,u=`
.${c}{display:flex;flex-direction:column;height:100%;min-height:0;overflow:hidden}
.${c}>*{min-height:0}
.${c} .dsh-right-tab-error{padding:16px 18px;color:#b94a48;font:13px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
`;function d(){if(typeof document>`u`||document.getElementById(l)!==null)return;let e=document.createElement(`style`);e.id=l,e.textContent=u,document.head.appendChild(e)}function f(t){return function(n){let r=(0,e.useRef)(null);return(0,e.useEffect)(()=>{let e=r.current;if(e===null)return;let n;try{n=t.mount(e)}catch(n){console.error(`[page-kit] 右栏看板挂载失败 `+t.id+`:`,n);let r=document.createElement(`div`);r.className=`dsh-right-tab-error`,r.textContent=`看板加载失败：`+(n instanceof Error?n.message:String(n)),e.appendChild(r)}return()=>{try{typeof n==`function`&&n()}catch(e){console.error(`[page-kit] 右栏看板卸载清理失败 `+t.id+`:`,e)}}},[]),(0,e.createElement)(`div`,{ref:r,className:c,"data-right-tab":t.id})}}function p(e,t){let n=e??{},r=n.sidebarRightTabs,i=n.sidebarRight,a=n.slots;if(r===void 0||typeof r.register!=`function`)throw Error(`sidebarRightTabs 服务不可用（DSH 官方右侧栏未加载）`);if(i===void 0||typeof i.openTab!=`function`)throw Error(`sidebarRight 服务不可用（DSH 官方右侧栏未加载）`);d();let o=[];if(((e,t)=>{try{if(typeof n.effect==`function`){n.effect(e,t);return}let r=e();typeof r==`function`&&o.push(r)}catch(e){console.error(`[page-kit] 右栏注册失败 `+t+`:`,e)}})(()=>r.register({id:t.id,kind:t.kind,title:()=>t.title,keepMounted:!0}),`tab-type:`+t.id),a!==void 0&&typeof a.register==`function`){let e=f(t);try{typeof a.inject==`function`?a.inject(`sidebar.right.pane.tab`,()=>a.register({name:`sidebar.right.pane.tab`,key:t.id},e)):a.register({name:`sidebar.right.pane.tab`,key:t.id},e)}catch(e){console.error(`[page-kit] 右栏正文注册失败 `+t.id+`:`,e)}}else console.error(`[page-kit] slots 服务不可用，右栏正文未注册 `+t.id);let s=()=>{try{return i.openTab(t.kind),!0}catch(e){return console.error(`[page-kit] 右栏打开失败 `+t.kind+`:`,e),!1}},c=()=>{try{if(typeof i.isExpanded==`function`&&i.isExpanded()===!1||typeof i.active!=`function`)return!1;let e=i.active();return e!=null&&e.kind===t.kind}catch{return!1}},l=()=>{if(c())try{let e=i.active?.();e!=null&&e.id!==void 0&&i.close?.(e.id)}catch(e){console.error(`[page-kit] 右栏关闭失败 `+t.kind+`:`,e)}};return{open:s,toggle:()=>{c()?l():s()},close:l,isActive:c,dispose:()=>{l();for(let e of o.splice(0))try{e()}catch{}}}}const m=[{key:`engine`,zh:`盈利引擎线`},{key:`autonomy`,zh:`Autonomy 线`},{key:`account`,zh:`账户定时任务`},{key:`other`,zh:`临时/核验/其他`}],h={engine:`盈利引擎线`,autonomy:`Autonomy 线`,account:`账户定时任务`,other:`临时/核验/其他`},g={profit_engine:`engine`,autonomy:`autonomy`},_=new Set(`每日数据更新.每日数据质量检查.每日财报时效性检查.每周财务数据更新.market_daily_snapshot.chan-scan-daily.chan_scan_daily.market-style-update.market_style_update.fund_flow_update.market_perception_daily.daily-pool-refresh.daily_pool_refresh.pre-market-scan.pre_market_scan.每日信号生成.每日信号执行.signal-perf-backfill-daily.signal_perf_backfill_daily.signal_generate_sell.v13-risk-check.v13_risk_check.daily_trade_verify.每日模型重训.pre-market-routine.afternoon-open-check-live.m4-circuit-breaker-live.post-market-routine-live.data-quality-monitor-daily.event-calendar-check.attribution-daily.intraday-surge-scan-am.intraday-surge-scan-pm.equity-snapshot-daily.ingest_events_daily.ingest_events_policy.ingest_events_history.ingest_disclosure_calendar.minute_kline_sync.industry_chain_refresh.equity_snapshot_daily.core_plan_generate.strategy_loop_weekly`.split(`.`)),v=new Set([`daily-strategy-validation`,`daily_strategy_validation`,`v13-verification`,`v13_verification`,`weekly-strategy-discovery`,`weekly_strategy_discovery`,`每周策略发现`,`chan-knowledge-distill-weekly`,`chan_knowledge_distill_weekly`,`v13-weekly-report`,`v13_weekly_report`,`每周报告生成`,`evolution-distill-daily`,`evolution-gate-adjudicate`,`evolution-weekly-variant`,`meta-learning-weekly`,`weekly-report-m6`,`weekly_evolution`,`weekly_memory_distill`,`daily_ai_review`,`daily_recall_audit`,`weekly_tool_roi_review`,`data_hygiene_probe`]),y=new Set([`v13-simulation-trading`,`v13_simulation_trading`,`v14-simulation-trading`]);function b(e){let t=String(e??``);return _.has(t)?`engine`:v.has(t)?`autonomy`:y.has(t)||t.startsWith(`agent-brain-`)?`account`:`other`}const ee=new Set([`session-probe`]);function te(e){return ee.has(e)||e.startsWith(`board-`)||e.startsWith(`geer-`)||e===`v2_health_check`}function x(e){let t=String(e?.name??``),n=String(e?.agentLine??``).trim();if(n){let e=g[n]??n;if(e===`engine`||e===`autonomy`||e===`account`||e===`other`)return{line:e,source:`field`,unclassified:!1}}let r=b(t);return r===`other`?te(t)?{line:`other`,source:`name`,unclassified:!1}:{line:`other`,source:`fallback`,unclassified:!0}:{line:r,source:`name`,unclassified:!1}}function ne(e){let t=x(e).line;return t===`engine`||t===`autonomy`}function S(e){return i(String(e),{omitDateIfToday:!0})}function C(e){let t=String(e??``).match(/^(\d{2}):(\d{2})/);return t?Number(t[1])*60+Number(t[2]):9999}const re=[`周日`,`周一`,`周二`,`周三`,`周四`,`周五`,`周六`];function w(e){let t=String(e??``).trim(),n=t.split(/\s+/);if(n.length!==5)return t||`—`;let r=n[0],i=n[1],a=n[2],o=n[3],s=n[4],c=e=>/^\d+$/.test(e)?Number(e):null;if(i===`*`||i===`?`)return r===`0`||r===`*`?`每小时`:t;let l=c(i),u=r===`*`||r===`?`?0:c(r);if(l===null||u===null||l>23||u>59)return t;let d=String(l).padStart(2,`0`)+`:`+String(u).padStart(2,`0`),f=c(a),p=o!==`*`&&o!==`?`?c(o):null;if(f!==null)return(p===null?`每月 `+f+` 日`:`每年 `+p+` 月 `+f+` 日`)+` `+d;if(a!==`*`&&a!==`?`&&a!==`L`)return t;if(a===`L`)return`每月最后一日 `+d;let m=ie(s);if(m===null)return t;let h;return h=m.length===7?`每日`:m.length===5&&m.every(e=>e>=1&&e<=5)?`工作日`:`每`+m.map(e=>re[e]).join(`、`),p!==null&&(h+=`（`+p+` 月）`),h+` `+d}function ie(e){if(e===`*`||e===`?`){let e=[];for(let t=0;t<7;t++)e.push(t);return e}let t=[];for(let n of e.split(`,`)){let e=/^(\d+)(?:-(\d+))?$/.exec(n.trim());if(!e)return null;let r=Number(e[1])%7,i=e[2]?Number(e[2])%7:r;if(i<r)return null;for(let e=r;e<=i;e++)t.push(e)}return[...new Set(t)].sort((e,t)=>e-t)}function T(e,t){let n=String(e??``).trim();return n.length<=t?n:n.slice(0,t)+`…`}const E={success:`成功`,failed:`失败`,pending:`待执行`,skipped:`已跳过`,off_day:`非执行日`,unknown:`未知`},ae={success:`✅`,failed:`❌`,pending:`⏳`,skipped:`⏭️`,off_day:`⏸`,unknown:`❔`},D={success:`ok`,failed:`bad`,pending:`wait`,skipped:`wait`,off_day:`off`,unknown:`unk`},O={confirmed:`已确认`,pending:`等待`,off_day:`非执行日`,failed:`失败`,late:`晚点`,degraded:`降级`,unknown:`未知`},k={confirmed:`ok`,pending:`wait`,off_day:`off`,failed:`bad`,late:`late`,degraded:`deg`,unknown:`unk`},oe={ok:`正常`,degraded:`降级`,failed:`故障`,unknown:`未知`},se={ok:`ok`,degraded:`deg`,failed:`bad`,unknown:`unk`},ce={"quantsys-v2":`量化后端 quantsys-v2`,"agent-os":`Agent OS`,postgres:`数据库 PostgreSQL`,"agent-dh":`Agent-DH 宿主`},le={market_daily_snapshot:`每日市场快照`,chan_scan_daily:`产业链链扫`,"chan-scan-daily":`产业链链扫`,v13_risk_check:`风控熔断检查`,"v13-risk-check":`风控熔断检查`,daily_trade_verify:`交易对账`,signal_perf_backfill_daily:`信号表现回填`,"signal-perf-backfill-daily":`信号表现回填`,v13_weekly_report:`每周报告`,"v13-weekly-report":`每周报告(v13)`,market_style_update:`市场风格更新`,"market-style-update":`市场风格更新`,v13_simulation_trading:`模拟交易执行`,"v13-simulation-trading":`模拟交易执行`,v13_verification:`策略验证裁决`,"v13-verification":`策略验证裁决`,pre_market_scan:`盘前扫描`,"pre-market-scan":`盘前扫描`,weekly_strategy_discovery:`周度策略发现`,"weekly-strategy-discovery":`周度策略发现`,daily_strategy_validation:`策略日验证`,"daily-strategy-validation":`策略日验证`,daily_pool_refresh:`股票池刷新`,"daily-pool-refresh":`股票池刷新`,fund_flow_update:`资金流数据更新`,chan_knowledge_distill_weekly:`知识蒸馏(周)`,"chan-knowledge-distill-weekly":`知识蒸馏(周)`,每日数据更新:`每日数据更新`,每日数据质量检查:`每日数据质量检查`,每周财务数据更新:`每周财务数据更新`,每周策略发现:`每周策略发现`,每日模型重训:`每日模型重训`,"attribution-daily":`业绩归因(M6)`,minute_kline_sync:`分钟线同步`,industry_chain_refresh:`产业链刷新`,ingest_events_daily:`事件入库(每日)`,ingest_events_policy:`事件入库(政策)`,"session-probe":`会话探针`,"intraday-surge-scan-am":`盘中异动扫描(上午)`,"intraday-surge-scan-pm":`盘中异动扫描(下午)`,每日财报时效性检查:`每日财报时效性检查`,每日信号生成:`每日信号生成`,每日信号执行:`每日信号执行`,每周报告生成:`每周报告生成`,"pre-market-routine":`盘前例程`,"afternoon-open-check-live":`午后开盘检查`,"data-quality-monitor-daily":`数据质量监控`,"event-calendar-check":`事件日历检查`,"m4-circuit-breaker-live":`熔断回路检查`,"post-market-routine-live":`盘后例程`,"evolution-distill-daily":`进化蒸馏`,"evolution-gate-adjudicate":`进化裁决`,"evolution-weekly-variant":`进化变体`,"meta-learning-weekly":`元学习`,"weekly-report-m6":`学习飞轮周报`,"geer-take-profit-0901":`歌尔止盈观察`,"v14-simulation-trading":`模拟交易执行(v14)`,"agent-brain-morning-analysis":`晨间账户分析`,"agent-brain-realtime-check":`账户实时检查`,"agent-brain-daily-review":`账户日终复盘`,"agent-brain-daily-audit":`账户每日审计`,"agent-brain-weekly-roi":`账户周度ROI`,"agent-brain-weekly-evolution":`账户周度进化`,"agent-brain-weekly-distill":`账户周度蒸馏`,market_perception_daily:`市场感知`,signal_generate_sell:`卖出信号生成`,v2_health_check:`信号源健康检查`,"board-3341a342-verify-daily-review":`执行看板核验`};function A(e){let t=String(e??``);return le[t]??t}function ue(e){return ne({name:e})}const de=[{code:`M0`,zh:`数据地基`},{code:`M1`,zh:`市场感知`},{code:`M2`,zh:`股票池`},{code:`M3`,zh:`信号生成`},{code:`M4`,zh:`风控止损`},{code:`M5`,zh:`交易对账`},{code:`M6`,zh:`经验进化`}],fe=[{code:`L1`,zh:`策略验证`},{code:`L2`,zh:`经验蒸馏`},{code:`L3`,zh:`验证门裁决`},{code:`L4`,zh:`周报进化`}],j={failed:5,late:4,degraded:3,pending:2,off_day:1,unknown:0,confirmed:0};function pe(e){if(e.length===0)return{status:`unknown`,label:`暂无检查点`};let t=`confirmed`;for(let n of e){let e=String(n.status??`unknown`);(j[e]??0)>(j[t]??0)&&(t=e)}return{status:t,label:O[t]??t}}function me(){let e=document.createElement(`div`);e.className=`dsh-exec-board`;let n=e=>{let t=document.createElement(`div`);return t.innerHTML=e,t.firstElementChild},r=(e,r,i,a=`bd`)=>n(`<section class="dsh-exec-cardx"><div class="hd"><span class="t">`+t(e)+`</span><span class="more">`+t(r)+`</span></div><div class="`+a+`" data-role="`+i+`"></div></section>`),i=document.createElement(`div`);i.className=`dsh-exec-wrap`;let a=n(`<div class="dsh-exec-head"><h1 class="dsh-exec-title">双线执行确认看板<small>只读监控 · 运行与操作由 agent 自动完成</small></h1><div class="dsh-exec-meta"><span class="dsh-exec-last" data-role="lastFetch">—</span><button type="button" class="dsh-exec-btn" data-role="refresh">↻ 刷新</button></div></div>`),o=n(`<div class="dsh-exec-banner" data-role="banner"></div>`),s=r(`今日执行总览`,`双线口径（盈利引擎 + Autonomy）· 来自当日 cron 计划与运行结果`,`healthBox`),c=r(`执行流水线`,`ENGINE M0–M6 × AUTONOMY L1–L4 检查点状态`,`flowBox`),l=r(`今日时间轴`,`按业务线分组：盈利引擎 / Autonomy 展开 · 账户与其它折叠 · 徽标 v2/os=调度来源 dh/ts=调用 agent · 按计划时刻排序`,`timelineBox`),u=r(`调度任务`,`按业务线分类切换（盈利引擎 / Autonomy / 账户定时 / 临时核验）· 徽标 v2/os=调度来源 dh/ts=调用 agent · 点击任务行查看失败原因`,`tasksBox`),d=r(`错误事件`,`Agent OS error_events 单一事实源 · 全部历史分页（Tabs 状态过滤 + 页码）· 事件 ID：点击 #ID 复制完整 ID · 处置：我来解决=认领并投递 / 解决 / 忽略 / 复开`,`errsBox`);d.style.display=`none`;let f=r(`流水线阻断`,`failed/late 且声明阻断下游`,`blockBox`);f.style.display=`none`;let p=r(`僵尸任务`,`数据库存在但调度器未加载的任务`,`orphanedBox`);p.style.display=`none`,i.append(a,o,s,c,l,u,d,f,p),e.appendChild(i);let m=t=>e.querySelector(t);return{board:e,meta:m(`[data-role="lastFetch"]`),banner:o,healthBox:m(`[data-role="healthBox"]`),flowBox:m(`[data-role="flowBox"]`),timelineBox:m(`[data-role="timelineBox"]`),tasksBox:m(`[data-role="tasksBox"]`),errsSec:d,errsBox:m(`[data-role="errsBox"]`),blockSec:f,blockBox:m(`[data-role="blockBox"]`),orphanedSec:p,orphanedBox:m(`[data-role="orphanedBox"]`)}}function he(e,n){let r=(n.timeline??[]).filter(e=>e.status!==`off_day`&&ue({name:e.taskName,agentLine:e.agentLine})),i=r.length,a=0,o=0;for(let e of r)e.status===`success`?a++:e.status===`failed`&&o++;let s=Math.max(0,i-a-o),c=(e,t,n)=>`<div class="hb-item `+n+`"><div class="v">`+e+`</div><div class="n">`+t+`</div></div>`,l=`<div class="dsh-exec-hb">`+c(String(i),`今日计划任务`,`t`)+c(String(a),`✅ 已完成`,`ok`)+c(String(o),`❌ 失败`,o>0?`bad`:`ok`)+c(String(s),`⏳ 待执行`,`wait`)+`</div>`,u=n.health??[];u.length>0&&(l+=`<div class="dsh-exec-pills">`+u.map(e=>{let n=String(e.status??`unknown`);return`<span class="pill `+(n===`ok`?`ok`:`warn`)+`" title="`+t(e.error??``)+`"><i class="dot `+(se[n]??`unk`)+`"></i>`+t(ce[e.name??``]??e.name??``)+`<b>`+t(oe[n]??n)+`</b></span>`}).join(``)+`</div>`),e.healthBox.innerHTML=l}function ge(e,n,r){let i=pe(r),a=k[i.status]??`unk`,o=r.length===0?`<li class="cp-empty"><i class="dot unk"></i>暂无检查点</li>`:r.map(e=>{let n=String(e.status??`unknown`),r=e.expectTime?`<time class="cp-tm" title="计划执行 `+t(e.expectTime)+`">`+t(e.expectTime)+`</time>`:``;return`<li><i class="dot `+(k[n]??`unk`)+`"></i>`+r+t(e.name??`?`)+`<em>`+t(O[n]??n)+`</em></li>`}).join(``);return`<div class="node st-`+a+`"><div class="n-top"><i class="dot `+a+`"></i><b>`+e+`</b><span>`+t(n)+`</span><em>`+t(i.label)+`</em></div><ul class="cps">`+o+`</ul></div>`}function _e(e,t){let n=t.checkpoints??[],r={};for(let e of n){let t=String(e.line??``),n=String(e.module??``);if(t!==`engine`&&t!==`autonomy`)continue;let i=t+`|`+n;(r[i]=r[i]||[]).push(e)}let i=(e,t,n)=>`<div class="dsh-exec-band"><div class="band-t"><span class="band-badge `+t+`">`+e+`</span>    <i></i></div><div class="band-nodes">`+n.map(e=>ge(e.code,e.zh,r[t+`|`+e.code]??[])).join(``)+`</div></div>`;e.flowBox.innerHTML=i(`ENGINE`,`engine`,de)+i(`AUTONOMY`,`autonomy`,fe)}function ve(e){return E[e]??`未知`}const ye={v2:`引擎任务：quantsys-v2 cron 自动执行（不走 agent）`,os:`Agent OS 定时：webhook 触发 agent 执行`};function M(e){let n=String(e??``);if(n!==`v2`&&n!==`os`)return``;let r=n===`v2`?`引擎`:`系统`;return`<span class="exec-chip src `+n+`" title="`+t(ye[n]??``)+`">`+r+`</span>`}function N(e){let t=String(e??``);return t!==`dh`&&t!==`ts`?``:`<span class="exec-chip ag `+t+`" title="调用 `+(t===`dh`?`agent-dh`:`agent-ts`)+` 智能体执行">智能体</span>`}function P(e){let n=String(e.status??`unknown`),r=String(e.expectedTime??``),i=n===`failed`&&e.error?` title="`+t(e.error)+`"`:``;return`<div class="tl-item `+(D[n]??`unk`)+`"`+i+`><span class="tl-tm">`+t(r.slice(0,5))+`</span><span class="tl-ic">`+(ae[n]??`❔`)+`</span><div class="tl-bd"><div class="tl-nm">`+t(A(e.taskName))+`</div><div class="tl-st `+(D[n]??`unk`)+`">`+t(ve(n))+`</div><span class="tl-tags">`+M(e.src)+N(e.agentCall)+`</span></div></div>`}function F(e){let t=e.filter(e=>(e.freq??`daily`)!==`weekly`).length;return`共 `+e.length+` 项 · 日执行 `+t+` / 周执行 `+(e.length-t)}function be(e){let t=e.taskCoverage;if(!t)return``;let n=[],r=t.os,i=r?.included??0;if(i>0){let e=r?.lineTagged??0;n.push(e>=i?`OS 侧 `+i+` 个任务均带 agent_line 字段（分类以库中字段为准）`:`OS 侧 `+e+`/`+i+` 个任务带 agent_line 字段，其余按任务名名单兜底`)}let a=t.v2;if(a&&(a.total??0)>0){let e=a.domainMissing??0,t=a.missingNames??[],r=a.enabledTotal??a.total??0,i=r-e;n.push(`v2 侧 domain（六域，与业务线正交）启用任务已打标 `+i+`/`+r+(e>0?`，缺 `+e+`：`+t.slice(0,3).join(`、`)+(t.length>3?` 等`:``):``));let o=a.untaggedDisabled??[];o.length>0&&n.push(`v2 未启用任务未打标 `+o.length+` 个：`+o.slice(0,3).join(`、`)+(o.length>3?` 等`:``)+`（不参与对账，含有意留空）`)}let o=t.unclassified??[];o.length>0&&n.push(`⚠️ 未归类 `+o.length+` 个：`+o.slice(0,6).join(`、`)+(o.length>6?` 等`:``)+`（请补录名单或打标）`);let s=t.os;if(s&&(s.excluded??0)>0){let e=Object.entries(s.byReason??{}).filter(([,e])=>Number(e)>0).map(([e,t])=>e+` `+t).join(` / `);n.push(`OS 接口 `+(s.apiTotal??0)+` 个 → 并入 `+(s.included??0)+`（排除 `+(s.excluded??0)+(e?`：`+e:``)+`）`)}return n.length===0?``:`<div class="dsh-exec-cover">`+n.map(e=>`<span>`+e+`</span>`).join(``)+`</div>`}function xe(e,n){let r=(n.timeline??[]).slice().sort((e,t)=>C(e.expectedTime)-C(t.expectedTime)),i=be(n);if(r.length===0){e.timelineBox.innerHTML=i+`<div class="dsh-exec-empty">今日暂无计划任务</div>`;return}let a={engine:[],autonomy:[],account:[],other:[]};for(let e of r)(a[x({name:e.taskName,agentLine:e.agentLine}).line]??a.other).push(e);let o=(e,n)=>`<div class="dsh-exec-tlg t-`+e+`"><div class="tlg-t"><span class="t">`+t(h[e]??e)+`</span><em>`+t(F(n))+`</em></div><div class="dsh-exec-tl-list">`+n.map(P).join(``)+`</div></div>`,s=(e,n)=>n.length===0?``:`<details class="dsh-exec-tld"><summary><span class="caret">▶</span><i class="dk l-`+e+`"></i><b>`+t(h[e]??e)+`</b><em>`+t(F(n))+`</em></summary><div class="dsh-exec-tl-list">`+n.map(P).join(``)+`</div></details>`,c=o(`engine`,a.engine)+o(`autonomy`,a.autonomy)+s(`account`,a.account)+s(`other`,a.other);e.timelineBox.innerHTML=i+c}function I(e){if(e.enabled!==!0&&e.enabled!==`true`&&e.enabled!==1)return{cls:`off`,label:`未启用`};let t=Number(e.todaySuccess)||0,n=Number(e.todayTriggered)||0;if(n>0)return t>=n?{cls:`ok`,label:`今日成功`}:{cls:`bad`,label:`今日失败`};let r=``;return typeof e.lastRun==`string`?r=e.lastRun:e.lastRun&&typeof e.lastRun==`object`&&(r=String(e.lastRun.status??``)),r===`success`?{cls:`ok`,label:`上次成功`}:r===`failed`?{cls:`bad`,label:`上次失败`}:r===`skipped`?{cls:`wait`,label:`已跳过`}:{cls:`wait`,label:`待执行`}}let L=null,R=`all`;function Se(e){L=e}function Ce(e){R=e}let z=1,B=`all`,V=null;function we(e){z=e>0?Math.trunc(e):1}function Te(e){return Math.floor(e/10)+1}function Ee(e,t,n){let r=t=>`<button type="button" class="tpg-num`+(t===e?` act`:``)+`"`+(t===e?` aria-current="page"`:``)+` data-tkpage="`+t+`">`+t+`</button>`,i=[];if(t<=7)for(let e=1;e<=t;e++)i.push(r(e));else{let n=[];for(let r of[1,e-1,e,e+1,t].sort((e,t)=>e-t))r<1||r>t||n.includes(r)||n.push(r);let a=0;for(let e of n)a!==0&&e-a>1&&i.push(`<span class="tpg-gap">…</span>`),i.push(r(e)),a=e}return`<button type="button" class="tpg-arr" data-tkpage="`+(e-1)+`"`+(e<=1?` disabled`:``)+`>‹ 上一页</button><span class="tpg-nums">`+i.join(``)+`</span><button type="button" class="tpg-arr" data-tkpage="`+(e+1)+`"`+(e>=t?` disabled`:``)+`>下一页 ›</button><span class="tpg-cnt">第 `+e+`/`+t+` 页 · 共 `+n+` 条</span>`}function H(e){let t=e.lastRun;if(t==null)return{at:`—`,st:``,err:``};let n=``,r=``,i=``;if(typeof t==`string`)/^(success|failed|skipped|running|pending|unknown)$/.test(t)?r=t:n=S(t);else if(typeof t==`object`){let e=t;n=S(e.triggeredAt),r=String(e.status??``),i=String(e.error??e.message??``)}return{at:n||`—`,st:r,err:i}}function De(e){let t=String(e??``).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);return t?t[1]+`-`+t[2]+`-`+t[3]+` `+t[4]+`:`+t[5]:String(e??``).trim()||`—`}function Oe(e){let n=x(e),r=n.line,i=I(e),a=H(e),o=Number(e.todayTriggered)||0,s=Number(e.todaySuccess)||0,c=String(e.name??``),l=t(A(c)),u=(e,t)=>`<div class="tkd-i"><b>`+e+`</b><span>`+t+`</span></div>`,d=`<div class="tkd-i"><b>名称</b><span`+(A(c)===c?``:` title="系统任务名：`+t(c)+`"`)+`>`+l+`</span></div>`;d+=u(`调度来源`,e.src===`os`?`Agent OS（webhook 触发）`:`quantsys-v2 引擎`),(e.agentCall===`dh`||e.agentCall===`ts`)&&(d+=u(`调用 Agent`,e.agentCall===`dh`?`agent-dh（LLM 智能体）`:`agent-ts（LLM 智能体）`)),d+=u(`状态`,`<span class="tag `+i.cls+`">`+t(i.label)+`</span>`);let f=n.source===`field`?`任务自带字段`:n.source===`name`?`名单兜底`:`未归类（待补录）`;d+=u(`业务线`,t(h[r]??r)+` <em class="tkd-code">`+t(f)+`</em>`);let p=String(e.scheduleExpr??``).trim(),m=w(p);d+=u(`计划时刻`,t(m)+(m&&m!==p&&m!==`—`?`<em class="tkd-code">原 cron: `+t(p)+`</em>`:``)),d+=u(`上次运行`,t(a.at)),d+=u(`上次结果`,a.st?t(E[a.st]??a.st):`—`),d+=u(`今日`,t(o+` 次触发 / `+s+` 成功`)),d+=u(`下次运行`,t(De(e.nextRunAt)));let g=a.err||String(e.error??``);return g&&(d+=`<div class="tkd-i tkd-err"><b>失败原因</b><span>`+t(g)+`</span></div>`),d}function U(e,n){let r=n.tasks??[];if(r.length===0){L=null,R=`all`,z=1,B=`all`,V=null,e.tasksBox.innerHTML=`<div class="dsh-exec-empty">暂无调度任务</div>`;return}let i={engine:0,autonomy:0,account:0,other:0};for(let e of r){let t=x(e).line;i[t]=(i[t]??0)+1}R===`all`||(i[R]??0)>0||(R=`all`);let a=r.filter(e=>R===`all`||x(e).line===R);L!==null&&!a.some(e=>String(e.name)===L)&&(L=null);let o=R!==B,s=L!==V;B=R,V=L,o&&(z=1);let c=Math.max(1,Math.ceil(a.length/10));if(z>c&&(z=c),(o||s)&&L!==null){let e=a.findIndex(e=>String(e.name)===L);e>=0&&(z=Te(e))}let l=a.slice((z-1)*10,z*10);L!==null&&!l.some(e=>String(e.name)===L)&&(L=null);let u=e=>`<b class="c">`+e+`</b>`,d=(e,t,n)=>`<button type="button" class="dsh-exec-tab`+(R===e?` act`:``)+`" data-dom="`+e+`">`+t+u(n)+`</button>`,f=[d(`all`,`全部`,r.length)];for(let e of m)(i[e.key]??0)>0&&f.push(d(e.key,`<i class="dk l-`+e.key+`"></i>`+t(e.zh),i[e.key]));let p=l.map(e=>{let n=String(e.name??``),r=I(e),i=H(e),a=Number(e.todayTriggered)||0,o=Number(e.todaySuccess)||0,s=i.err||String(e.error??``),c=n===L?` sel`:``,l=A(n);return`<tr class="dsh-exec-tr`+c+`" data-tk="`+t(n)+`"`+(s?` title="失败原因：`+t(s.slice(0,300))+`"`:``)+`><td class="nm"`+(l===n?``:` title="系统任务名：`+t(n)+`"`)+`><span class="ln-hd"><i class="dk l-`+x(e).line+`"></i><span class="zh">`+t(l)+`</span></span></td><td class="cr" title="`+(e.scheduleExpr?t(`原 cron: `+String(e.scheduleExpr).trim()):``)+`">`+t(w(e.scheduleExpr))+`</td><td class="st"><span class="tag `+r.cls+`">`+t(r.label)+`</span>`+M(e.src)+N(e.agentCall)+`</td><td class="tm">`+t(i.at)+(i.st?`<em class="ls `+(D[i.st]??`unk`)+`">`+t(E[i.st]??i.st)+`</em>`:``)+`</td><td class="td">`+t(a+` 触发 / `+o+` 成功`)+`</td><td class="nx">`+t(S(e.nextRunAt))+`</td><td class="op">`+(r.cls===`bad`?`<button type="button" class="dsh-exec-solve" data-solve-task="`+t(n)+`" title="把该失败任务投递给窗口排查处置">我来解决</button>`:``)+`</td></tr>`}).join(``),h=a.length>10?`<div class="dsh-exec-tkpg">`+Ee(z,c,a.length)+`</div>`:``,g=L===null?null:a.find(e=>String(e.name)===L);e.tasksBox.innerHTML=`<div class="dsh-exec-legend dsh-exec-legend2"><span class="dsh-exec-hint">按业务线点击 tab 切换 · 点击任务行查看失败原因 · 失败行/错误条可点「我来解决」投递窗口排查 · 表底每页 10 条翻页 · <i class="dot ok"></i>成功 <i class="dot bad"></i>失败 <i class="dot wait"></i>待执行 <i class="dot off"></i>未启用</span></div><div class="dsh-exec-tabs">`+f.join(``)+`</div><div class="dsh-exec-tkcard"><div class="dsh-exec-tbwrap"><table class="dsh-exec-tb"><thead><tr><th>任务</th><th>计划时刻</th><th>状态</th><th>上次运行</th><th>今日</th><th>下次运行</th><th class="op">处理</th></tr></thead><tbody>`+(p||`<tr class="empty"><td colspan="7">该分类下暂无任务</td></tr>`)+`</tbody></table></div>`+h+`</div>`+(g?`<div class="dsh-exec-tkdetail">`+Oe(g)+`</div>`:``)}const W={open:`待处理`,processing:`处理中`,resolved:`已解决`,ignored:`已忽略`};function ke(e,n){let r=String(e.source??``).toLowerCase(),i=r.includes(`os`)?`os`:r.includes(`dsh`)?`dsh`:`v2`,a=e.status&&W[e.status]?e.status:`open`,o=Number(e.occurrenceCount)||1,s=String(e.line??e.msg??``).replace(/\n/g,` `),c=e.status===`processing`&&e.assignee?`<span class="asg" title="认领窗口">👤 `+t(e.assignee)+`</span>`:``,l=a===`processing`&&!e.assignee?`<span class="zombie" title="僵尸处理中：状态=处理中但无责任人。可点「认领」接手（P0 转移边）；超过 2 小时无人认领将由 P1 巡检自动回落为待处理">⚠ 僵尸(无责任人)</span>`:``,u=(a===`resolved`||a===`ignored`)&&e.resolutionNote?`<span class="note" title="`+t(e.resolutionNote)+`">📝 `+t(T(String(e.resolutionNote).replace(/\n/g,` `),60))+`</span>`:``,d=` data-evid="`+t(String(e.id??``))+`"`,f=String(e.id??``),p=f===``?`<span class="evid none" title="该行无 event id">#无ID</span>`:`<button type="button" class="evid" data-evcopy="`+t(f)+`" title="事件 ID（点击复制完整 ID）：`+t(f)+`">#`+t(f.slice(0,8))+`</button>`,m=``;return m=a===`open`?`<button type="button" class="dsh-exec-solve" data-solve-err="`+n+`"`+d+` title="认领(assignee=本窗口,状态→处理中)并投递给窗口排查处置">我来解决</button><button type="button" class="dsh-exec-evact"`+d+` data-evact="resolve" title="标记已解决">解决</button><button type="button" class="dsh-exec-evact"`+d+` data-evact="ignore" title="标记已忽略（不处置）">忽略</button>`:a===`processing`?(l===``?``:`<button type="button" class="dsh-exec-evact dsh-exec-claim"`+d+` data-evact="claim" title="僵尸回收：认领该处理中事件（assignee=本窗口，P0 转移边）">认领</button>`)+`<button type="button" class="dsh-exec-evact"`+d+` data-evact="resolve" title="已处置完成，标记解决">解决</button><button type="button" class="dsh-exec-evact"`+d+` data-evact="ignore" title="标记已忽略（不处置）">忽略</button>`:`<button type="button" class="dsh-exec-evact"`+d+` data-evact="reopen" title="重新打开为待处理">复开</button>`,`<li class="st-`+a+`"><span class="src `+i+`">`+t(e.source??`?`)+`</span><span class="evst st-`+a+`">`+W[a]+`</span>`+p+`<time title="最近出现 `+t(String(e.lastSeenAt??e.timestamp??``))+`">`+t(S(e.timestamp??e.lastSeenAt))+`</time>`+(o>1?`<span class="occ" title="同指纹累计出现 `+o+` 次（去重合并）">×`+o+`</span>`:``)+`<span class="line" title="`+t(s.slice(0,500))+`">`+t(T(s,120))+`</span>`+l+c+u+`<span class="op">`+m+`</span></li>`}function Ae(e,t,n){let r=t=>`<button type="button" class="tpg-num`+(t===e?` act`:``)+`"`+(t===e?` aria-current="page"`:``)+` data-errpage="`+t+`">`+t+`</button>`,i=[];if(t<=7)for(let e=1;e<=t;e++)i.push(r(e));else{let n=[];for(let r of[1,e-1,e,e+1,t].sort((e,t)=>e-t))r<1||r>t||n.includes(r)||n.push(r);let a=0;for(let e of n)a!==0&&e-a>1&&i.push(`<span class="tpg-gap">…</span>`),i.push(r(e)),a=e}return`<button type="button" class="tpg-arr" data-errpage="`+(e-1)+`"`+(e<=1?` disabled`:``)+`>‹ 上一页</button><span class="tpg-nums">`+i.join(``)+`</span><button type="button" class="tpg-arr" data-errpage="`+(e+1)+`"`+(e>=t?` disabled`:``)+`>下一页 ›</button><span class="tpg-cnt">第 `+e+`/`+t+` 页 · 共 `+n+` 条</span>`}function G(e,n){let r=n.counts.total??n.total;if(!n.error&&r===0&&!n.active){e.errsSec.style.display=`none`;return}e.errsSec.style.display=``;let i=(e,t,r)=>`<button type="button" class="dsh-exec-tab`+(n.active===e?` act`:``)+`" data-errst="`+e+`">`+t+`<b class="c">`+r+`</b></button>`,a=i(``,`全部`,n.counts.total??0)+i(`open`,`待处理`,n.counts.open??0)+i(`processing`,`处理中`,n.counts.processing??0)+i(`resolved`,`已解决`,n.counts.resolved??0)+i(`ignored`,`已忽略`,n.counts.ignored??0),o=n.events.map((e,t)=>ke(e,t)).join(``),s=n.events.length===0?`<li class="empty"><span class="line">该状态下暂无错误事件</span></li>`:``,c=Math.max(1,Math.ceil(n.total/Math.max(1,n.pageSize))),l=n.total>n.pageSize?`<div class="dsh-exec-tkpg">`+Ae(n.page,c,n.total)+`</div>`:``,u=n.error?`<div class="dsh-exec-banner show">⚠ 错误事件加载失败：`+t(n.error)+` — 请检查 Agent OS :8080</div>`:``;e.errsBox.innerHTML=u+`<div class="dsh-exec-legend dsh-exec-legend2"><span class="dsh-exec-hint">按状态点击 Tabs 过滤 · 全部历史分页浏览 · <i class="dot ok"></i>待处理/处理中可处置 <i class="dot bad"></i>×N=同指纹累计次数（去重合并）· 点击 <b>#ID</b> 复制完整事件 ID</span></div><div class="dsh-exec-tabs">`+a+`</div><ol class="dsh-exec-errs">`+o+s+`</ol>`+l}function je(e,n){let r=n.blockedFlows??[];e.blockSec.style.display=r.length>0?``:`none`,r.length!==0&&(e.blockBox.innerHTML=r.map(e=>`<div class="dsh-exec-block"><b>`+t(e.checkpointName??e.checkpointId??`?`)+`</b><span class="tag bad">`+t(O[String(e.status??``)]??t(e.status??``))+`</span>`+(e.blocks&&e.blocks.length>0?`<span class="blocks">阻断: `+t(e.blocks.join(`, `))+`</span>`:``)+`</div>`).join(``))}function Me(e,n){let r=n.orphanedTasks??[];if(e.orphanedSec.style.display=``,r.length===0){e.orphanedBox.innerHTML=`<div class="dsh-exec-orphaned-empty">✓ 当前无僵尸任务（数据库中的任务均已正确加载到调度器）</div>`;return}e.orphanedBox.innerHTML=`<div class="dsh-exec-orphaned-list">`+r.map(e=>{let n=e.daysSinceLastRun??0,r=e.lastRunAt?S(e.lastRunAt):`从未执行`,i=e.enabled?`<span class="tag enabled">启用</span>`:`<span class="tag disabled">禁用</span>`;return`
      <div class="dsh-exec-orphaned-item" data-task-id="${e.id}">
        <div class="orphaned-header">
          <span class="task-name">⚠️ ${t(e.name??`?`)}</span>
          ${i}
        </div>
        <div class="orphaned-info">
          <span class="info-item">最后执行: ${t(r)}</span>
          <span class="info-item">距今: ${n}天</span>
          <span class="info-item reason">原因: ${t(e.reason??`?`)}</span>
        </div>
        <div class="orphaned-actions">
          <button type="button" class="dsh-exec-cleanup-btn" data-orphaned-id="${e.id}" title="从数据库删除此僵尸任务">清理</button>
        </div>
      </div>
    `}).join(``)+`</div>`}function Ne(e,t){he(e,t),_e(e,t),xe(e,t),U(e,t),je(e,t),Me(e,t)}function Pe(e){let t=e.prefix,n,r,i=()=>{r?.(),r=void 0,n!==void 0&&(n.remove(),n=void 0)},a=(e,n)=>{let r=document.createElement(`div`);r.className=t+`-toast `+(n?`ok`:`err`),r.textContent=e,document.body.appendChild(r),window.setTimeout(()=>{r.classList.add(`out`),window.setTimeout(()=>r.remove(),350)},4200)},o=async(t,n,r)=>{let i=e.current();console.log(`[solve-kit] postSolve`,{endpoint:e.endpoint,kind:t,toSession:r,from:i});try{let o=await fetch(e.endpoint,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({kind:t,task:t===`task`?n:void 0,err:t===`error`?n:void 0,from_session:i||void 0,to_session:r})}),s=await o.json().catch(()=>null);if(console.log(`[solve-kit] response`,s),s===null||s.success!==!0){a(`投递失败：`+String(s?.error??`HTTP `+o.status),!1);return}let c=s.data;if(a(c?.delivered===!0?`✓ `+String(c?.note??`已投递`):`⚠ `+String(c?.error??s.error??`投递失败`),c?.delivered===!0),c?.delivered===!0&&c.target?.sessionId)try{let e=window,t=e.__dshHldSessions??e.__dshExecSessions??e.__dshBbdSessions??e.__dshPmSessions??e.__dshHldCtx?.sessions??e.__dshExecCtx?.sessions??e.__dshBbdCtx?.sessions??e.__dshPmCtx?.sessions;t&&typeof t.open==`function`?(console.log(`[solve-kit] auto-opening target session:`,c.target.sessionId),t.open(c.target.sessionId)):console.warn(`[solve-kit] sessions service not available for auto-open`)}catch(e){console.warn(`[solve-kit] failed to auto-open session:`,e)}}catch(e){a(`请求异常：`+String(e instanceof Error?e.message:e),!1)}},s=e=>{let t=e.lastIndexOf(`session-`);return t>=0&&e.length>=t+16?`w-`+e.slice(t+8,t+16):e};return{toast:a,openPicker:(c,l,u)=>{console.log(`[solve-kit] openPicker`,{kind:l,identity:u});let d=e.resolveSnapshot(l,u);if(console.log(`[solve-kit] resolveSnapshot`,d),d===null){a(`⚠ 数据已刷新，请重试`,!1);return}i();let f=c.getBoundingClientRect();(async()=>{let t=null;try{let n=await e.online?.();Array.isArray(n)&&(t=new Set(n.map(String)))}catch{}let n=e.candidates();if(n.length===0&&t!==null&&t.size>0){let r=String(e.current()??``);n=[...t].map(e=>({sid:String(e),label:s(String(e)),current:String(e)===r})),console.warn(`[solve-kit] 会话候选为空，回退在线窗口清单合成候选`,n.length)}if(n.length===0){o(d.kind,d.snap);return}p(n,t,f)})();let p=(a,s,c)=>{let l=document.createElement(`div`);l.className=t+`-solvepop`;let u=document.createElement(`div`);u.className=t+`-solvepop-head`,u.textContent=`投递给窗口排查处置`+(s===null?``:`（● 当前 / ○ 在线 / ○离线）`),l.appendChild(u);let f=document.createElement(`div`);f.className=t+`-solvepop-list`;let p=(e,n)=>{let r=document.createElement(`button`);return r.type=`button`,r.className=t+`-solvepop-item`+(e.current?` cur`:``)+(n?``:` off`),r.textContent=(e.current?`● `:`○ `)+e.label+(n?``:`（离线）`),r.addEventListener(`click`,()=>{if(!n){if(!window.confirm(`窗口「`+e.label+`」不在线（agent 未加载），直接投递必失败。

确定改投到当前在线窗口处理吗？
（或先到该窗口发一条消息激活后再重试）`))return;i(),o(d.kind,d.snap);return}i(),o(d.kind,d.snap,e.sid)}),r},m=a.filter(e=>s===null||e.current||s.has(e.sid)),h=a.filter(e=>!(s===null||e.current||s.has(e.sid)));m.sort((e,t)=>Number(t.current)-Number(e.current));for(let e of m)f.appendChild(p(e,!0));if(h.length>0){let e=document.createElement(`div`);e.style.display=`none`;for(let t of h)e.appendChild(p(t,!1));let n=document.createElement(`button`);n.type=`button`,n.className=t+`-solvepop-cancel`;let r=e=>{n.textContent=(e?`▾ 收起离线窗口`:`▸ 显示离线/已归档窗口`)+`（`+h.length+`）`};r(!1),n.addEventListener(`click`,()=>{let t=e.style.display!==`none`;e.style.display=t?`none`:``,r(!t)}),f.appendChild(n),f.appendChild(e)}l.appendChild(f);let g=document.createElement(`button`);g.type=`button`,g.className=t+`-solvepop-cancel`,g.textContent=`取消`,g.addEventListener(`click`,i),l.appendChild(g);let _;try{_=typeof e.host==`function`?e.host():e.host}catch{_=void 0}(_??document.body).appendChild(l),n=l;let v=40+(m.length+ +(h.length>0))*30+32,y=c.bottom+6;y+v>window.innerHeight&&(y=Math.max(6,c.top-v-6)),l.style.position=`fixed`,l.style.left=Math.max(6,Math.min(c.left,Math.max(6,window.innerWidth-280)))+`px`,l.style.top=y+`px`;let b=e=>{let t=e.target;t!==null&&l.contains(t)||(document.removeEventListener(`click`,b,!0),r=void 0,i())};document.addEventListener(`click`,b,!0),r=()=>document.removeEventListener(`click`,b,!0)}},close:i}}let K=!1,q=!1;const J={total:0,open:0,processing:0,resolved:0,ignored:0};async function Y(e){try{let t=await fetch(`/dashboard/api/board/error-action`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify(e)}),n=await t.json().catch(()=>({}));return!t.ok&&n.success===void 0?{ok:!1,error:`HTTP `+t.status}:n.success===!1?{ok:!1,error:n.error??`操作失败`}:{ok:!0,message:n.data?.message??`已更新`}}catch(e){return{ok:!1,error:e instanceof Error?e.message:String(e)}}}async function Fe(e){try{if(typeof navigator<`u`&&navigator.clipboard?.writeText)return await navigator.clipboard.writeText(e),!0}catch{}try{let t=document.createElement(`textarea`);t.value=e,t.setAttribute(`readonly`,``),t.style.position=`fixed`,t.style.top=`-1000px`,t.style.opacity=`0`,document.body.appendChild(t),t.select();let n=document.execCommand(`copy`);return document.body.removeChild(t),n}catch{return!1}}function Ie(e){let t,n,r={events:[],total:0,page:1,pageSize:10,active:``,counts:{...J}},i=new Map,a=document.createElement(`div`);a.dataset.dshExecView=``,a.className=`dsh-exec-view`,e.appendChild(a),t=me(),a.appendChild(t.board);let o=a.querySelector(`[data-role="refresh"]`),s=()=>{p(),m({silent:!0})};o?.addEventListener(`click`,s);let c=e=>{let r=e.target;if(n===void 0||t===void 0)return;let i=r.closest(`.dsh-exec-solve[data-solve-task]`);if(i!==null&&i.dataset.solveTask!==void 0){v.openPicker(i,`task`,{name:i.dataset.solveTask});return}let a=r.closest(`.dsh-exec-tab[data-dom]`);if(a!==null){Ce(a.dataset.dom??`all`),U(t,n);return}let o=r.closest(`.dsh-exec-tkpg [data-tkpage]`);if(o!==null&&!o.disabled){we(Number(o.dataset.tkpage)),U(t,n);return}let s=r.closest(`.dsh-exec-tr[data-tk]`)?.dataset.tk;s!==void 0&&(Se(s),U(t,n))};t.tasksBox.addEventListener(`click`,c);let l=e=>{let a=e.target;if(t===void 0)return;let o=a.closest(`.evid[data-evcopy]`);if(o!==null){let e=o.dataset.evcopy??``;e!==``&&Fe(e).then(t=>v.toast(t?`✓ 已复制事件 ID：`+e:`⚠ 复制失败，请手动复制 ID：`+e,t));return}let s=a.closest(`.dsh-exec-tab[data-errst]`);if(s!==null){r={...r,active:s.dataset.errst??``,page:1},m();return}let c=a.closest(`.dsh-exec-tkpg [data-errpage]`);if(c!==null&&!c.disabled){let e=Number(c.dataset.errpage);!Number.isNaN(e)&&e>=1&&(r={...r,page:Math.trunc(e)},m());return}let l=a.closest(`.dsh-exec-solve[data-solve-err]`);if(l!==null&&l.dataset.solveErr!==void 0){let e=Number(l.dataset.solveErr),t=r.events[e];if(t?.id===void 0&&l.dataset.evid&&(t=r.events.find(e=>String(e.id)===String(l.dataset.evid))),t?.id===void 0)return;if(i.set(String(t.id),{row:{...t,fetchedAt:n?.fetchedAt??``},fetchedAt:n?.fetchedAt??``}),i.size>60){let e=i.keys().next().value;e!==void 0&&i.delete(e)}(async()=>{let n=await Y({id:t.id,action:`claim`,from_session:g()});if(!n.ok){v.toast(`⚠ 认领失败：`+(n.error??``));return}v.openPicker(l,`error`,{index:e,id:t.id}),m({silent:!0})})();return}let u=a.closest(`.dsh-exec-evact[data-evid][data-evact]`);if(u!==null){let e=u.dataset.evid,t=u.dataset.evact;if(e===void 0||t===void 0)return;let n;if(t===`resolve`||t===`ignore`){let e=t===`resolve`?`处置结论（≥10字）：根因 + 动作 + 证据
例：根因=Python3.13移除timeout参数；动作=thread_pool.py改cancel_futures；证据=pytest PASS`:`忽略理由（≥10字）：为何误报 / 无需处置`,r=window.prompt(e);if(r===null)return;if(n=r.trim(),[...n].length<10){v.toast(`⚠ 结论太短（≥10字），未提交`);return}}(async()=>{let r=await Y({id:e,action:t,from_session:g(),note:n});v.toast(r.ok?`✓ `+(r.message??`已更新`):`⚠ `+(r.error??`操作失败`)),r.ok&&m({silent:!0})})()}};t.errsBox.addEventListener(`click`,l);let u=e=>{let t=e.target.closest(`.dsh-exec-cleanup-btn[data-orphaned-id]`);if(t!==null&&t.dataset.orphanedId!==void 0){let e=t.dataset.orphanedId;if(!window.confirm(`确认清理僵尸任务 ID: ${e}？\n此操作将从数据库中永久删除该任务。`))return;(async()=>{try{let t=await fetch(`/dashboard/api/board/orphaned-task-cleanup`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({id:e})}),n=await t.json().catch(()=>({}));if(!t.ok||n.success===!1){v.toast(`⚠ 清理失败：`+(n.error??`HTTP `+t.status));return}v.toast(`✓ `+(n.data?.message??`僵尸任务已清理`)),p()}catch(e){v.toast(`⚠ 清理失败：`+(e instanceof Error?e.message:String(e)))}})()}};t.orphanedBox.addEventListener(`click`,u);let d=()=>{o?.removeEventListener(`click`,s),t?.tasksBox.removeEventListener(`click`,c),t?.errsBox.removeEventListener(`click`,l),t?.orphanedBox.removeEventListener(`click`,u)};p(!0),m();let f=window.setInterval(()=>{document.hidden||(p(),m({silent:!0}))},3e4);async function p(e=!1){if(!K){K=!0;try{let e=await fetch(`/dashboard/api/board`,{headers:{Accept:`application/json`}});if(!e.ok)throw Error(`HTTP `+e.status);let r=await e.json();if(!r.success||r.data===void 0)throw Error(r.error??`API 返回失败`);if(t===void 0)return;n=r.data,Ne(t,n),t.meta.textContent=`刷新于 `+new Date().toLocaleTimeString()+` · 数据 `+(r.data.fetchedAt??``),t.banner.classList.remove(`show`)}catch(e){if(t===void 0)return;t.banner.innerHTML=`⚠ 无法连接看板 API：`+String(e&&e.message?e.message:e)+` — 请检查 :13080 与插件状态`,t.banner.classList.add(`show`)}finally{K=!1}}}async function m(e){if(q)return;q=!0;let n=r;try{let e=new URLSearchParams;n.active&&e.set(`status`,n.active),e.set(`page`,String(n.page)),e.set(`pageSize`,String(n.pageSize));let i=await fetch(`/dashboard/api/board/error-events?`+e.toString(),{headers:{Accept:`application/json`}});if(!i.ok)throw Error(`HTTP `+i.status);let a=await i.json();if(!a.success||a.data===void 0)throw Error(a.error??`API 返回失败`);if(t===void 0)return;r={events:Array.isArray(a.data.events)?a.data.events:[],total:Number(a.data.total??n.total),page:Math.max(1,Number(a.data.page??n.page)),pageSize:n.pageSize,active:n.active,counts:{...J,...a.data.counts??{}},error:void 0},G(t,r)}catch(n){let i=String(n&&n.message?n.message:n);if(e?.silent||v.toast(`⚠ 错误事件加载失败：`+i),t===void 0)return;r={...r,error:i},G(t,r)}finally{q=!1}}let h=()=>{let e=window,t=e.__dshExecSessions;if(!t?.list)try{t=e.__dshExecCtx?.sessions,t?.list&&(e.__dshExecSessions=t)}catch{}let n=null;try{let t=e.__dshExecWorkspaces?.list?.getSnapshot?.()?.archivedSessionIds;Array.isArray(t)&&(n=new Set(t.map(String)))}catch{}let r=[];try{let e=t?.list?.getSnapshot?.();if(!e)return r;let i=String(e.current??``),a=Array.isArray(e.items)?e.items:Array.isArray(e.ids)?e.ids.map(t=>e.byId?.[t]).filter(Boolean):[];for(let e of a){let t=String(e?.id??e?.sessionId??``);!t||e.blank||n?.has(t)||e?.origin!==`subagent`&&r.push({sid:t,label:String(e.displayTitle??e.title??t),current:t===i})}r.length===0&&console.warn(`[dashboard-execution] 会话候选为空诊断`,{hasFac:!!t,hasList:!!t?.list,snapKeys:e?Object.keys(e):null,idsLen:Array.isArray(e?.ids)?e.ids.length:null,itemsLen:Array.isArray(e?.items)?e.items.length:null,byIdLen:e?.byId?Object.keys(e.byId).length:null,rowsLen:a.length,current:i||null,archivedLen:n?.size??null})}catch{}return r},g=()=>{try{return String(window.__dshExecSessions?.list?.getSnapshot?.()?.current??``)}catch{return``}},_=(e,t)=>{if(e===`task`){if(n===void 0)return null;let e=n.fetchedAt??``,r=(n.tasks??[]).find(e=>String(e.name)===t.name);return r?{kind:`task`,snap:{...r,fetchedAt:e}}:null}let a=n?.fetchedAt??``;if(t.id!==void 0){let e=i.get(String(t.id));if(e)return{kind:`error`,snap:e.row}}let o=r.events[Number(t.index??-1)];return o?{kind:`error`,snap:{...o,fetchedAt:a}}:null},v=Pe({endpoint:`/dashboard/api/board/solve`,prefix:`dsh-exec`,candidates:h,online:async()=>{try{let e=await(await fetch(`/dashboard/api/board/online-windows`)).json();return Array.isArray(e?.data?.online)?e.data.online.map(String):[]}catch{return[]}},current:g,resolveSnapshot:(e,t)=>_(e,t),host:()=>a});return()=>{window.clearInterval(f),d(),v.close(),a.remove()}}const X=`智能执行`,Z=`@pi-investment/dashboard-execution/footer-action.css`,Q=`dashboard-execution:open-board`;function Le(t){let{wide:n}=t,r=X;return(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-exec-foot wide`:`dsh-exec-foot rail`,title:r,"aria-label":r,onClick:()=>{console.log(`[dashboard-execution] footer action clicked — dispatching`,Q),window.dispatchEvent(new CustomEvent(Q,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-exec-foot-icon`,key:`i`},$),(0,e.createElement)(`span`,{className:`dsh-exec-foot-label`,key:`l`},r)]:(0,e.createElement)(`span`,{className:`dsh-exec-foot-icon`,key:`i`},$))}const $=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function Re(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${Z}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=Z,e.textContent=`
.dsh-exec-foot {
  display: flex; align-items: center; gap: 8px;
  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
  font: inherit; font-size: 13px; cursor: pointer;
  -webkit-appearance: none; appearance: none;
}
.dsh-exec-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-exec-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
.dsh-exec-foot.wide {
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border-radius: 8px; justify-content: flex-start; text-align: left;
}
.dsh-exec-foot.rail {
  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
  justify-content: center; padding: 0;
}
.dsh-exec-foot-icon { display: inline-flex; flex: none; }
.dsh-exec-foot.rail .dsh-exec-foot-label { display: none; }
.dsh-exec-foot-icon svg { width: 16px; height: 16px; }
`,document.head.appendChild(e)}function ze(){let e=`dsh-exec-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
.dsh-exec-entry {
  display: flex; align-items: center; gap: 8px; position: relative;
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border: none; border-radius: 8px; background: transparent;
  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
  cursor: pointer; text-align: left;
}
.dsh-exec-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-exec-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
.dsh-exec-entry svg { flex: none; }
/* sidebar.footer.action 列表默认按行排布——把整个 seat 容器改为纵向列，
   两个看板按钮即上下堆叠（wide 整宽 / rail 纵向图标） */
div[data-slot="sidebar.footer.action"] {
  display: flex !important; flex-direction: column; align-items: stretch; width: 100%; min-width: 0;
}
[data-sidebar-collapsed] [data-dsh-exec-entry],
[class*="_collapsed"] [data-dsh-exec-entry] {
  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
  justify-content: center; gap: 0; text-align: center;
}
[data-sidebar-collapsed] [data-dsh-exec-entry] .dsh-exec-entry-label,
[class*="_collapsed"] [data-dsh-exec-entry] .dsh-exec-entry-label { display: none; }
[data-sidebar-collapsed] [data-dsh-exec-entry] svg,
[class*="_collapsed"] [data-dsh-exec-entry] svg { width: 16px; height: 16px; }

/* 看板正文在右侧栏 tab 内常显（右栏自带显隐与折叠） */
.dsh-exec-view { display: none; }
.dsh-exec-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.dsh-exec-board { flex: 1; min-height: 0; overflow-y: auto; box-sizing: border-box; }

/* ================= 浅色监控主题（design page2，固定色板） ================= */
.dsh-exec-board {
  --panel:#fff; --line:#ebeef5; --border:#e4e7ed;
  --text:#303133; --body:#606266; --dim:#909399; --faint:#c0c4cc;
  --ok:#67c23a; --bad:#f56c6c; --late:#e6a23c; --wait:#909399; --unk:#a2a8b3;
  background:#f0f2f5; color:var(--body);
  font:13px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  padding:18px 22px 56px;
}
.dsh-exec-board * { box-sizing: border-box; }
.dsh-exec-wrap { max-width: 1560px; }

/* 顶栏 */
.dsh-exec-head { display:flex; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:16px; }
.dsh-exec-title { font-size:20px; font-weight:600; color:#1f2d3d; margin:0; letter-spacing:.3px; }
.dsh-exec-title small { color:var(--dim); font-size:12px; font-weight:400; margin-left:10px; }
.dsh-exec-meta { margin-left:auto; display:flex; align-items:center; gap:14px; color:var(--dim); font-size:12px; }
.dsh-exec-last { font-variant-numeric:tabular-nums; }
.dsh-exec-btn { background:var(--panel); color:var(--accent, #409eff); border:1px solid var(--accent, #409eff); border-radius:6px; padding:4px 14px; font-size:12px; cursor:pointer; }
.dsh-exec-btn:hover { background:#ecf5ff; }
.dsh-exec-btn:active { opacity:.8; }
.dsh-exec-banner { display:none; background:#fef0f0; border:1px solid #fde2e2; color:#f56c6c; padding:10px 16px; border-radius:8px; margin-bottom:14px; font-size:13px; }
.dsh-exec-banner.show { display:block; }

/* 区块卡 */
.dsh-exec-cardx { background:var(--panel); border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.05); margin-bottom:16px; overflow:hidden; }
.dsh-exec-cardx .hd { display:flex; align-items:baseline; justify-content:space-between; gap:12px; padding:13px 18px; border-bottom:1px solid #f0f0f0; flex-wrap:wrap; }
.dsh-exec-cardx .hd .t { font-size:15px; font-weight:600; color:var(--text); }
.dsh-exec-cardx .hd .more { font-size:12px; color:var(--dim); font-weight:400; }
.dsh-exec-cardx .bd { padding:14px 18px; }
.dsh-exec-empty { color:var(--faint); font-size:13px; padding:10px 0; }
/* 分类对账提示（2026-09-12）：字段未打通 / 未归类任务 / OS 并入对账 —— 显式可见，不静默 */
.dsh-exec-cover { display:flex; flex-wrap:wrap; gap:6px 14px; padding:6px 0 8px; font-size:12px; color:var(--faint); }
.dsh-exec-cover span { padding:2px 8px; border-radius:4px; background:var(--bg2); }
.dsh-exec-cover code { font-family:var(--mono, monospace); padding:0 3px; }

/* 执行总览：大数字健康条 + 服务 pills */
.dsh-exec-hb { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:12px; }
.hb-item { border-radius:10px; padding:12px 16px; text-align:center; background:#fafbfc; border:1px solid var(--line); }
.hb-item .v { font-size:30px; font-weight:700; color:var(--text); font-variant-numeric:tabular-nums; line-height:1.2; }
.hb-item .n { font-size:12px; color:var(--dim); margin-top:3px; }
.hb-item.ok { background:#f0f9eb; border-color:#e1f3d8; } .hb-item.ok .v { color:#67c23a; }
.hb-item.bad { background:#fef0f0; border-color:#fde2e2; } .hb-item.bad .v { color:#f56c6c; }
.hb-item.wait { background:#f4f4f5; border-color:#ebeef5; } .hb-item.wait .v { color:#909399; }
.dsh-exec-pills { display:flex; flex-wrap:wrap; gap:8px; }
.dsh-exec-pills .pill { display:inline-flex; align-items:center; gap:6px; font-size:12px; padding:4px 12px; border-radius:999px; background:#f4f4f5; color:var(--body); }
.dsh-exec-pills .pill.ok { background:#f0f9eb; color:#529b2e; }
.dsh-exec-pills .pill.warn { background:#fdf6ec; color:#e6a23c; }
.dsh-exec-pills .pill b { font-weight:500; }
.dsh-exec-pills .dot { width:8px; height:8px; border-radius:50%; background:var(--wait); }
.dsh-exec-pills .dot.ok { background:#67c23a; } .dsh-exec-pills .dot.bad { background:#f56c6c; }
.dsh-exec-pills .dot.deg { background:#e6a23c; } .dsh-exec-pills .dot.unk { background:#c0c4cc; }

/* 流水线带：ENGINE × AUTONOMY */
.dsh-exec-band { margin-bottom:16px; }
.dsh-exec-band:last-child { margin-bottom:0; }
.band-t { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.band-badge { font-size:10px; letter-spacing:1px; padding:2px 8px; border-radius:4px; font-weight:600; }
.band-badge.engine { background:#ecf5ff; color:#409eff; }
.band-badge.autonomy { background:#fdf6ec; color:#e6a23c; }
.band-t i { flex:1; height:1px; background:var(--line); }
.band-nodes { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:8px; }
.dsh-exec-band .node { background:#fff; border:1px solid var(--line); border-left:3px solid var(--wait); border-radius:8px; padding:9px 11px; min-width:0; }
.dsh-exec-band .node.st-ok { border-left-color:#67c23a; }
.dsh-exec-band .node.st-bad { border-left-color:#f56c6c; }
.dsh-exec-band .node.st-late, .dsh-exec-band .node.st-deg { border-left-color:#e6a23c; }
.dsh-exec-band .node .n-top { display:flex; align-items:center; gap:6px; }
.dsh-exec-band .node .n-top b { font-size:12px; color:var(--text); font-weight:600; }
.dsh-exec-band .node .n-top span { font-size:12.5px; color:var(--text); font-weight:500; margin-right:auto; }
.dsh-exec-band .node .n-top em { font-style:normal; font-size:11px; color:var(--dim); white-space:nowrap; }
.dsh-exec-band .node .dot { width:8px; height:8px; border-radius:50%; flex:none; background:var(--wait); }
.dsh-exec-band .node .dot.ok { background:#67c23a; } .dsh-exec-band .node .dot.bad { background:#f56c6c; }
.dsh-exec-band .node .dot.late, .dsh-exec-band .node .dot.deg { background:#e6a23c; }
.dsh-exec-band .node .dot.off, .dsh-exec-band .node .dot.unk { background:#c0c4cc; }
.dsh-exec-band .node .cps { list-style:none; margin:7px 0 0; padding:0; border-top:1px dashed var(--line); }
.dsh-exec-band .node .cps li { display:flex; align-items:center; gap:6px; font-size:11.5px; color:var(--body); padding-top:5px; }
.dsh-exec-band .node .cps li .dot { width:6px; height:6px; }
.dsh-exec-band .node .cps li em { font-style:normal; color:var(--faint); margin-left:auto; font-size:10.5px; white-space:nowrap; }
.dsh-exec-band .node .cps li.cp-empty { color:var(--faint); }
.dsh-exec-band .node .cps li time.cp-tm { flex:none; min-width:36px; text-align:center; font-size:10px; line-height:1.7; color:var(--faint); background:#f4f4f5; border-radius:3px; padding:0 4px; font-variant-numeric:tabular-nums; }

/* 今日时间轴：日执行 / 周执行 分组（2026-09-04） */
.dsh-exec-tlg + .dsh-exec-tlg { margin-top:16px; }
.dsh-exec-tlg .tlg-t { display:flex; align-items:baseline; gap:8px; margin-bottom:6px; }
.dsh-exec-tlg .tlg-t .t { font-size:12.5px; font-weight:600; color:var(--text); }
.dsh-exec-tlg .tlg-t .t::before { content:''; display:inline-block; width:8px; height:8px; border-radius:2px; margin-right:7px; background:#409eff; vertical-align:0; }
.dsh-exec-tlg + .dsh-exec-tlg .tlg-t .t::before { background:#e6a23c; }
.dsh-exec-tlg .tlg-t em { font-style:normal; font-size:11px; color:var(--faint); margin-left:auto; }
.dsh-exec-tlg .dsh-exec-tl-list { border:1px solid var(--line); border-radius:8px; padding:2px 12px; background:#fff; }
/* 业务线分组着色（2026-09-08：引擎蓝 / Autonomy 紫） */
.dsh-exec-tlg.t-engine .tlg-t .t::before { background:#409eff; }
.dsh-exec-tlg.t-autonomy .tlg-t .t::before { background:#9c6ade; }
/* 非双线（账户 / 其它）折叠组（2026-09-08：默认收起，展示条目计数） */
.dsh-exec-tld { margin-top:16px; border:1px dashed var(--line); border-radius:8px; background:#fbfcfe; }
.dsh-exec-tld + .dsh-exec-tld { margin-top:8px; }
.dsh-exec-tld summary { display:flex; align-items:center; gap:7px; list-style:none; cursor:pointer; padding:7px 12px; font-size:12px; color:var(--dim); user-select:none; }
.dsh-exec-tld summary::-webkit-details-marker { display:none; }
.dsh-exec-tld summary .caret { transition:transform .12s; color:var(--faint); font-size:9px; flex:none; }
.dsh-exec-tld[open] summary .caret { transform:rotate(90deg); }
.dsh-exec-tld summary b { font-weight:600; font-size:12.5px; color:var(--text); }
.dsh-exec-tld summary em { font-style:normal; font-size:11px; color:var(--faint); margin-left:auto; white-space:nowrap; }
.dsh-exec-tld .dsh-exec-tl-list { border:none; background:transparent; padding:0 6px 4px 10px; }

/* 时间轴 */
.dsh-exec-tl-list { position:relative; }
.dsh-exec-tl-list::before { content:''; position:absolute; left:106px; top:6px; bottom:6px; width:2px; background:var(--line); border-radius:1px; }
.tl-item { position:relative; display:flex; align-items:center; gap:12px; padding:8px 0; }
.tl-item .tl-tm { flex:none; width:72px; text-align:right; font-size:12px; color:var(--faint); font-variant-numeric:tabular-nums; }
.tl-item .tl-ic { flex:none; width:18px; text-align:center; font-size:13px; }
.tl-item .tl-bd { display:flex; align-items:baseline; gap:10px; min-width:0; flex:1; }
.tl-item .tl-nm { font-size:13px; color:var(--text); }
.tl-item .tl-st { flex:none; font-size:11px; padding:0 8px; border-radius:4px; line-height:1.8; }
.tl-item.ok .tl-st { background:#f0f9eb; color:#529b2e; }
.tl-item.bad .tl-st { background:#fef0f0; color:#f56c6c; }
.tl-item.wait .tl-st { background:#f4f4f5; color:#909399; }
.tl-item.unk .tl-st { background:#f4f4f5; color:#a2a8b3; }
.tl-item.off .tl-st { background:#f4f4f5; color:#a2a8b3; }
.tl-item.off .tl-nm { color:#909399; }
.tl-item.bad .tl-nm { color:#f56c6c; }
.tl-item.bad { background:#fff5f5; border-radius:8px; padding:8px 10px; margin:0 -10px; }
/* 徽标：调度来源 v2/os · 调用 agent dh/ts（时间轴行尾 + 任务表） */
.tl-item .tl-tags { margin-left:auto; display:inline-flex; align-items:center; gap:4px; flex:none; }
.exec-chip { display:inline-block; font:600 9.5px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; padding:0 4px; border-radius:3px; vertical-align:1px; white-space:nowrap; }
.exec-chip.src.v2 { background:#e8f1fd; color:#3370c9; }
.exec-chip.src.os { background:#fdf3e3; color:#d98c1f; }
.exec-chip.ag.dh { background:#f3ecfa; color:#8b5fc8; }
.exec-chip.ag.ts { background:#e0f4f6; color:#1498a8; }

/* 任务分组 */
.dsh-exec-domain { margin-bottom:14px; }
.dsh-exec-domain:last-child { margin-bottom:0; }
.dm-t { display:flex; align-items:baseline; gap:8px; margin-bottom:6px; }
.dm-t .t { font-size:13px; font-weight:600; color:var(--text); }
.dm-t em { font-style:normal; font-size:11px; color:var(--faint); }
.dm-rows { border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.tk-row { display:flex; align-items:center; gap:12px; padding:7px 12px; font-size:12.5px; }
.tk-row + .tk-row { border-top:1px solid var(--line); }
.tk-row:hover { background:#fafbfc; }
.tk-nm { color:var(--text); }
.tk-tg { flex:none; }
.tk-tm { margin-left:auto; color:var(--faint); font-size:11px; font-variant-numeric:tabular-nums; white-space:nowrap; }
.dsh-exec-domain .tag, .dsh-exec-block .tag { display:inline-block; padding:0 8px; border-radius:4px; font-size:11px; line-height:1.8; white-space:nowrap; }
.dsh-exec-domain .tag.ok, .dsh-exec-block .tag.ok { background:#f0f9eb; color:#529b2e; }
.dsh-exec-domain .tag.bad, .dsh-exec-block .tag.bad { background:#fef0f0; color:#f56c6c; }
.dsh-exec-domain .tag.wait, .dsh-exec-block .tag.wait { background:#f4f4f5; color:#909399; }
.dsh-exec-domain .tag.off { background:#f4f4f5; color:#909399; }


/* 调度任务：任务卡 tab 横排 + 点击详情（2026-09-04） */
.dsh-exec-tks { display:flex; flex-wrap:wrap; gap:10px; }
.dsh-exec-tk { appearance:none; display:flex; flex-direction:column; gap:3px; flex:0 0 auto; min-width:176px; max-width:272px;
  padding:8px 12px 7px; border:1px solid var(--line); border-radius:10px; background:#fff;
  font:inherit; color:var(--text); cursor:pointer; text-align:left; position:relative; overflow:hidden;
  transition:border-color .15s, box-shadow .15s, transform .1s; }
.dsh-exec-tk::before { content:''; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--wait); }
.dsh-exec-tk.st-ok::before { background:#67c23a; }
.dsh-exec-tk.st-bad::before { background:#f56c6c; }
.dsh-exec-tk.st-wait::before { background:#e6a23c; }
.dsh-exec-tk.st-off::before, .dsh-exec-tk.st-unk::before { background:#c0c4cc; }
.dsh-exec-tk:hover { border-color:#b3d8ff; box-shadow:0 2px 6px rgba(64,158,255,.14); }
.dsh-exec-tk.sel { border-color:#409eff; box-shadow:0 0 0 2px rgba(64,158,255,.16); background:#f7fbff; }
.dsh-exec-tk.sel .tk-name { color:#1d6fe0; }
.dsh-exec-tk .tk-top { display:flex; align-items:center; gap:6px; min-width:0; }
.dsh-exec-tk .tk-name { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:600; font-size:13px; color:var(--text); }
.dsh-exec-tk .tk-tag { flex:none; }
.dsh-exec-tk .tk-cap { color:var(--dim); font-size:11px; font-variant-numeric:tabular-nums; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.dk { width:8px; height:8px; border-radius:50%; flex:none; background:#909399; }
.dk.d0 { background:#409eff; } .dk.d1 { background:#67c23a; } .dk.d2 { background:#e6a23c; }
.dk.d3 { background:#9c6ade; } .dk.d4 { background:#26c6da; } .dk.d5 { background:#ff7a45; }
.dk.d6 { background:#00b578; } /* 自主例程（Agent OS 调 agent） */
.dk.dx { background:#a2a8b3; }
/* 业务线配色（2026-09-08：tab 圆点 / 时间轴折叠组 / 任务行线标 共用） */
.dk.l-engine { background:#409eff; } .dk.l-autonomy { background:#9c6ade; }
.dk.l-account { background:#26c6da; } .dk.l-other { background:#a2a8b3; }
.dsh-exec-legend { display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding:0 0 10px; font-size:12px; color:var(--dim); }
.dsh-exec-legend .lg { display:inline-flex; align-items:center; gap:5px; }
.dsh-exec-legend .lg b { color:var(--text); font-weight:600; font-variant-numeric:tabular-nums; }
.dsh-exec-hint { margin-left:auto; color:var(--faint); font-size:11px; display:inline-flex; align-items:center; gap:5px; flex-wrap:wrap; }
.dsh-exec-hint .dot { width:7px; height:7px; border-radius:50%; display:inline-block; }
.dsh-exec-hint .dot.ok { background:#67c23a; } .dsh-exec-hint .dot.bad { background:#f56c6c; }
.dsh-exec-hint .dot.wait { background:#e6a23c; } .dsh-exec-hint .dot.off { background:#c0c4cc; }
.dsh-exec-tkdetail { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px 22px; margin-top:12px;
  background:#fafbfc; border:1px solid var(--line); border-left:3px solid #409eff; border-radius:10px; padding:11px 16px; }
.dsh-exec-tkdetail .tkd-i { min-width:0; }
.dsh-exec-tkdetail .tkd-i b { display:block; font-weight:600; font-size:11px; color:var(--faint); margin-bottom:1px; }
.dsh-exec-tkdetail .tkd-i span { font-size:12.5px; color:var(--text); word-break:break-all; }
.dsh-exec-tkdetail .tkd-code { font-style:normal; color:var(--faint); font-size:11px; margin-left:6px; }
.dsh-exec-tkdetail .tkd-err { grid-column:1 / -1; }
.dsh-exec-tkdetail .tkd-err span { color:#f56c6c; }
.dsh-exec-tkdetail .tag { display:inline-block; padding:0 8px; border-radius:4px; font-size:11px; line-height:1.8; }


/* 调度任务：分类 tab（pill，带计数）+ 任务表格（2026-09-04 v2 · 对齐设计稿定时任务表） */
.dsh-exec-tabs { display:flex; flex-wrap:wrap; gap:8px; align-items:center; padding:0 0 12px; }
.dsh-exec-tab { appearance:none; display:inline-flex; align-items:center; gap:5px; border:1px solid var(--line); background:#fff;
  color:var(--body); font:inherit; font-size:12.5px; padding:4px 13px; border-radius:999px; cursor:pointer; transition:all .15s; }
.dsh-exec-tab:hover { border-color:#b3d8ff; color:#1d6fe0; background:#f7fbff; }
.dsh-exec-tab.act { background:#409eff; border-color:#409eff; color:#fff; font-weight:500; }
.dsh-exec-tab .c { font-weight:600; opacity:.8; font-variant-numeric:tabular-nums; }
.dsh-exec-tab .dk { width:7px; height:7px; flex:none; }
.dsh-exec-legend2 { padding:0 0 2px; }
.dsh-exec-tbwrap { overflow-x:auto; border:1px solid var(--line); border-radius:8px; }
.dsh-exec-tb { width:100%; border-collapse:collapse; font-size:12.5px; background:#fff; }
.dsh-exec-tb th { text-align:left; color:var(--dim); font-weight:500; font-size:11.5px; padding:7px 12px; border-bottom:1px solid var(--line); background:#fafbfc; white-space:nowrap; }
.dsh-exec-tb td { padding:7px 12px; border-bottom:1px solid #f5f5f5; color:var(--body); vertical-align:middle; }
.dsh-exec-tb tbody tr:last-child td { border-bottom:none; }
.dsh-exec-tb tbody tr { cursor:pointer; }
.dsh-exec-tb tbody tr:hover { background:#f7fbff; }
.dsh-exec-tb tbody tr.sel { background:#ecf5ff; }
.dsh-exec-tb tbody tr.sel td { color:var(--text); }
.dsh-exec-tb tr.empty { cursor:default; text-align:center; color:var(--faint); }
.dsh-exec-tb .nm .ln-hd { display:inline-flex; align-items:center; gap:5px; }
.dsh-exec-tb .nm .ln-hd .dk { width:7px; height:7px; }
.dsh-exec-tb .nm .zh { color:var(--text); font-weight:500; }
.dsh-exec-tb .nm .code { display:block; color:var(--faint); font-size:10.5px; margin-top:1px; }
.dsh-exec-tb .cr { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11.5px; color:var(--dim); white-space:nowrap; }
.dsh-exec-tb .tag { display:inline-block; padding:0 8px; border-radius:4px; font-size:11px; line-height:1.8; white-space:nowrap; }
.dsh-exec-tb .tag.ok { background:#f0f9eb; color:#529b2e; }
.dsh-exec-tb .tag.bad { background:#fef0f0; color:#f56c6c; }
.dsh-exec-tb .tag.wait { background:#f4f4f5; color:#909399; }
.dsh-exec-tb .tag.off { background:#f4f4f5; color:#a2a8b3; }
.dsh-exec-tb .ls { font-style:normal; font-size:10.5px; margin-left:5px; color:var(--dim); }
.dsh-exec-tb .ls.ok { color:#67c23a; } .dsh-exec-tb .ls.bad { color:#f56c6c; }
.dsh-exec-tb .ls.wait { color:#e6a23c; } .dsh-exec-tb .ls.unk { color:var(--faint); }
.dsh-exec-tb .tm, .dsh-exec-tb .nx, .dsh-exec-tb .td { white-space:nowrap; font-variant-numeric:tabular-nums; }
.dsh-exec-tb .st { white-space:nowrap; }
.dsh-exec-tb .st .exec-chip { margin-left:5px; }
.dsh-exec-tb .tm, .dsh-exec-tb .nx { color:var(--dim); font-size:12px; }
.dsh-exec-tb .td { color:var(--body); font-size:12px; }

/* 调度任务：一体卡片 + 表底分页条（2026-09-05 v2 · 观感对齐 holdings「历史交易」分页） */
.dsh-exec-tkcard { border:1px solid var(--line); border-radius:8px; background:#fff; overflow:hidden; }
.dsh-exec-tkcard .dsh-exec-tbwrap { border:none; border-radius:0; }
.dsh-exec-tkpg { display:flex; align-items:center; gap:8px; padding:9px 14px; border-top:1px solid #ebeef5; flex-wrap:wrap; }
.dsh-exec-tkpg .tpg-arr, .dsh-exec-tkpg .tpg-num { min-width:26px; height:24px; padding:0 9px; border:1px solid #dcdfe6;
  border-radius:4px; background:#fff; color:#606266; font-size:12px; line-height:22px; cursor:pointer; font-family:inherit; }
.dsh-exec-tkpg .tpg-arr:hover:not(:disabled), .dsh-exec-tkpg .tpg-num:hover { border-color:#409eff; color:#409eff; }
.dsh-exec-tkpg .tpg-arr:disabled { color:#c0c4cc; background:#f5f7fa; cursor:not-allowed; }
.dsh-exec-tkpg .tpg-num.act { background:#409eff; border-color:#409eff; color:#fff; }
.dsh-exec-tkpg .tpg-nums { display:inline-flex; gap:4px; align-items:center; }
.dsh-exec-tkpg .tpg-gap { padding:0 2px; color:#c0c4cc; }
.dsh-exec-tkpg .tpg-cnt { margin-left:auto; font-size:12px; color:#909399; white-space:nowrap; font-variant-numeric:tabular-nums; }

/* 错误事件 / 阻断 */
.dsh-exec-errs { list-style:none; margin:0; padding:0; }
.dsh-exec-errs li { display:flex; gap:10px; align-items:baseline; padding:7px 0; font-size:12px; border-bottom:1px dashed var(--line); color:var(--body); }
.dsh-exec-errs li:last-child { border-bottom:none; }
.dsh-exec-errs li.empty { color:var(--faint); font-style:italic; justify-content:center; padding:10px 0; }
.dsh-exec-errs li .src { flex:none; border-radius:4px; padding:0 6px; font-size:10.5px; color:#fff; }
.dsh-exec-errs .src.v2 { background:#e6a23c; } .dsh-exec-errs .src.os { background:#409eff; } .dsh-exec-errs .src.dsh { background:#909399; }
.dsh-exec-errs li time { flex:none; color:var(--faint); font-size:11px; font-variant-numeric:tabular-nums; }
.dsh-exec-errs li .line { flex:1 1 auto; color:var(--dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
/* 状态机徽标（error_events 去重事件） */
.dsh-exec-errs li .evst { flex:none; border-radius:3px; padding:0 5px; font-size:10px; line-height:1.7; font-weight:600; }
.dsh-exec-errs li .evst.st-open { background:#fef0f0; color:#f56c6c; border:1px solid #fbc4c4; }
.dsh-exec-errs li .evst.st-processing { background:#ecf5ff; color:#409eff; border:1px solid #b3d8ff; }
.dsh-exec-errs li .evst.st-resolved { background:#f0f9eb; color:#67c23a; border:1px solid #c2e7b0; }
.dsh-exec-errs li .evst.st-ignored { background:#f4f4f5; color:#909399; border:1px solid #d3d4d6; }
/* 事件 ID 徽标：短 ID 可复制（2026-09-10，用户反馈列表缺 ID 无法指认具体事件） */
.dsh-exec-errs li .evid { flex:none; border:1px solid #dcdfe6; background:#fafafa; color:#909399; border-radius:3px;
  padding:0 5px; font-size:10.5px; line-height:1.7; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; cursor:pointer; }
.dsh-exec-errs li .evid:hover { color:#409eff; border-color:#c6e2ff; background:#ecf5ff; }
.dsh-exec-errs li .evid.none { cursor:default; color:#c0c4cc; }
.dsh-exec-errs li .occ { flex:none; color:#f56c6c; font-size:10.5px; font-weight:700; font-variant-numeric:tabular-nums; }
.dsh-exec-errs li .asg { flex:none; color:#9254de; font-size:10.5px; background:#f5f0ff; border-radius:3px; padding:0 5px; white-space:nowrap; }
/* P2 僵尸标记（2026-10-21, w-6224baac）：处理中但无责任人——红底警示 + 认领按钮 */
.dsh-exec-errs li .zombie { flex:none; color:#c45656; font-size:10.5px; font-weight:600; background:#fef0f0; border:1px solid #fbc4c4; border-radius:3px; padding:0 5px; white-space:nowrap; cursor:help; }
.dsh-exec-errs li .dsh-exec-claim { color:#c45656; border-color:#fbc4c4; }
.dsh-exec-errs li .dsh-exec-claim:hover { color:#fff; background:#f56c6c; border-color:#f56c6c; }
.dsh-exec-errs li .note { flex:none; color:#3f7f3f; font-size:10.5px; background:#f0f9eb; border-radius:3px; padding:0 5px; white-space:nowrap; max-width:260px; overflow:hidden; text-overflow:ellipsis; cursor:help; }
.dsh-exec-errs li .op { margin-left:auto; display:inline-flex; gap:6px; align-items:center; flex:none; }
.dsh-exec-errs li .op .dsh-exec-solve { margin-left:0; }
.dsh-exec-evact { flex:none; border:1px solid #dcdfe6; background:#fff; color:#606266; border-radius:5px; padding:1px 8px; font-size:11px; line-height:1.6; cursor:pointer; white-space:nowrap; vertical-align:middle; }
.dsh-exec-evact:hover { color:#409eff; border-color:#c6e2ff; background:#ecf5ff; }
.dsh-exec-block { display:flex; align-items:center; gap:10px; padding:8px 0; font-size:12.5px; }
.dsh-exec-block b { color:var(--text); font-weight:500; }
.dsh-exec-block .blocks { color:var(--faint); font-size:11.5px; }

/* ================= 我来解决（solve 投递） ================= */
/* 按钮：失败任务行「处理」列 + 错误事件条 */
.dsh-exec-solve {
  flex:none; border:1px solid #c6e2ff; background:#ecf5ff; color:#409eff;
  border-radius:5px; padding:2px 9px; font-size:11.5px; line-height:1.7;
  cursor:pointer; white-space:nowrap; vertical-align:middle;
}
.dsh-exec-solve:hover { background:#d9ecff; border-color:#79bbff; }
.dsh-exec-solve:active { background:#c6e2ff; }
.dsh-exec-tb td.op { text-align:center; white-space:nowrap; }
.dsh-exec-errs li .dsh-exec-solve { align-self:center; margin-left:auto; }
/* 选择器浮层：锚点下弹出的窗口列表 */
.dsh-exec-solvepop {
  position:fixed; z-index:9999; min-width:232px; max-width:300px;
  background:var(--panel,#fff); border:1px solid var(--border,#e4e7ed);
  border-radius:8px; box-shadow:0 6px 22px rgba(0,0,0,.16);
  padding:6px; font-size:12.5px; color:var(--body,#606266);
}
.dsh-exec-solvepop-head {
  padding:4px 8px 7px; color:var(--text,#303133); font-weight:600; font-size:12px;
  border-bottom:1px solid var(--line,#ebeef5); margin-bottom:4px;
}
.dsh-exec-solvepop-list { display:flex; flex-direction:column; max-height:264px; overflow-y:auto; }
.dsh-exec-solvepop-item {
  border:none; background:transparent; text-align:left; padding:5px 8px;
  border-radius:5px; cursor:pointer; color:var(--body,#606266); font:inherit; font-size:12.5px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.dsh-exec-solvepop-item:hover { background:var(--hover,rgba(128,128,128,.12)); }
.dsh-exec-solvepop-item.cur { color:#409eff; font-weight:600; }
.dsh-exec-solvepop-cancel {
  width:100%; margin-top:4px; border:none; background:transparent; color:var(--dim,#909399);
  font:inherit; font-size:12px; padding:4px; cursor:pointer; border-top:1px solid var(--line,#ebeef5);
}
.dsh-exec-solvepop-cancel:hover { color:var(--text,#303133); }
/* toast：投递结果飘字 */
.dsh-exec-toast {
  position:fixed; left:50%; bottom:54px; transform:translateX(-50%);
  z-index:10000; max-width:70vw; background:#303133; color:#fff;
  border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6;
  box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s;
}
.dsh-exec-toast.ok { background:#529b2e; }
.dsh-exec-toast.err { background:#e64545; }
.dsh-exec-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }

/* Orphaned tasks (僵尸任务) */
.dsh-exec-orphaned-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dsh-exec-orphaned-item {
  padding: 12px;
  border: 1px solid #ff6b6b33;
  border-radius: 6px;
  background: #ff6b6b11;
}

.dsh-exec-orphaned-item .orphaned-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dsh-exec-orphaned-item .task-name {
  font-weight: 500;
  color: #ff6b6b;
}

.dsh-exec-orphaned-item .tag {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
}

.dsh-exec-orphaned-item .tag.enabled {
  background: #ffc10733;
  color: #ffc107;
}

.dsh-exec-orphaned-item .tag.disabled {
  background: #9e9e9e33;
  color: #9e9e9e;
}

.dsh-exec-orphaned-item .orphaned-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}

.dsh-exec-orphaned-item .orphaned-info .reason {
  flex: 1 1 100%;
  color: #ff6b6b;
}

.dsh-exec-orphaned-item .orphaned-actions {
  display: flex;
  justify-content: flex-end;
}

.dsh-exec-cleanup-btn {
  padding: 4px 12px;
  border: 1px solid #ff6b6b;
  border-radius: 4px;
  background: white;
  color: #ff6b6b;
  cursor: pointer;
  font-size: 13px;
}

.dsh-exec-cleanup-btn:hover {
  background: #ff6b6b;
  color: white;
}


.dsh-exec-orphaned-empty {
  padding: 24px;
  text-align: center;
  color: #28a745;
  font-size: 14px;
  background: #28a74511;
  border-radius: 6px;
}
`,(document.head??document.documentElement).appendChild(t)}const Be=[`slots`,`sessions`,`workspaces`,`sidebarRight`,`sidebarRightTabs`];function Ve(e){try{window.__dshExecCtx=e,window.__dshExecSessions=e?.sessions,window.__dshExecWorkspaces=e?.workspaces}catch{}try{Re(),ze(),o(`dsh-exec`),window.__dshExecClient?.dispose();let t=p(e,{id:`@pi-investment/dashboard-execution`,kind:`dashboard-execution`,title:`智能执行`,mount:e=>Ie(e)}),n=e=>{let n=e.detail?.open;if(console.log(`[dashboard-execution] open-board event`,{open:n},`active:`,t.isActive()),n===!0){t.open()||s(`请先打开一个会话 —— 右侧栏需要有会话才能停靠看板`,!1,`dsh-exec`);return}if(!t.isActive()&&!t.open()){s(`请先打开一个会话 —— 右侧栏需要有会话才能停靠看板`,!1,`dsh-exec`);return}t.isActive()&&t.close()};window.addEventListener(Q,n),window.__dshExecClient={dispose:()=>{window.removeEventListener(Q,n),t.dispose()}};let r=e.slots;r?r.inject(`sidebar.footer.action`,()=>r.register({name:`sidebar.footer.action`,id:`dashboard-execution`,order:100,label:X},Le)):console.warn(`[dashboard-execution] ctx.slots unavailable (inject missing "slots")`)}catch(e){console.error(`[dashboard-execution] client half failed to start:`,e)}}exports.apply=Ve,exports.inject=Be,exports.name=`@pi-investment/dashboard-execution/client`;