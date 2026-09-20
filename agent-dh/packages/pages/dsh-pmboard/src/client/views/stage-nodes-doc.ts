/**
 * 文档 / UI / 分析节点专属内容渲染（REQ-47939a t11 机械拆分，属 stage-panel 节点内容域）。
 *
 * @module dsh-pmboard/client/views/stage-nodes-doc
 */
import { esc } from '../html.js'
import type { TaskRecord } from '../types.ts'

/* ------------------------------------------------------------------ 其他节点类型占位 */

export function renderDocContent(task: TaskRecord): string {
  // 从 executions.evidence 提取文档文件
  const lastExec = task.executions[task.executions.length - 1]
  const docFiles: string[] = []
  const apis: string[] = []
  let completeness = { defined: 0, total: 0 }

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析文档文件 "docs/api/auth.md"
      if (ev.match(/\.(md|txt|pdf|html)$/i)) {
        docFiles.push(ev)
      }

      // 解析 API 端点 "POST /api/auth/login"
      if (ev.match(/^(GET|POST|PUT|DELETE|PATCH)\s+\//)) {
        apis.push(ev)
      }

      // 解析完成度 "3/5 sections completed"
      const compMatch = ev.match(/(\d+)\/(\d+)\s*.*?completed/i)
      if (compMatch) {
        completeness.defined = parseInt(compMatch[1], 10)
        completeness.total = parseInt(compMatch[2], 10)
      }
    })
  }

  // 从 description 中提取 API 列表（如果 evidence 中没有）
  if (apis.length === 0 && task.description) {
    const apiMatches = task.description.match(/(GET|POST|PUT|DELETE|PATCH)\s+\/[^\s\n]+/g)
    if (apiMatches) apis.push(...apiMatches)
  }

  const completionPct = completeness.total > 0
    ? Math.round((completeness.defined / completeness.total) * 100)
    : 0

  const docFilesHtml = docFiles.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📄 文档内容</h3>
      <ul class="dsh-pm-doc-list">
        ${docFiles.map(file => `<li><code>${esc(file)}</code></li>`).join('')}
      </ul>
    </div>` : ''

  const apisHtml = apis.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>🔗 关联接口（${apis.length} 个）</h3>
      <ul class="dsh-pm-api-list">
        ${apis.map(api => {
          const [method, path] = api.split(/\s+/)
          return `<li><span class="dsh-pm-api-method" data-method="${method}">${method}</span> <code>${esc(path)}</code></li>`
        }).join('')}
      </ul>
    </div>` : ''

  const completenessHtml = completeness.total > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📊 完成度</h3>
      <div class="dsh-pm-completeness">
        <div class="dsh-pm-completeness-bar">
          <span class="dsh-pm-completeness-label">整体进度</span>
          <span class="dsh-pm-completeness-value">${completionPct}%</span>
          <div class="dsh-pm-completeness-track">
            <div class="dsh-pm-completeness-fill" style="width: ${completionPct}%"></div>
          </div>
        </div>
        <div class="dsh-pm-completeness-detail">
          已完成 ${completeness.defined} / ${completeness.total} 部分
        </div>
      </div>
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📝 文档概览</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">文档文件</span>
          <span class="dsh-pm-stat-value">${docFiles.length} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">关联接口</span>
          <span class="dsh-pm-stat-value">${apis.length} 个</span>
        </div>
        ${completeness.total > 0 ? `
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">完成度</span>
          <span class="dsh-pm-stat-value">${completionPct}%</span>
        </div>` : ''}
      </div>
    </div>
    ${docFilesHtml}
    ${apisHtml}
    ${completenessHtml}`
}

export function renderUIContent(task: TaskRecord): string {
  // 从 executions.evidence 提取 UI 设计信息
  const lastExec = task.executions[task.executions.length - 1]
  const designFiles: string[] = []
  const components: string[] = []
  const specs: Record<string, string> = {}

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析设计文件 "design/login.fig" 或 "mockup.png"
      if (ev.match(/\.(fig|sketch|xd|png|jpg|svg)$/i)) {
        designFiles.push(ev)
      }

      // 解析组件 "Button, Input, LoginForm"
      if (ev.includes('component') || ev.includes('组件')) {
        const comps = ev.replace(/components?[:\s]*/i, '').split(/[,，]/).map(c => c.trim())
        components.push(...comps)
      }

      // 解析设计规范 "color: #3B82F6" / "font: Inter 16px"
      const specMatch = ev.match(/^(color|font|spacing|radius)[:\s]+(.+)/i)
      if (specMatch) {
        specs[specMatch[1].toLowerCase()] = specMatch[2].trim()
      }
    })
  }

  // 从 description 提取组件列表
  if (components.length === 0 && task.description) {
    const compMatch = task.description.match(/组件[：:]\s*([^\n]+)/)
    if (compMatch) {
      const comps = compMatch[1].split(/[,，、]/).map(c => c.trim())
      components.push(...comps)
    }
  }

  const designFilesHtml = designFiles.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>🖼️ 设计稿</h3>
      <ul class="dsh-pm-design-list">
        ${designFiles.map(file => `<li><code>${esc(file)}</code></li>`).join('')}
      </ul>
    </div>` : ''

  const specsHtml = Object.keys(specs).length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>🎯 设计规范</h3>
      <div class="dsh-pm-kv">
        ${Object.entries(specs).map(([key, value]) => `
          <span>${key === 'color' ? '主色调' : key === 'font' ? '字体' : key === 'spacing' ? '间距' : '圆角'}</span>
          <span><code>${esc(value)}</code></span>
        `).join('')}
      </div>
    </div>` : ''

  const componentsHtml = components.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📱 组件清单</h3>
      <ul class="dsh-pm-component-list">
        ${components.map(comp => `<li>${esc(comp)}</li>`).join('')}
      </ul>
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>🎨 UI 设计</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">设计文件</span>
          <span class="dsh-pm-stat-value">${designFiles.length} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">组件数量</span>
          <span class="dsh-pm-stat-value">${components.length} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">设计规范</span>
          <span class="dsh-pm-stat-value">${Object.keys(specs).length} 项</span>
        </div>
      </div>
    </div>
    ${designFilesHtml}
    ${specsHtml}
    ${componentsHtml}`
}

export function renderAnalysisContent(task: TaskRecord): string {
  // 从 executions.evidence 提取分析信息
  const lastExec = task.executions[task.executions.length - 1]
  let recommendation = ''
  const options: Array<{name: string; score: number}> = []
  const risks: string[] = []
  const references: string[] = []

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析推荐方案 "Recommended: JWT"
      if (ev.match(/^recommended?[:\s]+/i)) {
        recommendation = ev.replace(/^recommended?[:\s]+/i, '').trim()
      }

      // 解析选项评分 "JWT: 4/5" 或 "Session: ⭐⭐⭐"
      const scoreMatch = ev.match(/^(.+?)[:：]\s*(?:(\d+)\/5|([⭐★]+))/)
      if (scoreMatch) {
        const name = scoreMatch[1].trim()
        const score = scoreMatch[2] ? parseInt(scoreMatch[2], 10) : (scoreMatch[3]?.length || 0)
        options.push({ name, score })
      }

      // 解析风险点 "Risk: token leakage"
      if (ev.match(/^risk[:\s]+/i)) {
        risks.push(ev.replace(/^risk[:\s]+/i, '').trim())
      }

      // 解析参考资料（URL）
      if (ev.match(/^https?:\/\//)) {
        references.push(ev)
      }
    })
  }

  // 从 description 提取推荐和风险
  if (!recommendation && task.description) {
    const recMatch = task.description.match(/推荐[方案]?[：:]\s*([^\n]+)/)
    if (recMatch) recommendation = recMatch[1].trim()
  }

  const optionsHtml = options.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📊 方案对比</h3>
      <div class="dsh-pm-options">
        ${options.map(opt => {
          const stars = '⭐'.repeat(opt.score) + '☆'.repeat(5 - opt.score)
          return `
            <div class="dsh-pm-option">
              <span class="dsh-pm-option-name">${esc(opt.name)}</span>
              <span class="dsh-pm-option-score">${stars}</span>
            </div>`
        }).join('')}
      </div>
    </div>` : ''

  const recommendationHtml = recommendation ? `
    <div class="dsh-pm-detail-section">
      <h3>✅ 推荐方案</h3>
      <div class="dsh-pm-recommendation">
        <div class="dsh-pm-recommendation-title">${esc(recommendation)}</div>
      </div>
    </div>` : ''

  const risksHtml = risks.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>⚠️ 风险点（${risks.length} 项）</h3>
      <ul class="dsh-pm-risk-list">
        ${risks.map(risk => `<li>${esc(risk)}</li>`).join('')}
      </ul>
    </div>` : ''

  const referencesHtml = references.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📚 参考资料</h3>
      <ul class="dsh-pm-reference-list">
        ${references.map(ref => `<li><a href="${esc(ref)}" target="_blank" rel="noopener">${esc(ref)}</a></li>`).join('')}
      </ul>
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>🔍 分析结果</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">对比方案</span>
          <span class="dsh-pm-stat-value">${options.length} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">风险点</span>
          <span class="dsh-pm-stat-value">${risks.length} 项</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">参考资料</span>
          <span class="dsh-pm-stat-value">${references.length} 个</span>
        </div>
      </div>
    </div>
    ${recommendationHtml}
    ${optionsHtml}
    ${risksHtml}
    ${referencesHtml}`
}
