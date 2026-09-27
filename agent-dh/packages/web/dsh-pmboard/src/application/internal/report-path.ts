/**
 * 汇报文件路径的**归一解析**（REQ-260927123256-196b 实测缺陷 D15）。
 *
 * 背景事故：子代理在 `filesChanged` 里写 `agent-dh/packages/...`（相对 **git 根**），而凭证门
 * （`assertDoneEvidence` → `deps.docs.stat`）按 **工作区根**（`deps.docs.workspaceRoot()` =
 * 本实例 `process.cwd()` = `/…/agent-dh`）解析 → 去找 `agent-dh/agent-dh/packages/...` →
 * 真实文件被判「不存在」→ 子卡凭证门恒不过、链必停（实测 04:51/05:10/05:28 三次）。
 *
 * 这里只做一件事：**同一个文件先按原样、再按「去掉工作区根 basename 前缀」解析**，取首个存在的。
 * 不猜、不放开前缀匹配——只有命中真实文件才算数（解不出就返回 undefined，凭证门照旧拦）。
 *
 * @module dsh-pmboard/application/internal/report-path
 */
import type { UseCaseDeps } from '../ports.js'

/** 汇报路径的候选解析顺序：原样 → 去掉 workspaceRoot basename 前缀（去重、保序）。 */
export function reportPathCandidates(file: string, workspaceRoot?: string): string[] {
  const raw = typeof file === 'string' ? file.trim() : ''
  if (raw.length === 0) return []
  const normalized = raw.replace(/\\/g, '/').replace(/^\.\//, '')
  const candidates = [raw]
  const root = (typeof workspaceRoot === 'string' ? workspaceRoot : '').replace(/\\/g, '/').replace(/\/+$/, '')
  const base = root.split('/').filter((s) => s.length > 0).pop()
  if (base !== undefined && base.length > 0 && normalized.startsWith(base + '/')) {
    candidates.push(normalized.slice(base.length + 1))
  }
  return [...new Set(candidates)]
}

/**
 * 汇报文件的真实 mtime：按候选顺序取**首个存在**的解析结果；都不存在 → undefined。
 * 调用方（凭证门）据此判「文件是否存在且新于开工时刻」。
 */
export function reportFileMtime(deps: UseCaseDeps, file: string): number | undefined {
  if (typeof file !== 'string' || file.trim().length === 0) return undefined
  let root: string | undefined
  try {
    root = deps.docs.workspaceRoot()
  } catch {
    root = undefined
  }
  for (const candidate of reportPathCandidates(file, root)) {
    const st = deps.docs.stat(candidate)
    if (st !== undefined) return st.mtimeMs
  }
  return undefined
}
