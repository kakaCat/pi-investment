/**
 * pmboard 样式分片 · board（REQ-47939a t12 从 styles.ts 机械拆分，原文件 1148-1531 行）。
 * 看板层：进度点/Tab 内容区 + 当前阶段高亮卡/统计卡 + 验收泳道置灰 + 会话内联流程图/详情面板 + 产物 chips 与确认按钮。
 * 注意：本文件是原单文件 CSS 模板的**连续区段**，由 styles.ts 按原物理顺序拼接，拼接结果与拆分前逐字节一致。
 */
export const BOARD_CSS = `/* Tab 内容区 */
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
.dsh-pm-stage-panel[data-stage="design"] { --pm-stage: var(--pm-c-design); }
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
.dsh-pm-stage-panel[data-stage="design"] .dsh-pm-stage-label::before { content: '📐'; }
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

/* ---- 需求卡片高亮动画（跳转定位时使用；REQ-f0579a t5 从 base.ts 移入：base 超 400 行门禁） ---- */
@keyframes highlight-flash {
  0% { box-shadow: 0 0 0 0 rgba(74,125,255,.6); }
  50% { box-shadow: 0 0 20px 4px rgba(74,125,255,.4); }
  100% { box-shadow: 0 0 0 0 rgba(74,125,255,0); }
}
.dsh-pm-card.highlight-flash {
  animation: highlight-flash 2s ease-out;
}
`
