/**
 * 项目看板视图 —— 数据到 innerHTML 的纯渲染（参照 holdings view.ts 模式）。
 * 三层：泳道看板（需求状态列）/ 需求详情（任务 DAG + 任务列 + 评论）/ 待归类区。
 * 所有用户文本经 esc() 转义；交互经 data-action 属性委派到 board-mount。
 *
 * REQ-47939a t11：原 2579 行单文件已按视图区机械拆分为 views/* 与 render/dom-utils.ts；
 * 本文件仅做汇总再导出，对外导出符号集合与拆分前完全一致（DOM/类名/订阅方式均未变）。
 *
 * @module dsh-pmboard/client/view
 */
export { LANE_STATUSES, NO_ARCHIVED, buildEmpty, buildError } from './render/dom-utils.ts'
export { toReqCards, buildBoard, LIST_PAGE_SIZES, LIST_PAGE_SIZE_DEFAULT, defaultListDirFor, buildListView } from './views/board.ts'
export { buildReqDetail } from './views/stage-detail.ts'
export { buildTaskDetail } from './views/stage-panel.ts'
export { buildTasksPage } from './views/timeline.ts'
export type { BoardViewKind, ListSortKey, ListSortDir, ListViewOpts } from './views/board.ts'
