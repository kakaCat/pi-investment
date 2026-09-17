/**
 * 项目看板 client 样式 —— 泳道 / 详情 / 待归类 / DAG。
 * 类前缀 dsh-pm-（与 shell 隔离）；隐藏规则对齐 taskboard/execution 模式。
 */

const CSS_TAG = 'dsh-pmboard/styles.css'

const CSS = `
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
`

export function injectStyles(): void {
  if (typeof document === 'undefined') return
  if (document.querySelector(`style[data-plugin-css="${CSS_TAG}"]`)) return
  const tag = document.createElement('style')
  tag.dataset.pluginCss = CSS_TAG
  tag.textContent = CSS
  document.head.appendChild(tag)
}
