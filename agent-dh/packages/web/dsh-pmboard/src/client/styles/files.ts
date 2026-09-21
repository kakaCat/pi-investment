/**
 * pmboard 样式分片 · files（REQ-47939a t12 从 styles.ts 机械拆分，原文件 769-1147 行）。
 * 文档层：文档节点/UI 节点/分析节点 + 需求详情进度条/折叠/Tab + Markdown + 文档记录 + 文档缺失 + 视图切换 + 列表视图/工具条/分页。
 * 注意：本文件是原单文件 CSS 模板的**连续区段**，由 styles.ts 按原物理顺序拼接，拼接结果与拆分前逐字节一致。
 */
export const FILES_CSS = `/* 文档节点 - 文档列表 */
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
.dsh-pm-status-badge[data-status="design"] { background: rgba(240,160,32,.20); color: #a86a00; }
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

/* ---- 分页（render/pagination 的 tpg-* 类）---- */
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

`
