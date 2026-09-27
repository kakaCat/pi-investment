/**
 * 追溯关系事件处理器集成（REQ-260926140539-457b FR-6）。
 *
 * 由 board-mount 的「🔗 追溯」Tab 切到时调用：从 stageDetail.body 提取
 * traceability / coverage，渲染进 #dsh-pm-traceability-container，并绑定节点点击联动高亮。
 *
 * 本文件相对前序版本修了四处：
 *  1. 去掉 dynamic import —— 它与顶部静态 import 并存会触发构建告警
 *     INEFFECTIVE_DYNAMIC_IMPORT，且多一层微任务延迟使渲染时序不确定；
 *  2. 监听器改为**幂等绑定**（WeakSet）—— 原实现每次渲染都 addEventListener，
 *     反复切 Tab 会叠加多个处理器，一次点击触发 N 次高亮；
 *  3. 最新追溯数据用 WeakMap 持有 —— 原实现把 traceability 捕获进闭包，
 *     切换需求后监听器仍用**第一次**的数据做关联查找，高亮会错；
 *  4. **覆盖度形状归一**（toCoverageContainer）—— 装配器按节点只挂"自己那一段"
 *     覆盖度（扁平对象），而视图要 { design?, implementation?, testing? } 容器；
 *     原实现直接透传 → 三个分支全不命中 → 覆盖度卡片永不显示。
 */

import {
  renderTraceabilityView,
  handleTraceSelect,
  type TraceabilityData,
  type CoverageData,
} from './views/traceability-view.js'

/** 已绑定点击委托的容器（幂等保证）。 */
const interactionBound = new WeakSet<HTMLElement>()

/** 各容器当前有效的追溯数据（渲染后更新，供唯一监听器读取最新值）。 */
const currentTraceability = new WeakMap<HTMLElement, TraceabilityData>()

/** 覆盖度容器里的三个键。 */
type CoverageKey = 'design' | 'implementation' | 'testing'

/**
 * 判定扁平覆盖度属于哪一类：优先按**节点**（契约：设计→design、拆分/实施→implementation、
 * 验收→testing），节点缺失时按字段签名兜底。
 */
export function coverageKeyOf(stage: string | undefined, o: Record<string, unknown>): CoverageKey | undefined {
  if (stage === 'design' || stage === 'brainstorming') return 'design'
  if (stage === 'decomposing' || stage === 'implementing') return 'implementation'
  if (stage === 'accepting') return 'testing'

  if ('total_designs' in o || 'covered_designs' in o) return 'implementation'
  if ('total_tasks' in o || 'tested_tasks' in o || 'untested' in o) return 'testing'
  if ('total_frs' in o || 'covered_frs' in o) return 'design'
  return undefined
}

/**
 * 把 body.coverage 归一成视图要的 { design?, implementation?, testing? } 容器。
 */
export function toCoverageContainer(raw: unknown, stage: string | undefined): CoverageData | undefined {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return undefined
  const o = raw as Record<string, unknown>

  // 已是容器形式（含任一类键）→ 原样使用
  if (o['design'] !== undefined || o['implementation'] !== undefined || o['testing'] !== undefined) {
    return o as unknown as CoverageData
  }

  const key = coverageKeyOf(stage, o)
  return key === undefined ? undefined : ({ [key]: o } as unknown as CoverageData)
}

/**
 * 初始化追溯关系交互。幂等：同一容器只绑定一次点击委托。
 */
export function initTraceabilityInteraction(
  container: HTMLElement,
  traceability?: TraceabilityData,
): void {
  if (traceability === undefined) return

  // 无论是否首次绑定，都记下最新数据（切换需求后监听器据此用新值）
  currentTraceability.set(container, traceability)
  if (interactionBound.has(container)) return
  interactionBound.add(container)

  container.addEventListener('click', event => {
    const target = event.target as HTMLElement | null
    const node = target?.closest('[data-action="trace-select"]') as HTMLElement | null
    if (node === null) return

    const nodeType = node.dataset.type as 'fr' | 'design' | 'task' | 'test' | undefined
    const nodeId = node.dataset.id
    if (nodeType === undefined || nodeId === undefined || nodeId.length === 0) return

    // 读「当前」数据，而不是绑定时的旧数据
    const latest = currentTraceability.get(container)
    if (latest === undefined) return
    handleTraceSelect(nodeType, nodeId, latest)
  })
}

/**
 * 更新追溯视图（API 数据返回后调用）。
 *
 * 无追溯数据时直接返回，不动 DOM —— 保持 FR-9「RTM 是增强层，缺失不打断主流程」的降级语义。
 */
export function updateTraceabilityView(stageDetail: any, container: HTMLElement): void {
  const traceability = stageDetail?.body?.traceability as TraceabilityData | undefined
  const coverage = toCoverageContainer(stageDetail?.body?.coverage, stageDetail?.stage)
  if (traceability === undefined && coverage === undefined) return

  const traceContainer = container.querySelector<HTMLElement>('#dsh-pm-traceability-container')
  if (traceContainer === null) return

  traceContainer.innerHTML = renderTraceabilityView(traceability, coverage)

  // 委托绑在内层容器上（而非整个详情面板），作用域更小；容器元素本身在 innerHTML 重写中保留
  if (traceability !== undefined) initTraceabilityInteraction(traceContainer, traceability)
}
