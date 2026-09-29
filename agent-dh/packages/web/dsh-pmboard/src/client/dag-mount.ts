/**
 * DAG Canvas 挂载辅助
 * @module dsh-pmboard/client/dag-mount
 */
import { mountDagCanvas, type DagTaskLike } from './views/dag-view.js'

/**
 * 挂载 DAG Canvas（面板 HTML 进 DOM 之后调用）：按 canvasId 查找画布并初始化。
 * mountDagCanvas 自身幂等（先释放**同名**旧实例，画布已被换掉或顶层卡为空时同样回收），
 * SSE 每次重绘后重复调用是安全的。
 *
 * @param tasks 需求全量任务（含子卡；折叠为卡片层由 mountDagCanvas 负责）
 * @param ready 队列 ready[]（BoardState.ready[reqId]）；不传则统计条按「推导」标注
 * @param canvasId 画布 id；缺省 = 需求详情的 #dag-canvas，会话面板传 PANEL_DAG_CANVAS_ID
 */
export function tryMountDagCanvas(tasks: DagTaskLike[], ready?: readonly string[], canvasId: string = 'dag-canvas'): void {
  // 延迟执行，确保 DOM 已渲染
  requestAnimationFrame(() => {
    if (document.getElementById(canvasId) === null) return
    try {
      mountDagCanvas(tasks, ready, canvasId)
    } catch (err) {
      console.error('[DAG] Failed to mount canvas:', err)
    }
  })
}
