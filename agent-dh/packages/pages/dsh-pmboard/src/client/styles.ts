/**
 * 项目看板 client 样式 —— 泳道 / 详情 / 待归类 / DAG。
 * 类前缀 dsh-pm-（与 shell 隔离）；隐藏规则对齐 taskboard/execution 模式。
 */

const CSS_TAG = 'dsh-pmboard/styles.css'

const CSS = `
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
`

export function injectStyles(): void {
  if (typeof document === 'undefined') return
  if (document.querySelector(`style[data-plugin-css="${CSS_TAG}"]`)) return
  const tag = document.createElement('style')
  tag.dataset.pluginCss = CSS_TAG
  tag.textContent = CSS
  document.head.appendChild(tag)
}
