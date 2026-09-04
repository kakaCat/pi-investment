Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");const t=`data-dsh-exec-active`,n=[`data-dsh-atb-active`,`data-dsh-taskboard-active`,`data-dsh-ssh-active`,`data-dsh-hld-active`],r=`dsh-panel-activate`;function i(e){return e==null?``:String(e).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`).replace(/"/g,`&quot;`)}function a(e){if(!e)return`—`;let t=String(e).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);if(!t)return i(e).slice(0,5);let n=new Date,r=e=>(e<10?`0`:``)+e,a=n.getFullYear()+`-`+r(n.getMonth()+1)+`-`+r(n.getDate()),o=t[4]+`:`+t[5];return(t[1]+`-`+t[2]+`-`+t[3]===a?``:t[2]+`-`+t[3]+` `)+o}function o(e){let t=String(e??``).match(/^(\d{2}):(\d{2})/);return t?Number(t[1])*60+Number(t[2]):9999}const s=[`周日`,`周一`,`周二`,`周三`,`周四`,`周五`,`周六`];function c(e){let t=String(e??``).trim(),n=t.split(/\s+/);if(n.length!==5)return t||`—`;let r=n[0],i=n[1],a=n[2],o=n[3],c=n[4],u=e=>/^\d+$/.test(e)?Number(e):null;if(i===`*`||i===`?`)return r===`0`||r===`*`?`每小时`:t;let d=u(i),f=r===`*`||r===`?`?0:u(r);if(d===null||f===null||d>23||f>59)return t;let p=String(d).padStart(2,`0`)+`:`+String(f).padStart(2,`0`),m=u(a),h=o!==`*`&&o!==`?`?u(o):null;if(m!==null)return(h===null?`每月 `+m+` 日`:`每年 `+h+` 月 `+m+` 日`)+` `+p;if(a!==`*`&&a!==`?`&&a!==`L`)return t;if(a===`L`)return`每月最后一日 `+p;let g=l(c);if(g===null)return t;let _;return _=g.length===7?`每日`:g.length===5&&g.every(e=>e>=1&&e<=5)?`工作日`:`每`+g.map(e=>s[e]).join(`、`),h!==null&&(_+=`（`+h+` 月）`),_+` `+p}function l(e){if(e===`*`||e===`?`){let e=[];for(let t=0;t<7;t++)e.push(t);return e}let t=[];for(let n of e.split(`,`)){let e=/^(\d+)(?:-(\d+))?$/.exec(n.trim());if(!e)return null;let r=Number(e[1])%7,i=e[2]?Number(e[2])%7:r;if(i<r)return null;for(let e=r;e<=i;e++)t.push(e)}return[...new Set(t)].sort((e,t)=>e-t)}function u(e,t){let n=String(e??``).trim();return n.length<=t?n:n.slice(0,t)+`…`}const d={success:`成功`,failed:`失败`,pending:`待执行`,skipped:`已跳过`,unknown:`未知`},f={success:`✅`,failed:`❌`,pending:`⏳`,skipped:`⏭️`,unknown:`❔`},p={success:`ok`,failed:`bad`,pending:`wait`,skipped:`wait`,unknown:`unk`},m={confirmed:`已确认`,pending:`等待`,off_day:`非执行日`,failed:`失败`,late:`晚点`,degraded:`降级`,unknown:`未知`},h={confirmed:`ok`,pending:`wait`,off_day:`off`,failed:`bad`,late:`late`,degraded:`deg`,unknown:`unk`},g={ok:`正常`,degraded:`降级`,failed:`故障`,unknown:`未知`},_={ok:`ok`,degraded:`deg`,failed:`bad`,unknown:`unk`},v={"quantsys-v2":`量化后端 quantsys-v2`,"agent-os":`Agent OS`,postgres:`数据库 PostgreSQL`,"agent-dh":`Agent-DH 宿主`},y={market_daily_snapshot:`每日市场快照`,chan_scan_daily:`产业链链扫`,"chan-scan-daily":`产业链链扫`,v13_risk_check:`风控熔断检查`,"v13-risk-check":`风控熔断检查`,daily_trade_verify:`交易对账`,signal_perf_backfill_daily:`信号表现回填`,"signal-perf-backfill-daily":`信号表现回填`,v13_weekly_report:`每周报告`,"v13-weekly-report":`每周报告(v13)`,market_style_update:`市场风格更新`,"market-style-update":`市场风格更新`,v13_simulation_trading:`模拟交易执行`,"v13-simulation-trading":`模拟交易执行`,v13_verification:`策略验证裁决`,"v13-verification":`策略验证裁决`,pre_market_scan:`盘前扫描`,"pre-market-scan":`盘前扫描`,weekly_strategy_discovery:`周度策略发现`,"weekly-strategy-discovery":`周度策略发现`,daily_strategy_validation:`策略日验证`,"daily-strategy-validation":`策略日验证`,daily_pool_refresh:`股票池刷新`,"daily-pool-refresh":`股票池刷新`,fund_flow_update:`资金流数据更新`,chan_knowledge_distill_weekly:`知识蒸馏(周)`,"chan-knowledge-distill-weekly":`知识蒸馏(周)`,每日数据更新:`每日数据更新`,每日数据质量检查:`每日数据质量检查`,每周财务数据更新:`每周财务数据更新`,每日财报时效性检查:`每日财报时效性检查`,每日信号生成:`每日信号生成`,每日信号执行:`每日信号执行`,每周报告生成:`每周报告生成`,"pre-market-routine":`盘前例程`,"afternoon-open-check-live":`午后开盘检查`,"data-quality-monitor-daily":`数据质量监控`,"event-calendar-check":`事件日历检查`,"m4-circuit-breaker-live":`熔断回路检查`,"post-market-routine-live":`盘后例程`,"evolution-distill-daily":`进化蒸馏`,"evolution-gate-adjudicate":`进化裁决`,"evolution-weekly-variant":`进化变体`,"meta-learning-weekly":`元学习`,"weekly-report-m6":`学习飞轮周报`,"geer-take-profit-0901":`歌尔止盈观察`};function b(e){let t=String(e??``);return y[t]??t}const x=[{title:`数据与行情`,keys:[`每日数据更新`,`每日数据质量检查`,`每日财报时效性检查`,`每周财务数据更新`,`fund_flow_update`]},{title:`市场感知`,keys:[`market_daily_snapshot`,`market-style-update`,`pre-market-scan`]},{title:`信号与股票池`,keys:[`每日信号生成`,`每日信号执行`,`chan-scan-daily`,`daily-pool-refresh`]},{title:`风控与交易`,keys:[`v13-risk-check`,`daily_trade_verify`,`v13-simulation-trading`]},{title:`学习与验证`,keys:[`daily-strategy-validation`,`v13-verification`,`chan-knowledge-distill-weekly`,`weekly-strategy-discovery`,`signal-perf-backfill-daily`]},{title:`周报与汇总`,keys:[`v13-weekly-report`,`每周报告生成`]},{title:`自主例程`,keys:[`pre-market-routine`,`afternoon-open-check-live`,`data-quality-monitor-daily`,`event-calendar-check`,`m4-circuit-breaker-live`,`post-market-routine-live`,`evolution-distill-daily`,`geer-take-profit-0901`,`evolution-gate-adjudicate`,`evolution-weekly-variant`,`meta-learning-weekly`,`weekly-report-m6`]}];function S(e){let t=String(e??``);for(let e=0;e<x.length;e++)if(x[e].keys.includes(t))return{title:x[e].title,idx:e};return null}const ee=[{code:`M0`,zh:`数据地基`},{code:`M1`,zh:`市场感知`},{code:`M2`,zh:`股票池`},{code:`M3`,zh:`信号生成`},{code:`M4`,zh:`风控止损`},{code:`M5`,zh:`交易对账`},{code:`M6`,zh:`经验进化`}],C=[{code:`L1`,zh:`策略验证`},{code:`L2`,zh:`经验蒸馏`},{code:`L3`,zh:`验证门裁决`},{code:`L4`,zh:`周报进化`}],w={failed:5,late:4,degraded:3,pending:2,off_day:1,unknown:0,confirmed:0};function T(e){if(e.length===0)return{status:`unknown`,label:`暂无检查点`};let t=`confirmed`;for(let n of e){let e=String(n.status??`unknown`);(w[e]??0)>(w[t]??0)&&(t=e)}return{status:t,label:m[t]??t}}function te(){let e=document.createElement(`div`);e.className=`dsh-exec-board`;let t=e=>{let t=document.createElement(`div`);return t.innerHTML=e,t.firstElementChild},n=(e,n,r,a=`bd`)=>t(`<section class="dsh-exec-cardx"><div class="hd"><span class="t">`+i(e)+`</span><span class="more">`+i(n)+`</span></div><div class="`+a+`" data-role="`+r+`"></div></section>`),r=document.createElement(`div`);r.className=`dsh-exec-wrap`;let a=t(`<div class="dsh-exec-head"><h1 class="dsh-exec-title">双线执行确认看板<small>只读监控 · 运行与操作由 agent 自动完成</small></h1><div class="dsh-exec-meta"><span class="dsh-exec-last" data-role="lastFetch">—</span><button type="button" class="dsh-exec-btn" data-role="refresh">↻ 刷新</button></div></div>`),o=t(`<div class="dsh-exec-banner" data-role="banner"></div>`),s=n(`今日执行总览`,`来自当日 cron 计划与运行结果`,`healthBox`),c=n(`执行流水线`,`ENGINE M0–M6 × AUTONOMY L1–L4 检查点状态`,`flowBox`),l=n(`今日时间轴`,`分 日执行 / 周执行 · 徽标 v2/os=调度来源 dh/ts=调用 agent · 按计划时刻排序`,`timelineBox`),u=n(`调度任务`,`分类切换 · 徽标 v2/os=调度来源 dh/ts=调用 agent · 点击任务行查看失败原因`,`tasksBox`),d=n(`错误事件`,`近 10 条日志异常（系统侧）`,`errsBox`);d.style.display=`none`;let f=n(`流水线阻断`,`failed/late 且声明阻断下游`,`blockBox`);f.style.display=`none`,r.append(a,o,s,c,l,u,d,f),e.appendChild(r);let p=t=>e.querySelector(t);return{board:e,meta:p(`[data-role="lastFetch"]`),banner:o,healthBox:p(`[data-role="healthBox"]`),flowBox:p(`[data-role="flowBox"]`),timelineBox:p(`[data-role="timelineBox"]`),tasksBox:p(`[data-role="tasksBox"]`),errsSec:d,errsBox:p(`[data-role="errsBox"]`),blockSec:f,blockBox:p(`[data-role="blockBox"]`)}}function E(e,t){let n=t.timeline??[],r=n.length,a=0,o=0;for(let e of n)e.status===`success`?a++:e.status===`failed`&&o++;let s=Math.max(0,r-a-o),c=(e,t,n)=>`<div class="hb-item `+n+`"><div class="v">`+e+`</div><div class="n">`+t+`</div></div>`,l=`<div class="dsh-exec-hb">`+c(String(r),`今日计划任务`,`t`)+c(String(a),`✅ 已完成`,`ok`)+c(String(o),`❌ 失败`,o>0?`bad`:`ok`)+c(String(s),`⏳ 待执行`,`wait`)+`</div>`,u=t.health??[];u.length>0&&(l+=`<div class="dsh-exec-pills">`+u.map(e=>{let t=String(e.status??`unknown`);return`<span class="pill `+(t===`ok`?`ok`:`warn`)+`" title="`+i(e.error??``)+`"><i class="dot `+(_[t]??`unk`)+`"></i>`+i(v[e.name??``]??e.name??``)+`<b>`+i(g[t]??t)+`</b></span>`}).join(``)+`</div>`),e.healthBox.innerHTML=l}function D(e,t,n){let r=T(n),a=h[r.status]??`unk`,o=n.length===0?`<li class="cp-empty"><i class="dot unk"></i>暂无检查点</li>`:n.map(e=>{let t=String(e.status??`unknown`),n=e.expectTime?`<time class="cp-tm" title="计划执行 `+i(e.expectTime)+`">`+i(e.expectTime)+`</time>`:``;return`<li><i class="dot `+(h[t]??`unk`)+`"></i>`+n+i(e.name??`?`)+`<em>`+i(m[t]??t)+`</em></li>`}).join(``);return`<div class="node st-`+a+`"><div class="n-top"><i class="dot `+a+`"></i><b>`+e+`</b><span>`+i(t)+`</span><em>`+i(r.label)+`</em></div><ul class="cps">`+o+`</ul></div>`}function O(e,t){let n=t.checkpoints??[],r={};for(let e of n){let t=String(e.line??``),n=String(e.module??``);if(t!==`engine`&&t!==`autonomy`)continue;let i=t+`|`+n;(r[i]=r[i]||[]).push(e)}let i=(e,t,n)=>`<div class="dsh-exec-band"><div class="band-t"><span class="band-badge `+t+`">`+e+`</span>    <i></i></div><div class="band-nodes">`+n.map(e=>D(e.code,e.zh,r[t+`|`+e.code]??[])).join(``)+`</div></div>`;e.flowBox.innerHTML=i(`ENGINE`,`engine`,ee)+i(`AUTONOMY`,`autonomy`,C)}function k(e){return d[e]??`未知`}const A={v2:`引擎任务：quantsys-v2 cron 自动执行（不走 agent）`,os:`Agent OS 定时：webhook 触发 agent 执行`};function j(e){let t=String(e??``);return t!==`v2`&&t!==`os`?``:`<span class="exec-chip src `+t+`" title="`+i(A[t]??``)+`">`+t+`</span>`}function M(e){let t=String(e??``);return t!==`dh`&&t!==`ts`?``:`<span class="exec-chip ag `+t+`" title="调用 `+(t===`dh`?`agent-dh`:`agent-ts`)+` 智能体执行">`+t+`</span>`}function N(e){let t=String(e.status??`unknown`),n=String(e.expectedTime??``),r=t===`failed`&&e.error?` title="`+i(e.error)+`"`:``;return`<div class="tl-item `+(p[t]??`unk`)+`"`+r+`><span class="tl-tm">`+i(n.slice(0,5))+`</span><span class="tl-ic">`+(f[t]??`❔`)+`</span><div class="tl-bd"><div class="tl-nm">`+i(b(e.taskName))+`</div><div class="tl-st `+(p[t]??`unk`)+`">`+i(k(t))+`</div><span class="tl-tags">`+j(e.src)+M(e.agentCall)+`</span></div></div>`}function P(e,t){let n=(t.timeline??[]).slice().sort((e,t)=>o(e.expectedTime)-o(t.expectedTime));if(n.length===0){e.timelineBox.innerHTML=`<div class="dsh-exec-empty">今日暂无计划任务</div>`;return}let r=(e,t,n)=>`<div class="dsh-exec-tlg"><div class="tlg-t"><span class="t">`+e+`</span><em>`+t+` · `+n.length+` 项</em></div><div class="dsh-exec-tl-list">`+n.map(N).join(``)+`</div></div>`,i=n.filter(e=>(e.freq??`daily`)!==`weekly`),a=n.filter(e=>e.freq===`weekly`),s=r(`日执行`,`每日 / 交易日例行`,i)+(a.length>0?r(`周执行`,`每周固定日`,a):``);e.timelineBox.innerHTML=s}function F(e){if(e.enabled!==!0&&e.enabled!==`true`&&e.enabled!==1)return{cls:`off`,label:`未启用`};let t=Number(e.todaySuccess)||0,n=Number(e.todayTriggered)||0;if(n>0)return t>=n?{cls:`ok`,label:`今日成功`}:{cls:`bad`,label:`今日失败`};let r=``;return typeof e.lastRun==`string`?r=e.lastRun:e.lastRun&&typeof e.lastRun==`object`&&(r=String(e.lastRun.status??``)),r===`success`?{cls:`ok`,label:`上次成功`}:r===`failed`?{cls:`bad`,label:`上次失败`}:r===`skipped`?{cls:`wait`,label:`已跳过`}:{cls:`wait`,label:`待执行`}}let I=null,L=`all`;function R(e){I=e}function z(e){L=e}function B(e){let t=e.lastRun;if(t==null)return{at:`—`,st:``,err:``};let n=``,r=``,i=``;if(typeof t==`string`)/^(success|failed|skipped|running|pending|unknown)$/.test(t)?r=t:n=a(t);else if(typeof t==`object`){let e=t;n=a(e.triggeredAt),r=String(e.status??``),i=String(e.error??e.message??``)}return{at:n||`—`,st:r,err:i}}function V(e){let t=String(e??``).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);return t?t[1]+`-`+t[2]+`-`+t[3]+` `+t[4]+`:`+t[5]:String(e??``).trim()||`—`}function H(e){let t=S(e.name),n=F(e),r=B(e),a=Number(e.todayTriggered)||0,o=Number(e.todaySuccess)||0,s=String(e.name??``),l=i(b(s)),u=(e,t)=>`<div class="tkd-i"><b>`+e+`</b><span>`+t+`</span></div>`,f=u(`名称`,l+(b(s)===s?``:`<em class="tkd-code">`+i(s)+`</em>`));f+=u(`调度来源`,e.src===`os`?`Agent OS（webhook 触发）`:`quantsys-v2 引擎`),(e.agentCall===`dh`||e.agentCall===`ts`)&&(f+=u(`调用 Agent`,e.agentCall===`dh`?`agent-dh（LLM 智能体）`:`agent-ts（LLM 智能体）`)),f+=u(`状态`,`<span class="tag `+n.cls+`">`+i(n.label)+`</span>`),f+=u(`领域`,i(t?t.title:`其他任务`));let p=String(e.scheduleExpr??``).trim(),m=c(p);f+=u(`计划时刻`,i(m)+(m&&m!==p&&m!==`—`?`<em class="tkd-code">原 cron: `+i(p)+`</em>`:``)),f+=u(`上次运行`,i(r.at)),f+=u(`上次结果`,r.st?i(d[r.st]??r.st):`—`),f+=u(`今日`,i(a+` 次触发 / `+o+` 成功`)),f+=u(`下次运行`,i(V(e.nextRunAt)));let h=r.err||String(e.error??``);return h&&(f+=`<div class="tkd-i tkd-err"><b>失败原因</b><span>`+i(h)+`</span></div>`),f}function U(e,t){let n=t.tasks??[];if(n.length===0){I=null,L=`all`,e.tasksBox.innerHTML=`<div class="dsh-exec-empty">暂无调度任务</div>`;return}let r=x.map(()=>0),o=0;for(let e of n){let t=S(e.name);t?r[t.idx]++:o++}L===`all`||(L===`x`?o>0:r[Number(L)]>0)||(L=`all`);let s=e=>{if(L===`all`)return!0;let t=S(e);return L===`x`?t===null:t!==null&&String(t.idx)===L},l=n.filter(e=>s(String(e.name??``)));I!==null&&!l.some(e=>String(e.name)===I)&&(I=null);let u=e=>`<b class="c">`+e+`</b>`,f=(e,t,n)=>`<button type="button" class="dsh-exec-tab`+(L===e?` act`:``)+`" data-dom="`+e+`">`+t+u(n)+`</button>`,m=[f(`all`,`全部`,n.length)];x.forEach((e,t)=>{r[t]>0&&m.push(f(String(t),`<i class="dk d`+t+`"></i>`+i(e.title),r[t]))}),o>0&&m.push(f(`x`,`其他任务`,o));let h=l.map(e=>{let t=String(e.name??``),n=F(e),r=B(e),o=Number(e.todayTriggered)||0,s=Number(e.todaySuccess)||0,l=r.err||String(e.error??``),u=t===I?` sel`:``,f=b(t);return`<tr class="dsh-exec-tr`+u+`" data-tk="`+i(t)+`"`+(l?` title="失败原因：`+i(l.slice(0,300))+`"`:``)+`><td class="nm"><span class="zh">`+i(f)+`</span>`+(f===t?``:`<span class="code">`+i(t)+`</span>`)+`</td><td class="cr" title="`+(e.scheduleExpr?i(`原 cron: `+String(e.scheduleExpr).trim()):``)+`">`+i(c(e.scheduleExpr))+`</td><td class="st"><span class="tag `+n.cls+`">`+i(n.label)+`</span>`+j(e.src)+M(e.agentCall)+`</td><td class="tm">`+i(r.at)+(r.st?`<em class="ls `+(p[r.st]??`unk`)+`">`+i(d[r.st]??r.st)+`</em>`:``)+`</td><td class="td">`+i(o+` 触发 / `+s+` 成功`)+`</td><td class="nx">`+i(a(e.nextRunAt))+`</td></tr>`}).join(``),g=I===null?null:l.find(e=>String(e.name)===I);e.tasksBox.innerHTML=`<div class="dsh-exec-legend dsh-exec-legend2"><span class="dsh-exec-hint">点击 tab 切换分类 · 点击任务行查看失败原因 · <i class="dot ok"></i>成功 <i class="dot bad"></i>失败 <i class="dot wait"></i>待执行 <i class="dot off"></i>未启用</span></div><div class="dsh-exec-tabs">`+m.join(``)+`</div><div class="dsh-exec-tbwrap"><table class="dsh-exec-tb"><thead><tr><th>任务</th><th>计划时刻</th><th>状态</th><th>上次运行</th><th>今日</th><th>下次运行</th></tr></thead><tbody>`+(h||`<tr class="empty"><td colspan="6">该分类下暂无任务</td></tr>`)+`</tbody></table></div>`+(g?`<div class="dsh-exec-tkdetail">`+H(g)+`</div>`:``)}function W(e,t){let n=t.errors??[];e.errsSec.style.display=n.length>0?``:`none`,n.length!==0&&(e.errsBox.innerHTML=`<ol class="dsh-exec-errs">`+n.slice(0,10).map(e=>{let t=String(e.source??``).toLowerCase(),n=t.includes(`os`)?`os`:t.includes(`dsh`)?`dsh`:`v2`,r=u((e.line??e.file??``).replace(/\\n/g,` `),120);return`<li><span class="src `+n+`">`+i(e.source??`?`)+`</span><time>`+i(a(e.timestamp))+`</time><span class="line" title="`+i(e.line??``)+`">`+i(r)+`</span></li>`}).join(``)+`</ol>`)}function G(e,t){let n=t.blockedFlows??[];e.blockSec.style.display=n.length>0?``:`none`,n.length!==0&&(e.blockBox.innerHTML=n.map(e=>`<div class="dsh-exec-block"><b>`+i(e.checkpointName??e.checkpointId??`?`)+`</b><span class="tag bad">`+i(m[String(e.status??``)]??i(e.status??``))+`</span>`+(e.blocks&&e.blocks.length>0?`<span class="blocks">阻断: `+i(e.blocks.join(`, `))+`</span>`:``)+`</div>`).join(``))}function K(e,t){E(e,t),O(e,t),P(e,t),U(e,t),W(e,t),G(e,t)}let q=!1;function J(){let e={boardOpen:!1},i=()=>{e.boardOpen=!0,o()},a=()=>{e.boardOpen=!1,o()},o=()=>{if(e.boardOpen){for(let e of n)document.documentElement.removeAttribute(e);document.documentElement.setAttribute(t,``),document.dispatchEvent(new CustomEvent(r,{detail:`dashboard-execution`}))}else document.documentElement.removeAttribute(t)};return{isActive:()=>e.boardOpen,toggle:()=>{e.boardOpen?a():i()},getSnapshot:()=>e,openBoard:i,closeBoard:a,toggleBoard:()=>{e.boardOpen?a():i()}}}function Y(e){let n,i,a=0,o,s,c=()=>{if(i!==void 0)return;let e=document.querySelector(`[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface`);e!==null&&(i=document.createElement(`div`),i.dataset.dshExecView=``,i.className=`dsh-exec-view`,e.appendChild(i),n=te(),i.appendChild(n.board),o=i.querySelector(`[data-role="refresh"]`)??void 0,o?.addEventListener(`click`,()=>{u()}),n.tasksBox.addEventListener(`click`,e=>{let t=e.target;if(s===void 0||n===void 0)return;let r=t.closest(`.dsh-exec-tab[data-dom]`);if(r!==null){z(r.dataset.dom??`all`),U(n,s);return}let i=t.closest(`.dsh-exec-tr[data-tk]`)?.dataset.tk;i!==void 0&&(R(i),U(n,s))}),u(!0))},l=new MutationObserver(()=>{c()});l.observe(document.body,{childList:!0,subtree:!0});async function u(e=!1){if(!q){q=!0;try{let e=await fetch(`/dashboard/api/board`,{headers:{Accept:`application/json`}});if(!e.ok)throw Error(`HTTP `+e.status);let t=await e.json();if(!t.success||t.data===void 0)throw Error(t.error??`API 返回失败`);if(n===void 0)return;s=t.data,K(n,s),n.meta.textContent=`刷新于 `+new Date().toLocaleTimeString()+` · 数据 `+(t.data.fetchedAt??``),n.banner.classList.remove(`show`)}catch(e){if(n===void 0)return;n.banner.innerHTML=`⚠ 无法连接看板 API：`+String(e&&e.message?e.message:e)+` — 请检查 :13080 与插件状态`,n.banner.classList.add(`show`)}finally{q=!1}}}let d=t=>{t.detail!==`dashboard-execution`&&e.getSnapshot().boardOpen&&e.closeBoard()},f=t=>{if(!e.getSnapshot().boardOpen)return;let n=t.target;n!==null&&n.closest(`[data-dsh-exec-view]`)===null&&n.closest(`[data-dsh-exec-entry]`)===null&&n.closest(`[class*="dsh-exec-foot"]`)===null&&e.closeBoard()};document.addEventListener(`click`,f,!0),document.addEventListener(r,d);let p=()=>{a!==0&&window.clearInterval(a),a=window.setInterval(()=>{u()},3e4)},m=()=>{a!==0&&(window.clearInterval(a),a=0)},h=()=>{document.hidden?m():(p(),u())};return document.addEventListener(`visibilitychange`,h),c(),p(),()=>{document.removeEventListener(`click`,f,!0),document.removeEventListener(r,d),document.removeEventListener(`visibilitychange`,h),l.disconnect(),m(),document.documentElement.removeAttribute(t),i?.remove(),i=void 0,n=void 0}}const X=`智能执行`,Z=`@pi-investment/dashboard-execution/footer-action.css`,Q=`dashboard-execution:open-board`;function ne(t){let{wide:n}=t,r=X;return(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-exec-foot wide`:`dsh-exec-foot rail`,title:r,"aria-label":r,onClick:()=>{console.log(`[dashboard-execution] footer action clicked — dispatching`,Q),window.dispatchEvent(new CustomEvent(Q,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-exec-foot-icon`,key:`i`},$),(0,e.createElement)(`span`,{className:`dsh-exec-foot-label`,key:`l`},r)]:(0,e.createElement)(`span`,{className:`dsh-exec-foot-icon`,key:`i`},$))}const $=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function re(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${Z}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=Z,e.textContent=`
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
`,document.head.appendChild(e)}function ie(){let e=`dsh-exec-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
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
`,(document.head??document.documentElement).appendChild(t)}const ae=[`slots`];function oe(e){try{re(),ie(),window.__dshExecClient?.dispose();let t=J(),n=Y(t),r=e=>{let n=e.detail?.open;console.log(`[dashboard-execution] open-board event`,{open:n},`boardOpen:`,t.getSnapshot().boardOpen),n===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(Q,r),window.__dshExecClient={dispose:()=>{window.removeEventListener(Q,r),n(),t.closeBoard()}};let i=e.slots;i?i.inject(`sidebar.footer.action`,()=>i.register({name:`sidebar.footer.action`,id:`dashboard-execution`,order:100,label:X},ne)):console.warn(`[dashboard-execution] ctx.slots unavailable (inject missing "slots")`)}catch(e){console.error(`[dashboard-execution] client half failed to start:`,e)}}exports.apply=oe,exports.inject=ae,exports.name=`@pi-investment/dashboard-execution/client`;