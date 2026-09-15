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
.dsh-pm-markdown { font-size: 14px; line-height: 1.65; color: var(--dsw-text-secondary, #555); word-break: break-word; }
.dsh-pm-markdown p { margin: 0 0 8px; }
.dsh-pm-markdown p:last-child { margin-bottom: 0; }
.dsh-pm-markdown h1, .dsh-pm-markdown h2, .dsh-pm-markdown h3,
.dsh-pm-markdown h4, .dsh-pm-markdown h5, .dsh-pm-markdown h6 {
  margin: 14px 0 6px; color: var(--dsw-text-primary, #333); font-weight: 600; line-height: 1.3;
}
.dsh-pm-markdown h1 { font-size: 19px; }
.dsh-pm-markdown h2 { font-size: 17px; }
.dsh-pm-markdown h3 { font-size: 15px; }
.dsh-pm-markdown h4, .dsh-pm-markdown h5, .dsh-pm-markdown h6 { font-size: 14px; }
.dsh-pm-markdown ul, .dsh-pm-markdown ol { margin: 0 0 8px; padding-left: 22px; }
.dsh-pm-markdown li { margin: 3px 0; }
.dsh-pm-markdown li::marker { color: var(--dsw-text-secondary, #999); }
.dsh-pm-markdown code {
  background: rgba(128,128,128,.12); padding: 1px 6px; border-radius: 3px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12.5px;
  color: #c7254e;
}
.dsh-pm-markdown pre {
  background: rgba(128,128,128,.07); padding: 10px 12px; border-radius: 6px;
  overflow-x: auto; margin: 8px 0; line-height: 1.5;
}
.dsh-pm-markdown pre code { background: none; padding: 0; color: var(--dsw-text-primary, #333); font-size: 12.5px; }
.dsh-pm-markdown a { color: var(--dsw-accent, #4a7dff); text-decoration: none; }
.dsh-pm-markdown a:hover { text-decoration: underline; }
.dsh-pm-markdown strong { font-weight: 600; color: var(--dsw-text-primary, #333); }
.dsh-pm-markdown em { font-style: italic; }
.dsh-pm-markdown blockquote {
  margin: 8px 0; padding: 4px 12px; border-left: 3px solid var(--dsw-border, rgba(128,128,128,.3));
  color: var(--dsw-text-secondary, #777);
}
.dsh-pm-markdown hr { border: none; border-top: 1px solid var(--dsw-border, rgba(128,128,128,.15)); margin: 12px 0; }
.dsh-pm-detail-title { margin: 0 0 8px; font-size: 18px; font-weight: 600; color: var(--dsw-text-primary, #333); }

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

/* ---- 文档查看弹窗 ---- */
.dsh-pm-doc-modal-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,.3);
}
.dsh-pm-doc-modal {
  position: absolute; top: 0; right: 0; bottom: 0;
  width: min(720px, 82vw); height: 100%;
  border-radius: 0;
  background: var(--dsw-bg-primary, #fff);
  box-shadow: -6px 0 32px rgba(0,0,0,.18);
  display: flex; flex-direction: column; overflow: hidden;
}
.dsh-pm-doc-modal-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 12px 16px; border-bottom: 1px solid var(--dsw-border, rgba(128,128,128,.12));
}
.dsh-pm-doc-modal-title {
  font-family: ui-monospace, monospace; font-size: 13px;
  color: var(--dsw-text-primary, #333); word-break: break-all;
}
.dsh-pm-doc-modal-body {
  padding: 16px; overflow: auto; flex: 1;
}
.dsh-pm-doc-modal-body pre {
  margin: 0; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 13px;
  line-height: 1.6; white-space: pre-wrap; word-break: break-word;
  color: var(--dsw-text-primary, #333);
}

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

/* ---- 会话顶部需求进度（conversation.session.header.utilities 槽位）---- */
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
  color: var(--dsw-text-secondary, #999);
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

/* 流程图（纵向时间线）*/
.dsh-pm-flow { display: flex; align-items: stretch; gap: 0; overflow-x: auto; padding: 2px 0; }
.dsh-pm-flow-node { display: flex; flex-direction: column; align-items: center; gap: 3px; min-width: 56px; cursor: pointer; transition: all .2s ease; }
.dsh-pm-flow-node:hover { transform: translateY(-2px); }
.dsh-pm-flow-node[data-selected="true"] .dsh-pm-flow-dot {
  box-shadow: 0 0 0 3px rgba(74,125,255,.3);
  transform: scale(1.1);
}
.dsh-pm-flow-node[data-selected="true"] .dsh-pm-flow-label {
  font-weight: 700;
  color: #2f5fd0;
}
.dsh-pm-flow-dot {
  width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 11px; background: rgba(128,128,128,.18); color: var(--dsw-text-secondary, #888); border: none;
  transition: all .2s ease;
}
.dsh-pm-flow-node[data-state="done"] .dsh-pm-flow-dot { background: rgba(40,167,69,.9); color: #fff; }
.dsh-pm-flow-node[data-state="current"] .dsh-pm-flow-dot { background: #4a7dff; color: #fff; box-shadow: 0 0 0 3px rgba(74,125,255,.25); }
.dsh-pm-flow-label { font-size: 10px; color: var(--dsw-text-secondary, #999); white-space: nowrap; transition: all .2s ease; }
.dsh-pm-flow-node[data-state="done"] .dsh-pm-flow-label { color: #1e7e34; }
.dsh-pm-flow-node[data-state="current"] .dsh-pm-flow-label { color: #2f5fd0; font-weight: 600; }
.dsh-pm-flow-link { width: 14px; height: 2px; background: rgba(128,128,128,.22); margin-top: 9px; flex: none; }
.dsh-pm-flow-link[data-state="done"] { background: rgba(40,167,69,.55); }

.dsh-pm-cprog-task { display: flex; align-items: flex-start; gap: 7px; font-size: 12px; line-height: 1.45; }
.dsh-pm-cprog-task-ico { flex: none; }
.dsh-pm-cprog-task-body { min-width: 0; }
.dsh-pm-cprog-task-title { color: var(--dsw-text-primary, #333); }
.dsh-pm-cprog-task[data-status="done"] .dsh-pm-cprog-task-title { color: var(--dsw-text-secondary, #999); text-decoration: line-through; }
.dsh-pm-cprog-task-meta { font-size: 10px; color: var(--dsw-text-secondary, #aaa); }
.dsh-pm-cprog-tl { display: flex; flex-direction: column; gap: 5px; font-size: 11px; }
.dsh-pm-cprog-tl-row { display: flex; gap: 8px; align-items: baseline; }
.dsh-pm-cprog-tl-time { color: var(--dsw-text-secondary, #aaa); font-variant-numeric: tabular-nums; flex: none; }
.dsh-pm-cprog-tl-text { color: var(--dsw-text-primary, #444); }
.dsh-pm-cprog-empty { font-size: 12px; color: var(--dsw-text-secondary, #999); }
.dsh-pm-cprog-foot { display: flex; gap: 8px; }
`

export function injectStyles(): void {
  if (typeof document === 'undefined') return
  if (document.querySelector(`style[data-plugin-css="${CSS_TAG}"]`)) return
  const tag = document.createElement('style')
  tag.dataset.pluginCss = CSS_TAG
  tag.textContent = CSS
  document.head.appendChild(tag)
}
