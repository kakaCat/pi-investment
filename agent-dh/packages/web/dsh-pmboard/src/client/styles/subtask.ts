/**
 * 子卡链与自动链控制面样式（REQ-4842fe t-3be71b）——纯新增区段，不改既有选择器。
 * 四态徽标色与节点状态色同源（运行中=进行中蓝 / 已暂停=灰 / 熔断=红 / 手动=浅灰）。
 */
export const SUBTASK_CSS = `
/* ---- 自动链徽标（运行中/已暂停/熔断/手动）---- */
.dsh-pm-auto-badge { display: inline-flex; align-items: center; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; white-space: nowrap; }
.dsh-pm-auto-badge[data-auto="running"] { background: rgba(74,125,255,.14); color: #4a7dff; }
.dsh-pm-auto-badge[data-auto="paused"] { background: rgba(156,163,175,.18); color: #6b7280; }
.dsh-pm-auto-badge[data-auto="breaker"] { background: rgba(220,53,69,.14); color: #dc3545; }
.dsh-pm-auto-badge[data-auto="manual"] { background: rgba(156,163,175,.10); color: #9ca3af; font-weight: 500; }
.dsh-pm-auto-controls { display: flex; gap: 6px; margin-top: 6px; }
.dsh-pm-card-substat { font-size: 11px; color: var(--dsw-text-secondary, #666); margin-top: 2px; }

/* ---- 子卡链（父卡下，原生 details 折叠）---- */
.dsh-pm-subtasks { margin-top: 6px; border-top: 1px dashed var(--pm-line); padding-top: 6px; }
.dsh-pm-subtasks > summary { cursor: pointer; font-size: 11px; color: var(--dsw-text-secondary, #666); user-select: none; list-style: revert; }
.dsh-pm-subtask { display: flex; align-items: center; gap: 6px; padding: 3px 0 3px 4px; font-size: 12px; }
.dsh-pm-subtask:hover { background: var(--dsw-bg-secondary, #f9fafb); }
.dsh-pm-subtask-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--dsw-text-primary, #333); }
.dsh-pm-stage-badge { padding: 1px 6px; border-radius: 4px; font-size: 10px; background: rgba(74,125,255,.10); color: #4a7dff; white-space: nowrap; }
.dsh-pm-subtask-attempt { font-size: 10px; color: #dc3545; }
.dsh-pm-subtask-status { font-size: 10px; color: var(--dsw-text-secondary, #666); }
.dsh-pm-subtask-status[data-status="done"] { color: #28a745; }
.dsh-pm-subtask-status[data-status="in_progress"] { color: #4a7dff; }
.dsh-pm-subcount { font-size: 10px; color: var(--dsw-text-secondary, #666); }
.dsh-pm-manual-chip { margin-left: 6px; padding: 0 5px; border-radius: 4px; font-size: 10px; background: rgba(156,163,175,.14); color: #9ca3af; }
.dsh-pm-task.is-parent { border-left: 2px solid rgba(74,125,255,.45); }
`;
