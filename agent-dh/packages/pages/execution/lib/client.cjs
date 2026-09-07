Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");const t=`data-dsh-exec-active`,n=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`],r=`dsh-panel-activate`;function i(e){return e==null?``:String(e).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`)}function a(e){if(!e)return`—`;let t=String(e).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);if(!t)return i(e).slice(0,5);let n=new Date,r=e=>(e<10?`0`:``)+e,a=n.getFullYear()+`-`+r(n.getMonth()+1)+`-`+r(n.getDate()),o=t[4]+`:`+t[5];return(t[1]+`-`+t[2]+`-`+t[3]===a?``:t[2]+`-`+t[3]+` `)+o}function o(e){let t=String(e??``).match(/^(\d{2}):(\d{2})/);return t?Number(t[1])*60+Number(t[2]):9999}const s=[`周日`,`周一`,`周二`,`周三`,`周四`,`周五`,`周六`];function c(e){let t=String(e??``).trim(),n=t.split(/\s+/);if(n.length!==5)return t||`—`;let r=n[0],i=n[1],a=n[2],o=n[3],c=n[4],u=e=>/^\d+$/.test(e)?Number(e):null;if(i===`*`||i===`?`)return r===`0`||r===`*`?`每小时`:t;let d=u(i),f=r===`*`||r===`?`?0:u(r);if(d===null||f===null||d>23||f>59)return t;let p=String(d).padStart(2,`0`)+`:`+String(f).padStart(2,`0`),m=u(a),h=o!==`*`&&o!==`?`?u(o):null;if(m!==null)return(h===null?`每月 `+m+` 日`:`每年 `+h+` 月 `+m+` 日`)+` `+p;if(a!==`*`&&a!==`?`&&a!==`L`)return t;if(a===`L`)return`每月最后一日 `+p;let g=l(c);if(g===null)return t;let _;return _=g.length===7?`每日`:g.length===5&&g.every(e=>e>=1&&e<=5)?`工作日`:`每`+g.map(e=>s[e]).join(`、`),h!==null&&(_+=`（`+h+` 月）`),_+` `+p}function l(e){if(e===`*`||e===`?`){let e=[];for(let t=0;t<7;t++)e.push(t);return e}let t=[];for(let n of e.split(`,`)){let e=/^(\d+)(?:-(\d+))?$/.exec(n.trim());if(!e)return null;let r=Number(e[1])%7,i=e[2]?Number(e[2])%7:r;if(i<r)return null;for(let e=r;e<=i;e++)t.push(e)}return[...new Set(t)].sort((e,t)=>e-t)}function u(e,t){let n=String(e??``).trim();return n.length<=t?n:n.slice(0,t)+`…`}const d={success:`成功`,failed:`失败`,pending:`待执行`,skipped:`已跳过`,off_day:`非执行日`,unknown:`未知`},f={success:`✅`,failed:`❌`,pending:`⏳`,skipped:`⏭️`,off_day:`⏸`,unknown:`❔`},p={success:`ok`,failed:`bad`,pending:`wait`,skipped:`wait`,off_day:`off`,unknown:`unk`},m={confirmed:`已确认`,pending:`等待`,off_day:`非执行日`,failed:`失败`,late:`晚点`,degraded:`降级`,unknown:`未知`},h={confirmed:`ok`,pending:`wait`,off_day:`off`,failed:`bad`,late:`late`,degraded:`deg`,unknown:`unk`},g={ok:`正常`,degraded:`降级`,failed:`故障`,unknown:`未知`},_={ok:`ok`,degraded:`deg`,failed:`bad`,unknown:`unk`},v={"quantsys-v2":`量化后端 quantsys-v2`,"agent-os":`Agent OS`,postgres:`数据库 PostgreSQL`,"agent-dh":`Agent-DH 宿主`},y={market_daily_snapshot:`每日市场快照`,chan_scan_daily:`产业链链扫`,"chan-scan-daily":`产业链链扫`,v13_risk_check:`风控熔断检查`,"v13-risk-check":`风控熔断检查`,daily_trade_verify:`交易对账`,signal_perf_backfill_daily:`信号表现回填`,"signal-perf-backfill-daily":`信号表现回填`,v13_weekly_report:`每周报告`,"v13-weekly-report":`每周报告(v13)`,market_style_update:`市场风格更新`,"market-style-update":`市场风格更新`,v13_simulation_trading:`模拟交易执行`,"v13-simulation-trading":`模拟交易执行`,v13_verification:`策略验证裁决`,"v13-verification":`策略验证裁决`,pre_market_scan:`盘前扫描`,"pre-market-scan":`盘前扫描`,weekly_strategy_discovery:`周度策略发现`,"weekly-strategy-discovery":`周度策略发现`,daily_strategy_validation:`策略日验证`,"daily-strategy-validation":`策略日验证`,daily_pool_refresh:`股票池刷新`,"daily-pool-refresh":`股票池刷新`,fund_flow_update:`资金流数据更新`,chan_knowledge_distill_weekly:`知识蒸馏(周)`,"chan-knowledge-distill-weekly":`知识蒸馏(周)`,每日数据更新:`每日数据更新`,每日数据质量检查:`每日数据质量检查`,每周财务数据更新:`每周财务数据更新`,每日财报时效性检查:`每日财报时效性检查`,每日信号生成:`每日信号生成`,每日信号执行:`每日信号执行`,每周报告生成:`每周报告生成`,"pre-market-routine":`盘前例程`,"afternoon-open-check-live":`午后开盘检查`,"data-quality-monitor-daily":`数据质量监控`,"event-calendar-check":`事件日历检查`,"m4-circuit-breaker-live":`熔断回路检查`,"post-market-routine-live":`盘后例程`,"evolution-distill-daily":`进化蒸馏`,"evolution-gate-adjudicate":`进化裁决`,"evolution-weekly-variant":`进化变体`,"meta-learning-weekly":`元学习`,"weekly-report-m6":`学习飞轮周报`,"geer-take-profit-0901":`歌尔止盈观察`,"v14-simulation-trading":`模拟交易执行(v14)`,"agent-brain-morning-analysis":`晨间账户分析`,"agent-brain-realtime-check":`账户实时检查`,"agent-brain-daily-review":`账户日终复盘`,"agent-brain-daily-audit":`账户每日审计`,"agent-brain-weekly-roi":`账户周度ROI`,"agent-brain-weekly-evolution":`账户周度进化`,"agent-brain-weekly-distill":`账户周度蒸馏`,market_perception_daily:`市场感知`,signal_generate_sell:`卖出信号生成`,v2_health_check:`信号源健康检查`,"board-3341a342-verify-daily-review":`执行看板核验`};function b(e){let t=String(e??``);return y[t]??t}const x=[{key:`engine`,zh:`盈利引擎线`},{key:`autonomy`,zh:`Autonomy 线`},{key:`account`,zh:`账户定时任务`},{key:`other`,zh:`临时/核验/其他`}],S={engine:`盈利引擎线`,autonomy:`Autonomy 线`,account:`账户定时任务`,other:`临时/核验/其他`},ee=new Set(`每日数据更新.每日数据质量检查.每日财报时效性检查.每周财务数据更新.market_daily_snapshot.chan-scan-daily.chan_scan_daily.market-style-update.market_style_update.fund_flow_update.market_perception_daily.daily-pool-refresh.daily_pool_refresh.pre-market-scan.pre_market_scan.每日信号生成.每日信号执行.signal-perf-backfill-daily.signal_perf_backfill_daily.signal_generate_sell.v13-risk-check.v13_risk_check.daily_trade_verify.每日模型重训.pre-market-routine.afternoon-open-check-live.m4-circuit-breaker-live.post-market-routine-live.data-quality-monitor-daily.event-calendar-check`.split(`.`)),C=new Set([`daily-strategy-validation`,`daily_strategy_validation`,`v13-verification`,`v13_verification`,`weekly-strategy-discovery`,`weekly_strategy_discovery`,`chan-knowledge-distill-weekly`,`chan_knowledge_distill_weekly`,`v13-weekly-report`,`v13_weekly_report`,`每周报告生成`,`evolution-distill-daily`,`evolution-gate-adjudicate`,`evolution-weekly-variant`,`meta-learning-weekly`,`weekly-report-m6`,`weekly_evolution`,`weekly_memory_distill`,`daily_ai_review`,`daily_recall_audit`,`weekly_tool_roi_review`]),w=new Set([`v13-simulation-trading`,`v13_simulation_trading`,`v14-simulation-trading`]);function T(e){let t=String(e??``);return ee.has(t)?`engine`:C.has(t)?`autonomy`:w.has(t)||t.startsWith(`agent-brain-`)?`account`:(t.startsWith(`board-`)||t.startsWith(`geer-`),`other`)}function E(e){let t=T(String(e??``));return t===`engine`||t===`autonomy`}const D=[{code:`M0`,zh:`数据地基`},{code:`M1`,zh:`市场感知`},{code:`M2`,zh:`股票池`},{code:`M3`,zh:`信号生成`},{code:`M4`,zh:`风控止损`},{code:`M5`,zh:`交易对账`},{code:`M6`,zh:`经验进化`}],te=[{code:`L1`,zh:`策略验证`},{code:`L2`,zh:`经验蒸馏`},{code:`L3`,zh:`验证门裁决`},{code:`L4`,zh:`周报进化`}],O={failed:5,late:4,degraded:3,pending:2,off_day:1,unknown:0,confirmed:0};function ne(e){if(e.length===0)return{status:`unknown`,label:`暂无检查点`};let t=`confirmed`;for(let n of e){let e=String(n.status??`unknown`);(O[e]??0)>(O[t]??0)&&(t=e)}return{status:t,label:m[t]??t}}function k(){let e=document.createElement(`div`);e.className=`dsh-exec-board`;let t=e=>{let t=document.createElement(`div`);return t.innerHTML=e,t.firstElementChild},n=(e,n,r,a=`bd`)=>t(`<section class="dsh-exec-cardx"><div class="hd"><span class="t">`+i(e)+`</span><span class="more">`+i(n)+`</span></div><div class="`+a+`" data-role="`+r+`"></div></section>`),r=document.createElement(`div`);r.className=`dsh-exec-wrap`;let a=t(`<div class="dsh-exec-head"><h1 class="dsh-exec-title">双线执行确认看板<small>只读监控 · 运行与操作由 agent 自动完成</small></h1><div class="dsh-exec-meta"><span class="dsh-exec-last" data-role="lastFetch">—</span><button type="button" class="dsh-exec-btn" data-role="refresh">↻ 刷新</button></div></div>`),o=t(`<div class="dsh-exec-banner" data-role="banner"></div>`),s=n(`今日执行总览`,`双线口径（盈利引擎 + Autonomy）· 来自当日 cron 计划与运行结果`,`healthBox`),c=n(`执行流水线`,`ENGINE M0–M6 × AUTONOMY L1–L4 检查点状态`,`flowBox`),l=n(`今日时间轴`,`按业务线分组：盈利引擎 / Autonomy 展开 · 账户与其它折叠 · 徽标 v2/os=调度来源 dh/ts=调用 agent · 按计划时刻排序`,`timelineBox`),u=n(`调度任务`,`按业务线分类切换（盈利引擎 / Autonomy / 账户定时 / 临时核验）· 徽标 v2/os=调度来源 dh/ts=调用 agent · 点击任务行查看失败原因`,`tasksBox`),d=n(`错误事件`,`近 10 条日志异常（系统侧）`,`errsBox`);d.style.display=`none`;let f=n(`流水线阻断`,`failed/late 且声明阻断下游`,`blockBox`);f.style.display=`none`,r.append(a,o,s,c,l,u,d,f),e.appendChild(r);let p=t=>e.querySelector(t);return{board:e,meta:p(`[data-role="lastFetch"]`),banner:o,healthBox:p(`[data-role="healthBox"]`),flowBox:p(`[data-role="flowBox"]`),timelineBox:p(`[data-role="timelineBox"]`),tasksBox:p(`[data-role="tasksBox"]`),errsSec:d,errsBox:p(`[data-role="errsBox"]`),blockSec:f,blockBox:p(`[data-role="blockBox"]`)}}function A(e,t){let n=(t.timeline??[]).filter(e=>e.status!==`off_day`&&E(e.taskName)),r=n.length,a=0,o=0;for(let e of n)e.status===`success`?a++:e.status===`failed`&&o++;let s=Math.max(0,r-a-o),c=(e,t,n)=>`<div class="hb-item `+n+`"><div class="v">`+e+`</div><div class="n">`+t+`</div></div>`,l=`<div class="dsh-exec-hb">`+c(String(r),`今日计划任务`,`t`)+c(String(a),`✅ 已完成`,`ok`)+c(String(o),`❌ 失败`,o>0?`bad`:`ok`)+c(String(s),`⏳ 待执行`,`wait`)+`</div>`,u=t.health??[];u.length>0&&(l+=`<div class="dsh-exec-pills">`+u.map(e=>{let t=String(e.status??`unknown`);return`<span class="pill `+(t===`ok`?`ok`:`warn`)+`" title="`+i(e.error??``)+`"><i class="dot `+(_[t]??`unk`)+`"></i>`+i(v[e.name??``]??e.name??``)+`<b>`+i(g[t]??t)+`</b></span>`}).join(``)+`</div>`),e.healthBox.innerHTML=l}function re(e,t,n){let r=ne(n),a=h[r.status]??`unk`,o=n.length===0?`<li class="cp-empty"><i class="dot unk"></i>暂无检查点</li>`:n.map(e=>{let t=String(e.status??`unknown`),n=e.expectTime?`<time class="cp-tm" title="计划执行 `+i(e.expectTime)+`">`+i(e.expectTime)+`</time>`:``;return`<li><i class="dot `+(h[t]??`unk`)+`"></i>`+n+i(e.name??`?`)+`<em>`+i(m[t]??t)+`</em></li>`}).join(``);return`<div class="node st-`+a+`"><div class="n-top"><i class="dot `+a+`"></i><b>`+e+`</b><span>`+i(t)+`</span><em>`+i(r.label)+`</em></div><ul class="cps">`+o+`</ul></div>`}function ie(e,t){let n=t.checkpoints??[],r={};for(let e of n){let t=String(e.line??``),n=String(e.module??``);if(t!==`engine`&&t!==`autonomy`)continue;let i=t+`|`+n;(r[i]=r[i]||[]).push(e)}let i=(e,t,n)=>`<div class="dsh-exec-band"><div class="band-t"><span class="band-badge `+t+`">`+e+`</span>    <i></i></div><div class="band-nodes">`+n.map(e=>re(e.code,e.zh,r[t+`|`+e.code]??[])).join(``)+`</div></div>`;e.flowBox.innerHTML=i(`ENGINE`,`engine`,D)+i(`AUTONOMY`,`autonomy`,te)}function ae(e){return d[e]??`未知`}const j={v2:`引擎任务：quantsys-v2 cron 自动执行（不走 agent）`,os:`Agent OS 定时：webhook 触发 agent 执行`};function M(e){let t=String(e??``);if(t!==`v2`&&t!==`os`)return``;let n=t===`v2`?`引擎`:`系统`;return`<span class="exec-chip src `+t+`" title="`+i(j[t]??``)+`">`+n+`</span>`}function N(e){let t=String(e??``);return t!==`dh`&&t!==`ts`?``:`<span class="exec-chip ag `+t+`" title="调用 `+(t===`dh`?`agent-dh`:`agent-ts`)+` 智能体执行">智能体</span>`}function P(e){let t=String(e.status??`unknown`),n=String(e.expectedTime??``),r=t===`failed`&&e.error?` title="`+i(e.error)+`"`:``;return`<div class="tl-item `+(p[t]??`unk`)+`"`+r+`><span class="tl-tm">`+i(n.slice(0,5))+`</span><span class="tl-ic">`+(f[t]??`❔`)+`</span><div class="tl-bd"><div class="tl-nm">`+i(b(e.taskName))+`</div><div class="tl-st `+(p[t]??`unk`)+`">`+i(ae(t))+`</div><span class="tl-tags">`+M(e.src)+N(e.agentCall)+`</span></div></div>`}function F(e){let t=e.filter(e=>(e.freq??`daily`)!==`weekly`).length;return`共 `+e.length+` 项 · 日执行 `+t+` / 周执行 `+(e.length-t)}function oe(e,t){let n=(t.timeline??[]).slice().sort((e,t)=>o(e.expectedTime)-o(t.expectedTime));if(n.length===0){e.timelineBox.innerHTML=`<div class="dsh-exec-empty">今日暂无计划任务</div>`;return}let r={engine:[],autonomy:[],account:[],other:[]};for(let e of n)(r[T(String(e.taskName??``))]??r.other).push(e);let a=(e,t)=>`<div class="dsh-exec-tlg t-`+e+`"><div class="tlg-t"><span class="t">`+i(S[e]??e)+`</span><em>`+i(F(t))+`</em></div><div class="dsh-exec-tl-list">`+t.map(P).join(``)+`</div></div>`,s=(e,t)=>t.length===0?``:`<details class="dsh-exec-tld"><summary><span class="caret">▶</span><i class="dk l-`+e+`"></i><b>`+i(S[e]??e)+`</b><em>`+i(F(t))+`</em></summary><div class="dsh-exec-tl-list">`+t.map(P).join(``)+`</div></details>`,c=a(`engine`,r.engine)+a(`autonomy`,r.autonomy)+s(`account`,r.account)+s(`other`,r.other);e.timelineBox.innerHTML=c}function I(e){if(e.enabled!==!0&&e.enabled!==`true`&&e.enabled!==1)return{cls:`off`,label:`未启用`};let t=Number(e.todaySuccess)||0,n=Number(e.todayTriggered)||0;if(n>0)return t>=n?{cls:`ok`,label:`今日成功`}:{cls:`bad`,label:`今日失败`};let r=``;return typeof e.lastRun==`string`?r=e.lastRun:e.lastRun&&typeof e.lastRun==`object`&&(r=String(e.lastRun.status??``)),r===`success`?{cls:`ok`,label:`上次成功`}:r===`failed`?{cls:`bad`,label:`上次失败`}:r===`skipped`?{cls:`wait`,label:`已跳过`}:{cls:`wait`,label:`待执行`}}let L=null,R=`all`;function z(e){L=e}function B(e){R=e}let V=1,H=`all`,U=null;function W(e){V=e>0?Math.trunc(e):1}function G(e){return Math.floor(e/10)+1}function K(e,t,n){let r=t=>`<button type="button" class="tpg-num`+(t===e?` act`:``)+`"`+(t===e?` aria-current="page"`:``)+` data-tkpage="`+t+`">`+t+`</button>`,i=[];if(t<=7)for(let e=1;e<=t;e++)i.push(r(e));else{let n=[];for(let r of[1,e-1,e,e+1,t].sort((e,t)=>e-t))r<1||r>t||n.includes(r)||n.push(r);let a=0;for(let e of n)a!==0&&e-a>1&&i.push(`<span class="tpg-gap">…</span>`),i.push(r(e)),a=e}return`<button type="button" class="tpg-arr" data-tkpage="`+(e-1)+`"`+(e<=1?` disabled`:``)+`>‹ 上一页</button><span class="tpg-nums">`+i.join(``)+`</span><button type="button" class="tpg-arr" data-tkpage="`+(e+1)+`"`+(e>=t?` disabled`:``)+`>下一页 ›</button><span class="tpg-cnt">第 `+e+`/`+t+` 页 · 共 `+n+` 条</span>`}function q(e){let t=e.lastRun;if(t==null)return{at:`—`,st:``,err:``};let n=``,r=``,i=``;if(typeof t==`string`)/^(success|failed|skipped|running|pending|unknown)$/.test(t)?r=t:n=a(t);else if(typeof t==`object`){let e=t;n=a(e.triggeredAt),r=String(e.status??``),i=String(e.error??e.message??``)}return{at:n||`—`,st:r,err:i}}function se(e){let t=String(e??``).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);return t?t[1]+`-`+t[2]+`-`+t[3]+` `+t[4]+`:`+t[5]:String(e??``).trim()||`—`}function ce(e){let t=T(String(e.name??``)),n=I(e),r=q(e),a=Number(e.todayTriggered)||0,o=Number(e.todaySuccess)||0,s=String(e.name??``),l=i(b(s)),u=(e,t)=>`<div class="tkd-i"><b>`+e+`</b><span>`+t+`</span></div>`,f=`<div class="tkd-i"><b>名称</b><span`+(b(s)===s?``:` title="系统任务名：`+i(s)+`"`)+`>`+l+`</span></div>`;f+=u(`调度来源`,e.src===`os`?`Agent OS（webhook 触发）`:`quantsys-v2 引擎`),(e.agentCall===`dh`||e.agentCall===`ts`)&&(f+=u(`调用 Agent`,e.agentCall===`dh`?`agent-dh（LLM 智能体）`:`agent-ts（LLM 智能体）`)),f+=u(`状态`,`<span class="tag `+n.cls+`">`+i(n.label)+`</span>`),f+=u(`业务线`,i(S[t]??t));let p=String(e.scheduleExpr??``).trim(),m=c(p);f+=u(`计划时刻`,i(m)+(m&&m!==p&&m!==`—`?`<em class="tkd-code">原 cron: `+i(p)+`</em>`:``)),f+=u(`上次运行`,i(r.at)),f+=u(`上次结果`,r.st?i(d[r.st]??r.st):`—`),f+=u(`今日`,i(a+` 次触发 / `+o+` 成功`)),f+=u(`下次运行`,i(se(e.nextRunAt)));let h=r.err||String(e.error??``);return h&&(f+=`<div class="tkd-i tkd-err"><b>失败原因</b><span>`+i(h)+`</span></div>`),f}function J(e,t){let n=t.tasks??[];if(n.length===0){L=null,R=`all`,V=1,H=`all`,U=null,e.tasksBox.innerHTML=`<div class="dsh-exec-empty">暂无调度任务</div>`;return}let r={engine:0,autonomy:0,account:0,other:0};for(let e of n){let t=T(String(e.name??``));r[t]=(r[t]??0)+1}R===`all`||(r[R]??0)>0||(R=`all`);let o=e=>R===`all`||T(e)===R,s=n.filter(e=>o(String(e.name??``)));L!==null&&!s.some(e=>String(e.name)===L)&&(L=null);let l=R!==H,u=L!==U;H=R,U=L,l&&(V=1);let f=Math.max(1,Math.ceil(s.length/10));if(V>f&&(V=f),(l||u)&&L!==null){let e=s.findIndex(e=>String(e.name)===L);e>=0&&(V=G(e))}let m=s.slice((V-1)*10,V*10);L!==null&&!m.some(e=>String(e.name)===L)&&(L=null);let h=e=>`<b class="c">`+e+`</b>`,g=(e,t,n)=>`<button type="button" class="dsh-exec-tab`+(R===e?` act`:``)+`" data-dom="`+e+`">`+t+h(n)+`</button>`,_=[g(`all`,`全部`,n.length)];for(let e of x)(r[e.key]??0)>0&&_.push(g(e.key,`<i class="dk l-`+e.key+`"></i>`+i(e.zh),r[e.key]));let v=m.map(e=>{let t=String(e.name??``),n=I(e),r=q(e),o=Number(e.todayTriggered)||0,s=Number(e.todaySuccess)||0,l=r.err||String(e.error??``),u=t===L?` sel`:``,f=b(t);return`<tr class="dsh-exec-tr`+u+`" data-tk="`+i(t)+`"`+(l?` title="失败原因：`+i(l.slice(0,300))+`"`:``)+`><td class="nm"`+(f===t?``:` title="系统任务名：`+i(t)+`"`)+`><span class="ln-hd"><i class="dk l-`+T(t)+`"></i><span class="zh">`+i(f)+`</span></span></td><td class="cr" title="`+(e.scheduleExpr?i(`原 cron: `+String(e.scheduleExpr).trim()):``)+`">`+i(c(e.scheduleExpr))+`</td><td class="st"><span class="tag `+n.cls+`">`+i(n.label)+`</span>`+M(e.src)+N(e.agentCall)+`</td><td class="tm">`+i(r.at)+(r.st?`<em class="ls `+(p[r.st]??`unk`)+`">`+i(d[r.st]??r.st)+`</em>`:``)+`</td><td class="td">`+i(o+` 触发 / `+s+` 成功`)+`</td><td class="nx">`+i(a(e.nextRunAt))+`</td><td class="op">`+(n.cls===`bad`?`<button type="button" class="dsh-exec-solve" data-solve-task="`+i(t)+`" title="把该失败任务投递给窗口排查处置">我来解决</button>`:``)+`</td></tr>`}).join(``),y=s.length>10?`<div class="dsh-exec-tkpg">`+K(V,f,s.length)+`</div>`:``,S=L===null?null:s.find(e=>String(e.name)===L);e.tasksBox.innerHTML=`<div class="dsh-exec-legend dsh-exec-legend2"><span class="dsh-exec-hint">按业务线点击 tab 切换 · 点击任务行查看失败原因 · 失败行/错误条可点「我来解决」投递窗口排查 · 表底每页 10 条翻页 · <i class="dot ok"></i>成功 <i class="dot bad"></i>失败 <i class="dot wait"></i>待执行 <i class="dot off"></i>未启用</span></div><div class="dsh-exec-tabs">`+_.join(``)+`</div><div class="dsh-exec-tkcard"><div class="dsh-exec-tbwrap"><table class="dsh-exec-tb"><thead><tr><th>任务</th><th>计划时刻</th><th>状态</th><th>上次运行</th><th>今日</th><th>下次运行</th><th class="op">处理</th></tr></thead><tbody>`+(v||`<tr class="empty"><td colspan="7">该分类下暂无任务</td></tr>`)+`</tbody></table></div>`+y+`</div>`+(S?`<div class="dsh-exec-tkdetail">`+ce(S)+`</div>`:``)}function le(e,t){let n=t.errors??[];e.errsSec.style.display=n.length>0?``:`none`,n.length!==0&&(e.errsBox.innerHTML=`<ol class="dsh-exec-errs">`+n.slice(0,10).map((e,t)=>{let n=String(e.source??``).toLowerCase(),r=n.includes(`os`)?`os`:n.includes(`dsh`)?`dsh`:`v2`,o=u((e.line??e.file??``).replace(/\\n/g,` `),120);return`<li><span class="src `+r+`">`+i(e.source??`?`)+`</span><time>`+i(a(e.timestamp))+`</time><span class="line" title="`+i(e.line??``)+`">`+i(o)+`</span><button type="button" class="dsh-exec-solve" data-solve-err="`+t+`" title="把该错误事件投递给窗口排查处置">我来解决</button></li>`}).join(``)+`</ol>`)}function ue(e,t){let n=t.blockedFlows??[];e.blockSec.style.display=n.length>0?``:`none`,n.length!==0&&(e.blockBox.innerHTML=n.map(e=>`<div class="dsh-exec-block"><b>`+i(e.checkpointName??e.checkpointId??`?`)+`</b><span class="tag bad">`+i(m[String(e.status??``)]??i(e.status??``))+`</span>`+(e.blocks&&e.blocks.length>0?`<span class="blocks">阻断: `+i(e.blocks.join(`, `))+`</span>`:``)+`</div>`).join(``))}function de(e,t){A(e,t),ie(e,t),oe(e,t),J(e,t),le(e,t),ue(e,t)}function fe(e){let t=e.prefix,n,r,i=()=>{r?.(),r=void 0,n!==void 0&&(n.remove(),n=void 0)},a=(e,n)=>{let r=document.createElement(`div`);r.className=t+`-toast `+(n?`ok`:`err`),r.textContent=e,document.body.appendChild(r),window.setTimeout(()=>{r.classList.add(`out`),window.setTimeout(()=>r.remove(),350)},4200)},o=async(t,n,r)=>{let i=e.current();try{let o=await fetch(e.endpoint,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({kind:t,task:t===`task`?n:void 0,err:t===`error`?n:void 0,from_session:i||void 0,to_session:r})}),s=await o.json().catch(()=>null);if(s===null||s.success!==!0){a(`投递失败：`+String(s?.error??`HTTP `+o.status),!1);return}let c=s.data;a(c?.delivered===!0?`✓ `+String(c?.note??`已投递`):`⚠ `+String(c?.error??s.error??`投递失败`),c?.delivered===!0)}catch(e){a(`请求异常：`+String(e instanceof Error?e.message:e),!1)}};return{toast:a,openPicker:(s,c,l)=>{let u=e.resolveSnapshot(c,l);if(u===null){a(`⚠ 数据已刷新，请重试`,!1);return}i();let d=e.candidates();if(d.length===0){o(u.kind,u.snap);return}let f=document.createElement(`div`);f.className=t+`-solvepop`;let p=document.createElement(`div`);p.className=t+`-solvepop-head`,p.textContent=`投递给窗口排查处置`,f.appendChild(p);let m=document.createElement(`div`);m.className=t+`-solvepop-list`;for(let e of d){let n=document.createElement(`button`);n.type=`button`,n.className=t+`-solvepop-item`+(e.current?` cur`:``),n.textContent=(e.current?`● `:`○ `)+e.label,n.addEventListener(`click`,()=>{i(),o(u.kind,u.snap,e.sid)}),m.appendChild(n)}f.appendChild(m);let h=document.createElement(`button`);h.type=`button`,h.className=t+`-solvepop-cancel`,h.textContent=`取消`,h.addEventListener(`click`,i),f.appendChild(h);let g;try{g=typeof e.host==`function`?e.host():e.host}catch{g=void 0}(g??document.body).appendChild(f),n=f;let _=s.getBoundingClientRect(),v=40+d.length*30+32,y=_.bottom+6;y+v>window.innerHeight&&(y=Math.max(6,_.top-v-6)),f.style.position=`fixed`,f.style.left=Math.min(_.left,Math.max(6,window.innerWidth-280))+`px`,f.style.top=y+`px`;let b=e=>{let t=e.target;t!==null&&f.contains(t)||(document.removeEventListener(`click`,b,!0),r=void 0,i())};document.addEventListener(`click`,b,!0),r=()=>document.removeEventListener(`click`,b,!0)},close:i}}let Y=!1;function pe(){let e={boardOpen:!1},i=()=>{e.boardOpen=!0,o()},a=()=>{e.boardOpen=!1,o()},o=()=>{if(e.boardOpen){for(let e of n)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(t,``),document.dispatchEvent(new CustomEvent(r,{detail:`dashboard-execution`}))}else document.documentElement.removeAttribute(t)};return{isActive:()=>e.boardOpen,toggle:()=>{e.boardOpen?a():i()},getSnapshot:()=>e,openBoard:i,closeBoard:a,toggleBoard:()=>{e.boardOpen?a():i()}}}function me(e){let n,i,a=0,o,s,c=()=>{if(i!==void 0)return;let e=document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`);e!==null&&(i=document.createElement(`div`),i.dataset.dshExecView=``,i.className=`dsh-exec-view`,e.appendChild(i),n=k(),i.appendChild(n.board),o=i.querySelector(`[data-role="refresh"]`)??void 0,o?.addEventListener(`click`,()=>{u()}),n.tasksBox.addEventListener(`click`,e=>{let t=e.target;if(s===void 0||n===void 0)return;let r=t.closest(`.dsh-exec-solve[data-solve-task]`);if(r!==null&&r.dataset.solveTask!==void 0){m.openPicker(r,`task`,{name:r.dataset.solveTask});return}let i=t.closest(`.dsh-exec-tab[data-dom]`);if(i!==null){B(i.dataset.dom??`all`),J(n,s);return}let a=t.closest(`.dsh-exec-tkpg [data-tkpage]`);if(a!==null&&!a.disabled){W(Number(a.dataset.tkpage)),J(n,s);return}let o=t.closest(`.dsh-exec-tr[data-tk]`)?.dataset.tk;o!==void 0&&(z(o),J(n,s))}),n.errsBox.addEventListener(`click`,e=>{let t=e.target.closest(`.dsh-exec-solve[data-solve-err]`);t!==null&&t.dataset.solveErr!==void 0&&m.openPicker(t,`error`,{index:Number(t.dataset.solveErr)})}),u(!0))},l=new MutationObserver(()=>{c()});l.observe(document.body,{childList:!0,subtree:!0});async function u(e=!1){if(!Y){Y=!0;try{let e=await fetch(`/dashboard/api/board`,{headers:{Accept:`application/json`}});if(!e.ok)throw Error(`HTTP `+e.status);let t=await e.json();if(!t.success||t.data===void 0)throw Error(t.error??`API 返回失败`);if(n===void 0)return;s=t.data,de(n,s),n.meta.textContent=`刷新于 `+new Date().toLocaleTimeString()+` · 数据 `+(t.data.fetchedAt??``),n.banner.classList.remove(`show`)}catch(e){if(n===void 0)return;n.banner.innerHTML=`⚠ 无法连接看板 API：`+String(e&&e.message?e.message:e)+` — 请检查 :13080 与插件状态`,n.banner.classList.add(`show`)}finally{Y=!1}}}let d=()=>{let e=window,t=e.__dshExecSessions;if(!t?.list)try{t=e.__dshExecCtx?.sessions,t?.list&&(e.__dshExecSessions=t)}catch{}let n=null;try{let t=e.__dshExecWorkspaces?.list?.getSnapshot?.()?.archivedSessionIds;Array.isArray(t)&&(n=new Set(t.map(String)))}catch{}let r=[];try{let e=t?.list?.getSnapshot?.();if(!e)return r;let i=String(e.current??``),a=Array.isArray(e.items)?e.items:Array.isArray(e.ids)?e.ids.map(t=>e.byId?.[t]).filter(Boolean):[];for(let e of a){let t=String(e?.id??e?.sessionId??``);!t||e.blank||n?.has(t)||e?.origin!==`subagent`&&r.push({sid:t,label:String(e.displayTitle??e.title??t),current:t===i})}}catch{}return r},f=()=>{try{return String(window.__dshExecSessions?.list?.getSnapshot?.()?.current??``)}catch{return``}},p=(e,t)=>{if(s===void 0)return null;let n=s.fetchedAt??``;if(e===`task`){let e=(s.tasks??[]).find(e=>String(e.name)===t.name);return e?{kind:`task`,snap:{...e,fetchedAt:n}}:null}let r=(s.errors??[])[Number(t.index)];return r?{kind:`error`,snap:{...r,fetchedAt:n}}:null},m=fe({endpoint:`/dashboard/api/board/solve`,prefix:`dsh-exec`,candidates:d,current:f,resolveSnapshot:(e,t)=>p(e,t),host:()=>i}),h=t=>{t.detail!==`dashboard-execution`&&e.getSnapshot().boardOpen&&e.closeBoard()},g=t=>{if(!e.getSnapshot().boardOpen)return;let n=t.target;n!==null&&n.closest(`[data-dsh-exec-view]`)===null&&n.closest(`[data-dsh-exec-entry]`)===null&&n.closest(`[class*="dsh-exec-foot"]`)===null&&e.closeBoard()};document.addEventListener(`click`,g,!0),document.addEventListener(r,h);let _=()=>{a!==0&&window.clearInterval(a),a=window.setInterval(()=>{u()},3e4)},v=()=>{a!==0&&(window.clearInterval(a),a=0)},y=()=>{document.hidden?v():(_(),u())};return document.addEventListener(`visibilitychange`,y),c(),_(),()=>{document.removeEventListener(`click`,g,!0),document.removeEventListener(r,h),document.removeEventListener(`visibilitychange`,y),l.disconnect(),v(),m.close(),document.documentElement.removeAttribute(t),i?.remove(),i=void 0,n=void 0}}const X=`智能执行`,Z=`@pi-investment/dashboard-execution/footer-action.css`,Q=`dashboard-execution:open-board`;function he(t){let{wide:n}=t,r=X;return(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-exec-foot wide`:`dsh-exec-foot rail`,title:r,"aria-label":r,onClick:()=>{console.log(`[dashboard-execution] footer action clicked — dispatching`,Q),window.dispatchEvent(new CustomEvent(Q,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-exec-foot-icon`,key:`i`},$),(0,e.createElement)(`span`,{className:`dsh-exec-foot-label`,key:`l`},r)]:(0,e.createElement)(`span`,{className:`dsh-exec-foot-icon`,key:`i`},$))}const $=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function ge(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${Z}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=Z,e.textContent=`
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
`,document.head.appendChild(e)}function _e(){let e=`dsh-exec-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
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

html[data-dsh-exec-active] [data-pane="conversation"] > *:not([data-dsh-exec-view]),
html[data-dsh-exec-active] [class*="centerCol"] > *:not([data-dsh-exec-view]),
html[data-dsh-exec-active] .dshDesktopConversationSurface > *:not([data-dsh-exec-view]) { display: none !important; }
.dsh-exec-view { display: none; }
html[data-dsh-exec-active] .dsh-exec-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
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
.dsh-exec-errs li .src { flex:none; border-radius:4px; padding:0 6px; font-size:10.5px; color:#fff; }
.dsh-exec-errs .src.v2 { background:#e6a23c; } .dsh-exec-errs .src.os { background:#409eff; } .dsh-exec-errs .src.dsh { background:#909399; }
.dsh-exec-errs li time { flex:none; color:var(--faint); font-size:11px; font-variant-numeric:tabular-nums; }
.dsh-exec-errs li .line { color:var(--dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
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
`,(document.head??document.documentElement).appendChild(t)}const ve=[`slots`,`sessions`,`workspaces`];function ye(e){try{window.__dshExecCtx=e,window.__dshExecSessions=e?.sessions,window.__dshExecWorkspaces=e?.workspaces}catch{}try{ge(),_e(),window.__dshExecClient?.dispose();let t=pe(),n=me(t),r=e=>{let n=e.detail?.open;console.log(`[dashboard-execution] open-board event`,{open:n},`boardOpen:`,t.getSnapshot().boardOpen),n===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(Q,r),window.__dshExecClient={dispose:()=>{window.removeEventListener(Q,r),n(),t.closeBoard()}};let i=e.slots;i?i.inject(`sidebar.footer.action`,()=>i.register({name:`sidebar.footer.action`,id:`dashboard-execution`,order:100,label:X},he)):console.warn(`[dashboard-execution] ctx.slots unavailable (inject missing "slots")`)}catch(e){console.error(`[dashboard-execution] client half failed to start:`,e)}}exports.apply=ye,exports.inject=ve,exports.name=`@pi-investment/dashboard-execution/client`;