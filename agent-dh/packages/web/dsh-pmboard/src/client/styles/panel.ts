/**
 * pmboard 样式分片 · panel（REQ-47939a t12 从 styles.ts 机械拆分，原文件 1532-1876 行）。
 * 面板层：产物追溯链 + 任务/执行行 + 节点时间线 + 验收/归档节点 + 看板详情阶段导航 + 单节点工作记录 + markdown（含 wrap 哨兵）。
 * 注意：本文件是原单文件 CSS 模板的**连续区段**，由 styles.ts 按原物理顺序拼接，拼接结果与拆分前逐字节一致。
 */
export const PANEL_CSS = `/* 文件不存在的文档按钮（board-mount 运行时加 .dsh-pm-doc-missing） */
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

/* 设计节点：计划徽标 + 时间 */
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
