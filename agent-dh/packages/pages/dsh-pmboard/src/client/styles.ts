/**
 * 项目看板 client 样式 —— 泳道 / 详情 / 待归类 / DAG。
 * 类前缀 dsh-pm-（与 shell 隔离）；隐藏规则对齐 taskboard/execution 模式。
 *
 * REQ-47939a t12：原 1886 行单文件已按连续区段分层到 styles/*.ts；
 * 本文件按**原物理顺序**拼接（拼接结果与拆分前逐字节一致），注入接口不变。
 */
import { BASE_CSS } from './styles/base.ts'
import { BOARD_CSS } from './styles/board.ts'
import { DETAIL_CSS } from './styles/detail.ts'
import { FILES_CSS } from './styles/files.ts'
import { PANEL_CSS } from './styles/panel.ts'
import { TOKEN_CSS } from './styles/token.ts'
import { MARKS_CSS } from './styles/marks.ts'
import { SUBTASK_CSS } from './styles/subtask.ts'

const CSS_TAG = 'dsh-pmboard/styles.css'

// 拼接顺序 = 拆分前模板的物理顺序：base(9-399) → detail(400-768) → files(769-1147) → board(1148-1531) → panel(1532-1876)
// REQ-a33899 t6：TOKEN_CSS 追加在末尾（纯新增区段，不改既有选择器）
// REQ-d3e61a T-5：MARKS_CSS 追加在末尾（纯新增区段，不改既有选择器）
// REQ-4842fe t-3be71b：SUBTASK_CSS 追加在末尾（纯新增区段，不改既有选择器）
const CSS = BASE_CSS + DETAIL_CSS + FILES_CSS + BOARD_CSS + PANEL_CSS + TOKEN_CSS + MARKS_CSS + SUBTASK_CSS

export function injectStyles(): void {
  if (typeof document === 'undefined') return
  if (document.querySelector(`style[data-plugin-css="${CSS_TAG}"]`)) return
  const tag = document.createElement('style')
  tag.dataset.pluginCss = CSS_TAG
  tag.textContent = CSS
  document.head.appendChild(tag)
}
