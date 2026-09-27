/**
 * RTM 追溯关系可视化组件（REQ-260926140539-457b FR-6）
 * 
 * 实现双向绑定的追溯关系图：
 * - 点击 FR → 高亮对应的 Design / Task / Test
 * - 点击 Design → 高亮对应的 FR / Task
 * - 点击 Task → 高亮对应的 Design / Test
 * - 点击 Test → 高亮对应的 Task / FR
 * 
 * @module dsh-pmboard/client/views/traceability-view
 */

import { esc } from '../html.js'

/** 追溯数据结构 */
export interface TraceabilityData {
  /** FR → 设计章节 */
  fr_to_design?: Record<string, string[]>
  /** 设计章节 → 任务 */
  design_to_tasks?: Record<string, string[]>
  /** FR → 任务（跨级） */
  fr_to_tasks?: Record<string, string[]>
  /** 任务 → 测试 */
  task_to_tests?: Record<string, string[]>
  /** FR → 测试（跨级） */
  fr_to_tests?: Record<string, string[]>
}

/** 覆盖度数据结构 */
export interface CoverageData {
  design?: {
    total: number
    covered: number
    uncovered: string[]
    rate: number
    total_frs: number
    covered_frs: number
  }
  implementation?: {
    total: number
    covered: number
    uncovered: string[]
    rate: number
    total_designs: number
    covered_designs: number
  }
  testing?: {
    total_tasks: number
    tested_tasks: number
    untested: string[]
    rate: number
  }
}

/**
 * 渲染追溯关系可视化
 */
export function renderTraceabilityView(
  traceability?: TraceabilityData,
  coverage?: CoverageData
): string {
  if (!traceability) {
    return `
      <div class="dsh-pm-traceability-empty">
        <div class="dsh-pm-empty-icon">🔍</div>
        <div class="dsh-pm-empty-text">暂无追溯数据</div>
        <div class="dsh-pm-empty-hint">RTM 文件生成后将显示追溯关系</div>
      </div>`
  }

  return `
    <div class="dsh-pm-traceability-container">
      ${renderCoverageSummary(coverage)}
      ${renderTraceabilityGraph(traceability)}
      ${renderTraceabilityMatrix(traceability)}
    </div>`
}

/**
 * 渲染覆盖度摘要卡片
 */
function renderCoverageSummary(coverage?: CoverageData): string {
  if (!coverage) return ''

  const cards: string[] = []

  if (coverage.design) {
    const rate = coverage.design.rate
    const status = rate === 100 ? 'success' : rate >= 80 ? 'warning' : 'danger'
    cards.push(`
      <div class="dsh-pm-coverage-card dsh-pm-coverage-${status}">
        <div class="dsh-pm-coverage-title">🎨 设计覆盖度</div>
        <div class="dsh-pm-coverage-rate">${rate}%</div>
        <div class="dsh-pm-coverage-detail">${coverage.design.covered_frs}/${coverage.design.total_frs} FR 已覆盖</div>
        ${coverage.design.uncovered.length > 0 ? `<div class="dsh-pm-coverage-uncovered">未覆盖: ${coverage.design.uncovered.join(', ')}</div>` : ''}
      </div>`)
  }

  if (coverage.implementation) {
    const rate = coverage.implementation.rate
    const status = rate === 100 ? 'success' : rate >= 80 ? 'warning' : 'danger'
    cards.push(`
      <div class="dsh-pm-coverage-card dsh-pm-coverage-${status}">
        <div class="dsh-pm-coverage-title">⚙️ 实施覆盖度</div>
        <div class="dsh-pm-coverage-rate">${rate}%</div>
        <div class="dsh-pm-coverage-detail">${coverage.implementation.covered_designs}/${coverage.implementation.total_designs} 设计已实施</div>
        ${coverage.implementation.uncovered.length > 0 ? `<div class="dsh-pm-coverage-uncovered">未覆盖: ${coverage.implementation.uncovered.join(', ')}</div>` : ''}
      </div>`)
  }

  if (coverage.testing) {
    const rate = coverage.testing.rate
    const status = rate >= 80 ? 'success' : rate >= 60 ? 'warning' : 'danger'
    cards.push(`
      <div class="dsh-pm-coverage-card dsh-pm-coverage-${status}">
        <div class="dsh-pm-coverage-title">🧪 测试覆盖度</div>
        <div class="dsh-pm-coverage-rate">${rate}%</div>
        <div class="dsh-pm-coverage-detail">${coverage.testing.tested_tasks}/${coverage.testing.total_tasks} 任务已测试</div>
        ${coverage.testing.untested.length > 0 ? `<div class="dsh-pm-coverage-uncovered">未测试: ${coverage.testing.untested.join(', ')}</div>` : ''}
      </div>`)
  }

  if (cards.length === 0) return ''

  return `
    <div class="dsh-pm-coverage-summary">
      <h3 class="dsh-pm-section-title">📊 覆盖度概览</h3>
      <div class="dsh-pm-coverage-cards">${cards.join('')}</div>
    </div>`
}

/**
 * 渲染追溯关系图（可视化）
 */
function renderTraceabilityGraph(traceability: TraceabilityData): string {
  // 收集所有节点
  const frs = new Set<string>()
  const designs = new Set<string>()
  const tasks = new Set<string>()
  const tests = new Set<string>()

  // 从映射中提取节点
  if (traceability.fr_to_design) {
    Object.keys(traceability.fr_to_design).forEach(fr => frs.add(fr))
    Object.values(traceability.fr_to_design).forEach(designList => {
      designList.forEach(d => designs.add(d))
    })
  }

  if (traceability.design_to_tasks) {
    Object.keys(traceability.design_to_tasks).forEach(d => designs.add(d))
    Object.values(traceability.design_to_tasks).forEach(taskList => {
      taskList.forEach(t => tasks.add(t))
    })
  }

  if (traceability.task_to_tests) {
    Object.keys(traceability.task_to_tests).forEach(t => tasks.add(t))
    Object.values(traceability.task_to_tests).forEach(testList => {
      testList.forEach(test => tests.add(test))
    })
  }

  return `
    <div class="dsh-pm-traceability-graph">
      <h3 class="dsh-pm-section-title">🔗 追溯关系图（双向绑定）</h3>
      <div class="dsh-pm-trace-columns">
        <div class="dsh-pm-trace-column">
          <div class="dsh-pm-trace-column-header">📝 功能需求 (${frs.size})</div>
          <div class="dsh-pm-trace-nodes">
            ${Array.from(frs).map(fr => `
              <div class="dsh-pm-trace-node" data-type="fr" data-id="${esc(fr)}" data-action="trace-select">
                <span class="dsh-pm-trace-node-id">${esc(fr)}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="dsh-pm-trace-column">
          <div class="dsh-pm-trace-column-header">🎨 设计章节 (${designs.size})</div>
          <div class="dsh-pm-trace-nodes">
            ${Array.from(designs).map(design => `
              <div class="dsh-pm-trace-node" data-type="design" data-id="${esc(design)}" data-action="trace-select">
                <span class="dsh-pm-trace-node-id">${esc(design)}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="dsh-pm-trace-column">
          <div class="dsh-pm-trace-column-header">⚙️ 实施任务 (${tasks.size})</div>
          <div class="dsh-pm-trace-nodes">
            ${Array.from(tasks).map(task => `
              <div class="dsh-pm-trace-node" data-type="task" data-id="${esc(task)}" data-action="trace-select">
                <span class="dsh-pm-trace-node-id">${esc(task)}</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="dsh-pm-trace-column">
          <div class="dsh-pm-trace-column-header">🧪 测试用例 (${tests.size})</div>
          <div class="dsh-pm-trace-nodes">
            ${Array.from(tests).map(test => `
              <div class="dsh-pm-trace-node" data-type="test" data-id="${esc(test)}" data-action="trace-select">
                <span class="dsh-pm-trace-node-id">${esc(test)}</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
      <div class="dsh-pm-trace-hint">💡 点击任意节点查看其追溯关系</div>
    </div>`
}

/**
 * 渲染追溯关系矩阵（详细表格）
 */
function renderTraceabilityMatrix(traceability: TraceabilityData): string {
  const sections: string[] = []

  // FR → Design 映射
  if (traceability.fr_to_design && Object.keys(traceability.fr_to_design).length > 0) {
    sections.push(`
      <details class="dsh-pm-fold">
        <summary class="dsh-pm-section-title">📝 FR → 设计章节</summary>
        <div class="dsh-pm-trace-table">
          ${Object.entries(traceability.fr_to_design).map(([fr, designs]) => `
            <div class="dsh-pm-trace-row">
              <div class="dsh-pm-trace-cell dsh-pm-trace-from">${esc(fr)}</div>
              <div class="dsh-pm-trace-cell dsh-pm-trace-arrow">→</div>
              <div class="dsh-pm-trace-cell dsh-pm-trace-to">
                ${designs.map(d => `<span class="dsh-pm-trace-tag">${esc(d)}</span>`).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      </details>`)
  }

  // Design → Task 映射
  if (traceability.design_to_tasks && Object.keys(traceability.design_to_tasks).length > 0) {
    sections.push(`
      <details class="dsh-pm-fold">
        <summary class="dsh-pm-section-title">🎨 设计章节 → 任务</summary>
        <div class="dsh-pm-trace-table">
          ${Object.entries(traceability.design_to_tasks).map(([design, tasks]) => `
            <div class="dsh-pm-trace-row">
              <div class="dsh-pm-trace-cell dsh-pm-trace-from">${esc(design)}</div>
              <div class="dsh-pm-trace-cell dsh-pm-trace-arrow">→</div>
              <div class="dsh-pm-trace-cell dsh-pm-trace-to">
                ${tasks.map(t => `<span class="dsh-pm-trace-tag">${esc(t)}</span>`).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      </details>`)
  }

  // Task → Test 映射
  if (traceability.task_to_tests && Object.keys(traceability.task_to_tests).length > 0) {
    sections.push(`
      <details class="dsh-pm-fold">
        <summary class="dsh-pm-section-title">⚙️ 任务 → 测试用例</summary>
        <div class="dsh-pm-trace-table">
          ${Object.entries(traceability.task_to_tests).map(([task, tests]) => `
            <div class="dsh-pm-trace-row">
              <div class="dsh-pm-trace-cell dsh-pm-trace-from">${esc(task)}</div>
              <div class="dsh-pm-trace-cell dsh-pm-trace-arrow">→</div>
              <div class="dsh-pm-trace-cell dsh-pm-trace-to">
                ${tests.map(t => `<span class="dsh-pm-trace-tag">${esc(t)}</span>`).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      </details>`)
  }

  if (sections.length === 0) {
    return '<div class="dsh-pm-empty">暂无追溯映射数据</div>'
  }

  return `
    <div class="dsh-pm-traceability-matrix">
      <h3 class="dsh-pm-section-title">📋 追溯矩阵</h3>
      ${sections.join('')}
    </div>`
}

/**
 * 处理追溯节点点击事件（双向绑定高亮）
 */
export function handleTraceSelect(
  nodeType: 'fr' | 'design' | 'task' | 'test',
  nodeId: string,
  traceability: TraceabilityData
) {
  // 清除所有高亮
  document.querySelectorAll('.dsh-pm-trace-node').forEach(node => {
    node.classList.remove('dsh-pm-trace-selected', 'dsh-pm-trace-related')
  })

  // 高亮选中节点
  const selectedNode = document.querySelector(`[data-type="${nodeType}"][data-id="${nodeId}"]`)
  if (selectedNode) {
    selectedNode.classList.add('dsh-pm-trace-selected')
  }

  // 根据节点类型高亮相关节点
  const relatedIds = getRelatedNodes(nodeType, nodeId, traceability)
  
  relatedIds.forEach(({ type, id }) => {
    const relatedNode = document.querySelector(`[data-type="${type}"][data-id="${id}"]`)
    if (relatedNode) {
      relatedNode.classList.add('dsh-pm-trace-related')
    }
  })
}

/**
 * 获取相关联的节点（双向查找）
 */
function getRelatedNodes(
  nodeType: 'fr' | 'design' | 'task' | 'test',
  nodeId: string,
  traceability: TraceabilityData
): Array<{ type: string; id: string }> {
  const related: Array<{ type: string; id: string }> = []

  switch (nodeType) {
    case 'fr':
      // FR → Design
      if (traceability.fr_to_design?.[nodeId]) {
        traceability.fr_to_design[nodeId].forEach(d => {
          related.push({ type: 'design', id: d })
        })
      }
      // FR → Task (跨级)
      if (traceability.fr_to_tasks?.[nodeId]) {
        traceability.fr_to_tasks[nodeId].forEach(t => {
          related.push({ type: 'task', id: t })
        })
      }
      // FR → Test (跨级)
      if (traceability.fr_to_tests?.[nodeId]) {
        traceability.fr_to_tests[nodeId].forEach(t => {
          related.push({ type: 'test', id: t })
        })
      }
      break

    case 'design':
      // Design ← FR (反向)
      if (traceability.fr_to_design) {
        Object.entries(traceability.fr_to_design).forEach(([fr, designs]) => {
          if (designs.includes(nodeId)) {
            related.push({ type: 'fr', id: fr })
          }
        })
      }
      // Design → Task
      if (traceability.design_to_tasks?.[nodeId]) {
        traceability.design_to_tasks[nodeId].forEach(t => {
          related.push({ type: 'task', id: t })
        })
      }
      break

    case 'task':
      // Task ← Design (反向)
      if (traceability.design_to_tasks) {
        Object.entries(traceability.design_to_tasks).forEach(([design, tasks]) => {
          if (tasks.includes(nodeId)) {
            related.push({ type: 'design', id: design })
          }
        })
      }
      // Task ← FR (反向跨级)
      if (traceability.fr_to_tasks) {
        Object.entries(traceability.fr_to_tasks).forEach(([fr, tasks]) => {
          if (tasks.includes(nodeId)) {
            related.push({ type: 'fr', id: fr })
          }
        })
      }
      // Task → Test
      if (traceability.task_to_tests?.[nodeId]) {
        traceability.task_to_tests[nodeId].forEach(t => {
          related.push({ type: 'test', id: t })
        })
      }
      break

    case 'test':
      // Test ← Task (反向)
      if (traceability.task_to_tests) {
        Object.entries(traceability.task_to_tests).forEach(([task, tests]) => {
          if (tests.includes(nodeId)) {
            related.push({ type: 'task', id: task })
          }
        })
      }
      // Test ← FR (反向跨级)
      if (traceability.fr_to_tests) {
        Object.entries(traceability.fr_to_tests).forEach(([fr, tests]) => {
          if (tests.includes(nodeId)) {
            related.push({ type: 'fr', id: fr })
          }
        })
      }
      break
  }

  return related
}
