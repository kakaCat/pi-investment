/**
 * pmboard 样式分片 · detail（REQ-47939a t12 从 styles.ts 机械拆分，原文件 400-768 行）。
 * 详情层：拆分计划 + 时间线 + 甘特图 + 任务页 + 节点差异化展示（专属内容/统计卡/拆分/实施/测试/评审/合并节点）。
 * 注意：本文件是原单文件 CSS 模板的**连续区段**，由 styles.ts 按原物理顺序拼接，拼接结果与拆分前逐字节一致。
 */
export const DETAIL_CSS = `/* ---- 拆分计划（plan mode） ---- */
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
.dsh-pm-tl-row[data-status="design"] { border-left-color: #c2255c; }
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

`
