/**
 * RTM 追溯关系可视化样式（REQ-260926140539-457b FR-6）。
 *
 * 由 styles/traceability.css 转换而来：本仓客户端样式约定是 styles/*.ts 导出 CSS 字符串、
 * 由 styles.ts 按物理顺序拼接后注入（不存在 .css 直接 import 的构建支持）。
 * 色板一律复用全站令牌 --dsw-* / --pm-*，不造第二套（原文件的 --vscode-* 全仓无定义）。
 */
export const TRACEABILITY_CSS = `
/**
 * RTM 追溯关系可视化样式（REQ-260926140539-457b FR-6）
 */

/* 追溯容器 */
.dsh-pm-traceability-container {
  padding: 16px;
}

/* 空状态 */
.dsh-pm-traceability-empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--dsw-text-secondary, #6b7280);
}

.dsh-pm-empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.dsh-pm-empty-text {
  font-size: 16px;
  margin-bottom: 8px;
  font-weight: 500;
}

.dsh-pm-empty-hint {
  font-size: 13px;
  opacity: 0.7;
}

/* 覆盖度摘要 */
.dsh-pm-coverage-summary {
  margin-bottom: 24px;
}

.dsh-pm-coverage-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
  margin-top: 12px;
}

.dsh-pm-coverage-card {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--dsw-border, #e5e7eb);
  background: var(--dsw-bg-primary, #ffffff);
}

.dsh-pm-coverage-card.dsh-pm-coverage-success {
  border-left: 4px solid #28a745;
}

.dsh-pm-coverage-card.dsh-pm-coverage-warning {
  border-left: 4px solid #ff9800;
}

.dsh-pm-coverage-card.dsh-pm-coverage-danger {
  border-left: 4px solid #dc3545;
}

.dsh-pm-coverage-title {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 8px;
  opacity: 0.8;
}

.dsh-pm-coverage-rate {
  font-size: 32px;
  font-weight: 600;
  margin-bottom: 4px;
}

.dsh-pm-coverage-success .dsh-pm-coverage-rate {
  color: #28a745;
}

.dsh-pm-coverage-warning .dsh-pm-coverage-rate {
  color: #ff9800;
}

.dsh-pm-coverage-danger .dsh-pm-coverage-rate {
  color: #dc3545;
}

.dsh-pm-coverage-detail {
  font-size: 13px;
  opacity: 0.7;
}

.dsh-pm-coverage-uncovered {
  margin-top: 8px;
  padding: 8px;
  background: rgba(220,53,69,.12);
  border-radius: 4px;
  font-size: 12px;
  color: #dc3545;
}

/* 追溯关系图 */
.dsh-pm-traceability-graph {
  margin-bottom: 24px;
}

.dsh-pm-trace-columns {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-top: 12px;
  margin-bottom: 12px;
}

.dsh-pm-trace-column {
  border: 1px solid var(--dsw-border, #e5e7eb);
  border-radius: 8px;
  overflow: hidden;
}

.dsh-pm-trace-column-header {
  padding: 12px;
  background: var(--dsw-bg-primary, #ffffff);
  border-bottom: 1px solid var(--dsw-border, #e5e7eb);
  font-weight: 500;
  font-size: 13px;
  text-align: center;
}

.dsh-pm-trace-nodes {
  padding: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.dsh-pm-trace-node {
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 4px;
  border: 1px solid var(--dsw-border, #e5e7eb);
  background: var(--dsw-bg-secondary, #f3f4f6);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 12px;
}

.dsh-pm-trace-node:hover {
  background: var(--dsw-hover, rgba(0,0,0,.04));
  border-color: var(--dsw-accent, #0969da);
}

.dsh-pm-trace-node.dsh-pm-trace-selected {
  background: var(--dsw-active, rgba(9,105,218,.10));
  border-color: var(--dsw-accent, #0969da);
  color: var(--dsw-text-primary, #1f2328);
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.dsh-pm-trace-node.dsh-pm-trace-related {
  background: var(--dsw-bg-secondary, #f3f4f6);
  border-color: var(--dsw-bg-secondary, #f3f4f6);
  opacity: 0.9;
}

.dsh-pm-trace-node-id {
  font-family: ui-monospace, monospace;
}

.dsh-pm-trace-hint {
  text-align: center;
  font-size: 13px;
  color: var(--dsw-text-secondary, #6b7280);
  padding: 12px;
  background: var(--dsw-bg-secondary, #f3f4f6);
  border-radius: 4px;
}

/* 追溯矩阵 */
.dsh-pm-traceability-matrix {
  margin-top: 24px;
}

.dsh-pm-fold {
  border: 1px solid var(--dsw-border, #e5e7eb);
  border-radius: 4px;
  margin-bottom: 12px;
  overflow: hidden;
}

.dsh-pm-fold summary {
  padding: 12px 16px;
  cursor: pointer;
  background: var(--dsw-bg-primary, #ffffff);
  user-select: none;
}

.dsh-pm-fold summary:hover {
  background: var(--dsw-hover, rgba(0,0,0,.04));
}

.dsh-pm-fold[open] summary {
  border-bottom: 1px solid var(--dsw-border, #e5e7eb);
}

.dsh-pm-trace-table {
  padding: 12px;
}

.dsh-pm-trace-row {
  display: flex;
  align-items: center;
  padding: 8px;
  margin-bottom: 8px;
  border-radius: 4px;
  background: var(--dsw-bg-primary, #ffffff);
  border: 1px solid var(--dsw-border, #e5e7eb);
}

.dsh-pm-trace-row:last-child {
  margin-bottom: 0;
}

.dsh-pm-trace-cell {
  padding: 0 8px;
}

.dsh-pm-trace-from {
  flex: 0 0 200px;
  font-weight: 500;
  color: var(--dsw-accent, #0969da);
}

.dsh-pm-trace-arrow {
  flex: 0 0 30px;
  text-align: center;
  opacity: 0.5;
}

.dsh-pm-trace-to {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.dsh-pm-trace-tag {
  display: inline-block;
  padding: 4px 8px;
  background: var(--dsw-bg-secondary, #f3f4f6);
  color: var(--dsw-text-primary, #1f2328);
  border-radius: 3px;
  font-size: 11px;
  font-family: ui-monospace, monospace;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .dsh-pm-trace-columns {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .dsh-pm-trace-columns {
    grid-template-columns: 1fr;
  }
  
  .dsh-pm-coverage-cards {
    grid-template-columns: 1fr;
  }
}
`
