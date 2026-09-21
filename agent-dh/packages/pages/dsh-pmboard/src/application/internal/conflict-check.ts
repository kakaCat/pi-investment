/**
 * 拆分期改动面冲突拦截（REQ-4842fe t9 / FR-10 主防线）。
 *
 * 两张**互无依赖**的父卡若在 implementation 里声明同一文件，并行跑会互相覆盖——
 * 拆分阶段就拒绝（比运行期靠 mtime 事后发现便宜得多）。
 *
 * 诚实边界：本检查基于 implementation 文本里的文件路径 token，声明不全则查不出；
 * 运行期 mtime 兜底（cross-card.ts）是第二道防线，人工 review 仍不可替代。
 *
 * @module dsh-pmboard/application/internal/conflict-check
 */
export interface WorkSurfaceTask {
  key: string
  implementation: string
  dependsOn: readonly string[]
}

export interface WorkSurfaceConflict {
  file: string
  keys: [string, string]
}

import { fmt } from '../../domain/text/fmt.js'

const PATH_RE = /(?:agent-dh\/)?(?:packages|scripts|tests|docs)\/(?:[\w@-]+\/)*[\w@.-]+\.(?:tsx|json|mjs|cjs|ts|js|md|css|html|yaml|yml)/g

/** 抽取 implementation 声明的工作区文件路径（去重）。 */
export function declaredFiles(implementation: string): string[] {
  const out = new Set<string>()
  for (const m of implementation.matchAll(PATH_RE)) out.add(m[0])
  return [...out]
}

/** 冲突清单人读文本（错误消息与报告共用）。 */
export function describeConflicts(conflicts: readonly WorkSurfaceConflict[]): string {
  return conflicts.map((c) => fmt('{file}（{a} / {b}）', { file: c.file, a: c.keys[0], b: c.keys[1] })).join('；')
}

/** 传递闭包：某 key 的全部（间接）前置依赖。 */
function ancestorsOf(tasks: readonly WorkSurfaceTask[], key: string): Set<string> {
  const byKey = new Map(tasks.map((t) => [t.key, t]))
  const seen = new Set<string>()
  const stack = [...(byKey.get(key)?.dependsOn ?? [])]
  while (stack.length > 0) {
    const k = stack.pop() as string
    if (seen.has(k)) continue
    seen.add(k)
    for (const d of byKey.get(k)?.dependsOn ?? []) stack.push(d)
  }
  return seen
}

/**
 * 找出"互无依赖的卡声明了同一文件"的冲突对。
 * 同一条依赖链上的卡（前后依赖）不算冲突——它们天然串行。
 */
export function findWorkSurfaceConflicts(tasks: readonly WorkSurfaceTask[]): WorkSurfaceConflict[] {
  const files = new Map(tasks.map((t) => [t.key, new Set(declaredFiles(t.implementation))]))
  const ancestors = new Map(tasks.map((t) => [t.key, ancestorsOf(tasks, t.key)]))
  const conflicts: WorkSurfaceConflict[] = []
  for (let i = 0; i < tasks.length; i += 1) {
    for (let j = i + 1; j < tasks.length; j += 1) {
      const a = tasks[i] as WorkSurfaceTask
      const b = tasks[j] as WorkSurfaceTask
      const serial = (ancestors.get(b.key) as Set<string>).has(a.key) || (ancestors.get(a.key) as Set<string>).has(b.key)
      if (serial) continue
      const fa = files.get(a.key) as Set<string>
      for (const f of fa) {
        if ((files.get(b.key) as Set<string>).has(f)) conflicts.push({ file: f, keys: [a.key, b.key] })
      }
    }
  }
  return conflicts
}
