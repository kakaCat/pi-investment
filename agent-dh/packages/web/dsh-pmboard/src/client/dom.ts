/**
 * Mount-point helpers for the project board (dsh-pmboard).
 * 挂载点常量与页面标识常量（MainPanelId 同源）。
 *
 * @module dsh-pmboard/client/dom
 */

export const ENTRY_SELECTOR = '[data-dsh-pm-entry]'
export const BOARD_VIEW_SELECTOR = '[data-dsh-pm-view]'
export const PANEL_NAME = 'dsh-pmboard'
/**
 * main 插槽 key 与 sidebar.panellist 条目 id 的**同源身份**（MainPanelId，REQ-260928185112-e20d FR-1）。
 * 只是 PANEL_NAME 的语义别名：两端引用同一个常量，杜绝「两份真相」漂移。
 */
export const PANEL_ID = PANEL_NAME
export const PANEL_LABEL = '项目看板'
