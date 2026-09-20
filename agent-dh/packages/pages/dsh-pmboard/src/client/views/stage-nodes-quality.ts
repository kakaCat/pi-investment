/**
 * 测试 / 评审 / 合并节点专属内容渲染（REQ-47939a t11 机械拆分，属 stage-panel 节点内容域）。
 *
 * @module dsh-pmboard/client/views/stage-nodes-quality
 */
import { esc } from '../html.js'
import type { TaskRecord } from '../types.ts'
import { renderComments } from '../render/dom-utils.ts'

/* ------------------------------------------------------------------ 测试节点 */

export function renderTestContent(task: TaskRecord): string {
  // 从 executions.evidence 解析测试结果
  let total = 0, passed = 0, failed = 0, skipped = 0
  const failedCases: Array<{name: string; expected: string; actual: string; file: string}> = []

  const lastExec = task.executions[task.executions.length - 1]
  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析 "18 passed / 2 failed / 0 skipped"
      const match = ev.match(/(\d+)\s*passed.*?(\d+)\s*failed.*?(\d+)\s*skipped/i)
      if (match) {
        passed = parseInt(match[1], 10)
        failed = parseInt(match[2], 10)
        skipped = parseInt(match[3], 10)
        total = passed + failed + skipped
      }
    })
  }

  // 从 error 字段解析失败用例
  if (lastExec?.error) {
    const lines = lastExec.error.split('\n')
    lines.forEach(line => {
      const match = line.match(/(.+?):(\d+)\s*Expected:\s*(.+?)\s*Actual:\s*(.+)/)
      if (match) {
        failedCases.push({
          name: '测试用例',
          file: match[1] + ':' + match[2],
          expected: match[3],
          actual: match[4],
        })
      }
    })
  }

  const passRate = total > 0 ? ((passed / total) * 100).toFixed(1) : '0'

  const failedHtml = failedCases.length > 0 ? failedCases.map(c => `
    <div class="dsh-pm-test-fail">
      <div class="dsh-pm-test-fail-name">${esc(c.name)}</div>
      <div class="dsh-pm-test-fail-detail">
        <span>预期：<code>${esc(c.expected)}</code></span>
        <span>实际：<code>${esc(c.actual)}</code></span>
        <span>文件：<code>${esc(c.file)}</code></span>
      </div>
    </div>`).join('') : '<div class="dsh-pm-empty">所有测试通过</div>'

  // 覆盖率（从 evidence 提取）
  let stmtCov = 0, branchCov = 0, funcCov = 0, lineCov = 0
  if (lastExec?.evidence) {
    const covMatch = lastExec.evidence.find(ev => ev.includes('coverage'))
    if (covMatch) {
      const stmt = covMatch.match(/statements?:\s*(\d+)%/i)
      const branch = covMatch.match(/branches?:\s*(\d+)%/i)
      const func = covMatch.match(/functions?:\s*(\d+)%/i)
      const line = covMatch.match(/lines?:\s*(\d+)%/i)
      if (stmt) stmtCov = parseInt(stmt[1], 10)
      if (branch) branchCov = parseInt(branch[1], 10)
      if (func) funcCov = parseInt(func[1], 10)
      if (line) lineCov = parseInt(line[1], 10)
    }
  }

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📊 测试概况</h3>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">总计</span>
          <span class="dsh-pm-stat-value">${total} 个</span>
        </div>
        <div class="dsh-pm-stat dsh-pm-stat-success">
          <span class="dsh-pm-stat-label">通过</span>
          <span class="dsh-pm-stat-value">${passed} 个 (${passRate}%)</span>
        </div>
        <div class="dsh-pm-stat dsh-pm-stat-error">
          <span class="dsh-pm-stat-label">失败</span>
          <span class="dsh-pm-stat-value">${failed} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">跳过</span>
          <span class="dsh-pm-stat-value">${skipped} 个</span>
        </div>
      </div>
    </div>
    ${failed > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>❌ 失败的测试</h3>
      ${failedHtml}
    </div>` : ''}
    ${stmtCov > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>📈 覆盖率报告</h3>
      <div class="dsh-pm-coverage">
        <div class="dsh-pm-coverage-bar">
          <span class="dsh-pm-coverage-label">语句覆盖率</span>
          <span class="dsh-pm-coverage-value">${stmtCov}%</span>
          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${stmtCov}%"></div></div>
        </div>
        <div class="dsh-pm-coverage-bar">
          <span class="dsh-pm-coverage-label">分支覆盖率</span>
          <span class="dsh-pm-coverage-value">${branchCov}%</span>
          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${branchCov}%"></div></div>
        </div>
        <div class="dsh-pm-coverage-bar">
          <span class="dsh-pm-coverage-label">函数覆盖率</span>
          <span class="dsh-pm-coverage-value">${funcCov}%</span>
          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${funcCov}%"></div></div>
        </div>
        <div class="dsh-pm-coverage-bar">
          <span class="dsh-pm-coverage-label">行覆盖率</span>
          <span class="dsh-pm-coverage-value">${lineCov}%</span>
          <div class="dsh-pm-coverage-track"><div class="dsh-pm-coverage-fill" style="width: ${lineCov}%"></div></div>
        </div>
      </div>
    </div>` : ''}`
}

/* ------------------------------------------------------------------ 评审节点 */

export function renderReviewContent(task: TaskRecord): string {
  // 从 comments 中提取评审意见
  const reviewComments = task.comments.filter(c => c.createdBy?.kind === 'agent' || c.createdBy?.kind === 'human')

  // 从 executions.evidence 解析评审结果
  const lastExec = task.executions[task.executions.length - 1]
  let approved = false
  let reviewStatus = '待评审'
  const suggestions: Array<{file: string; line: string; severity: 'low' | 'medium' | 'high'; message: string; resolved: boolean}> = []
  const passedItems: string[] = []

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析 "approved" 或 "rejected"
      if (ev.toLowerCase().includes('approved') || ev.toLowerCase().includes('通过')) {
        approved = true
        reviewStatus = '已批准'
      }
      if (ev.toLowerCase().includes('rejected') || ev.toLowerCase().includes('退回')) {
        reviewStatus = '已退回'
      }

      // 解析通过项 "✓ code style"
      if (ev.startsWith('✓') || ev.startsWith('✅')) {
        passedItems.push(ev.replace(/^[✓✅]\s*/, ''))
      }

      // 解析改进建议 "file.ts:45 [medium] Use constant instead of magic number"
      const suggMatch = ev.match(/^(.+?):(\d+)\s*\[(\w+)\]\s*(.+)/)
      if (suggMatch) {
        suggestions.push({
          file: suggMatch[1],
          line: suggMatch[2],
          severity: suggMatch[3] as 'low' | 'medium' | 'high',
          message: suggMatch[4],
          resolved: false,
        })
      }
    })
  }

  const severityLabels = { low: '低', medium: '中', high: '高' }
  const severityColors = { low: '#28a745', medium: '#f0a020', high: '#dc3545' }

  const passedHtml = passedItems.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>✅ 通过项</h3>
      <ul class="dsh-pm-review-list">
        ${passedItems.map(item => `<li class="dsh-pm-review-pass">${esc(item)}</li>`).join('')}
      </ul>
    </div>` : ''

  const suggestionsHtml = suggestions.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>⚠️ 改进建议（${suggestions.length} 项）</h3>
      <div class="dsh-pm-suggestions">
        ${suggestions.map((s, i) => `
          <div class="dsh-pm-suggestion" data-severity="${s.severity}">
            <div class="dsh-pm-suggestion-head">
              <span class="dsh-pm-suggestion-num">${i + 1}</span>
              <code class="dsh-pm-file-path">${esc(s.file)}:${s.line}</code>
              <span class="dsh-pm-severity-badge" data-severity="${s.severity}" style="background: ${severityColors[s.severity]}">
                严重性：${severityLabels[s.severity]}
              </span>
            </div>
            <div class="dsh-pm-suggestion-body">${esc(s.message)}</div>
          </div>`).join('')}
      </div>
    </div>` : ''

  const commentsHtml = reviewComments.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>💬 评审讨论（${reviewComments.length} 条）</h3>
      ${renderComments(reviewComments)}
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📊 评审结果</h3>
      <div class="dsh-pm-review-status" data-status="${approved ? 'approved' : 'pending'}">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">状态</span>
          <span class="dsh-pm-stat-value">${reviewStatus}</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">通过项</span>
          <span class="dsh-pm-stat-value">${passedItems.length} 项</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">改进建议</span>
          <span class="dsh-pm-stat-value">${suggestions.length} 项</span>
        </div>
      </div>
    </div>
    ${passedHtml}
    ${suggestionsHtml}
    ${commentsHtml}`
}

/* ------------------------------------------------------------------ 合并节点 */

export function renderMergeContent(task: TaskRecord): string {
  // 从 executions.evidence 解析合并信息
  const lastExec = task.executions[task.executions.length - 1]
  let sourceBranch = '未知'
  let targetBranch = 'main'
  let commits = 0
  let filesChanged = 0
  let linesAdded = 0
  let linesDeleted = 0
  let mergeStatus = '进行中'
  const conflicts: Array<{file: string; description: string; resolution: string}> = []
  const ciChecks: Array<{name: string; status: 'pass' | 'fail' | 'pending'; details?: string}> = []

  if (lastExec?.evidence) {
    lastExec.evidence.forEach(ev => {
      // 解析 "feature/login → main"
      const branchMatch = ev.match(/(.+?)\s*(?:→|->|-)\s*(.+)/)
      if (branchMatch) {
        sourceBranch = branchMatch[1].trim()
        targetBranch = branchMatch[2].trim()
      }

      // 解析 "12 commits"
      const commitMatch = ev.match(/(\d+)\s*commits?/i)
      if (commitMatch) commits = parseInt(commitMatch[1], 10)

      // 解析 "15 files changed"
      const filesMatch = ev.match(/(\d+)\s*files?\s*changed/i)
      if (filesMatch) filesChanged = parseInt(filesMatch[1], 10)

      // 解析 "+854 -231"
      const diffMatch = ev.match(/\+(\d+)\s*-(\d+)/)
      if (diffMatch) {
        linesAdded = parseInt(diffMatch[1], 10)
        linesDeleted = parseInt(diffMatch[2], 10)
      }

      // 解析 "merged" 或 "conflicted"
      if (ev.toLowerCase().includes('merged') || ev.toLowerCase().includes('合并成功')) {
        mergeStatus = '✅ 合并成功'
      }
      if (ev.toLowerCase().includes('conflict')) {
        mergeStatus = '⚠️ 存在冲突'
      }

      // 解析冲突 "conflict: src/router.ts - routing config duplicate"
      const conflictMatch = ev.match(/conflict:\s*(.+?)\s*-\s*(.+)/i)
      if (conflictMatch) {
        conflicts.push({
          file: conflictMatch[1].trim(),
          description: conflictMatch[2].trim(),
          resolution: '待解决',
        })
      }

      // 解析 CI 检查 "✓ unit-tests: 18/18 passed"
      const ciMatch = ev.match(/^([✓✅❌⏳])\s*(.+?):\s*(.+)/)
      if (ciMatch) {
        const status = ciMatch[1] === '✓' || ciMatch[1] === '✅' ? 'pass' : ciMatch[1] === '❌' ? 'fail' : 'pending'
        ciChecks.push({
          name: ciMatch[2].trim(),
          status,
          details: ciMatch[3].trim(),
        })
      }
    })
  }

  const conflictsHtml = conflicts.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>⚠️ 冲突解决（${conflicts.length} 个）</h3>
      <div class="dsh-pm-conflicts">
        ${conflicts.map((c, i) => `
          <div class="dsh-pm-conflict">
            <div class="dsh-pm-conflict-num">${i + 1}</div>
            <div class="dsh-pm-conflict-body">
              <code class="dsh-pm-file-path">${esc(c.file)}</code>
              <div class="dsh-pm-conflict-desc">冲突：${esc(c.description)}</div>
              <div class="dsh-pm-conflict-resolution">解决：${esc(c.resolution)}</div>
            </div>
          </div>`).join('')}
      </div>
    </div>` : ''

  const ciHtml = ciChecks.length > 0 ? `
    <div class="dsh-pm-detail-section">
      <h3>✅ CI/CD 检查</h3>
      <div class="dsh-pm-ci-checks">
        ${ciChecks.map(check => {
          const icon = check.status === 'pass' ? '✅' : check.status === 'fail' ? '❌' : '⏳'
          return `
            <div class="dsh-pm-ci-check" data-status="${check.status}">
              <span class="dsh-pm-ci-icon">${icon}</span>
              <span class="dsh-pm-ci-name">${esc(check.name)}</span>
              <span class="dsh-pm-ci-details">${esc(check.details || '')}</span>
            </div>`
        }).join('')}
      </div>
    </div>` : ''

  return `
    <div class="dsh-pm-detail-section dsh-pm-specialized">
      <h3>📊 合并状态</h3>
      <div class="dsh-pm-merge-header">
        <div class="dsh-pm-merge-branch">
          <code>${esc(sourceBranch)}</code>
          <span class="dsh-pm-merge-arrow">→</span>
          <code>${esc(targetBranch)}</code>
        </div>
        <div class="dsh-pm-merge-status">${mergeStatus}</div>
      </div>
      <div class="dsh-pm-stats">
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">提交数</span>
          <span class="dsh-pm-stat-value">${commits} commits</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">变更文件</span>
          <span class="dsh-pm-stat-value">${filesChanged} 个</span>
        </div>
        <div class="dsh-pm-stat">
          <span class="dsh-pm-stat-label">代码变更</span>
          <span class="dsh-pm-stat-value">
            <span class="dsh-pm-stat-add">+${linesAdded}</span>
            <span class="dsh-pm-stat-del">-${linesDeleted}</span>
          </span>
        </div>
      </div>
    </div>
    ${conflictsHtml}
    ${ciHtml}`
}
