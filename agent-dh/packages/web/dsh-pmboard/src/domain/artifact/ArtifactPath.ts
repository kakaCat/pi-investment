/**
 * 产物路径归一层（REQ-b63a7d t1）——把台账里形态各异的产物/文档路径收敛成唯一口径。
 *
 * 背景（实测 2026-09-18，REQ-b63a7d）：`reqboard_task_report` 会把窗口汇报的 files_changed
 * **原样**登记成产物，而文件接口按「工作区相对路径」解析——于是同一份台账里同时存在
 * 四种形态，前端存在性预检时被白名单守卫判成 403（本实例扫描出 142 条）：
 *   ① 工作区名前缀 `agent-dh/docs/x.md`（仓库根相对）
 *   ② 绝对路径 `/Users/.../agent-dh/packages/x.ts`
 *   ③ 跨仓相对路径 `quantsys-v2/x.py`（注册时相对仓库根，本工作区接口不可服务）
 *   ④ 伪路径 `quantsys-v2/tests/{a.py,b.py}`（brace-glob 汇总写法，不是文件）
 *
 * 本文件只做**字符串判定**：不碰 I/O、不读时间与随机数（层边界门禁 INV-2）。
 * 「文件是否真的存在」「是否落在某个兄弟仓库」由调用方用 fs 决定——字符串层无法区分
 * 「工作区里恰好有个叫 quantsys-v2 的目录」与「仓库根下的兄弟仓库 quantsys-v2」。
 */

/** 归一后的路径形态。 */
export type ArtifactPathForm =
  /** 工作区相对路径（文件接口可服务；是否存在由 fs 判定） */
  | 'workspace'
  /** 指向工作区之外（绝对路径落在别处 / 仓库根下的兄弟仓库 / 用 .. 逃逸） */
  | 'outside'
  /** 伪路径（brace-glob 汇总写法、通配符、空串）——不是文件 */
  | 'pseudo'

/** 归一结果。 */
export interface NormalizedArtifactPath {
  /** 归一后的路径：workspace = 工作区相对；outside/pseudo = 尽力清洗后的原样 */
  path: string
  form: ArtifactPathForm
}

/** 伪路径特征：brace-glob 汇总写法与通配符（都不是真实文件）。 */
const PSEUDO_RE = /[{}*]/

function stripDotPrefix(p: string): string {
  let out = p
  while (out.startsWith('./')) out = out.slice(2)
  return out
}

function dropLeadingSlashes(p: string): string {
  let out = p
  while (out.startsWith('/')) out = out.slice(1)
  return out
}

function trimTrailingSlashes(p: string): string {
  return p.length > 1 ? p.replace(/\/+$/, '') : p
}

/**
 * 归一化一个产物路径。
 *
 * @param raw           台账里的原始字符串
 * @param workspaceRoot 工作区绝对路径（由调用方注入；domain 不读 process.cwd）
 */
export function normalizeArtifactPath(raw: string, workspaceRoot: string): NormalizedArtifactPath {
  const root = trimTrailingSlashes((workspaceRoot ?? '').replace(/\\/g, '/'))
  const slash = root.lastIndexOf('/')
  const base = slash >= 0 ? root.slice(slash + 1) : root
  const parent = slash > 0 ? root.slice(0, slash) : ''

  const original = (raw ?? '').trim().replace(/\\/g, '/')
  if (original.length === 0) return { path: '', form: 'pseudo' }
  if (PSEUDO_RE.test(original)) return { path: original, form: 'pseudo' }

  let p = original
  if (p.startsWith('/')) {
    if (base.length > 0 && (p === root || p.startsWith(root + '/'))) {
      // 绝对路径就在工作区内：剥掉工作区前缀
      p = dropLeadingSlashes(p.slice(root.length))
    } else if (parent.length > 0 && (p === parent || p.startsWith(parent + '/'))) {
      // 绝对路径在仓库根下：剥掉仓库根，再看首段是不是本工作区目录名
      p = dropLeadingSlashes(p.slice(parent.length))
      if (base.length === 0 || !(p === base || p.startsWith(base + '/'))) {
        return { path: p, form: 'outside' }
      }
      p = dropLeadingSlashes(p.slice(base.length))
    } else {
      return { path: p, form: 'outside' }
    }
  } else {
    p = stripDotPrefix(p)
    // 仓库根相对（agent-dh/docs/...）：剥掉重复的工作区目录名前缀
    if (base.length > 0 && (p === base || p.startsWith(base + '/'))) {
      p = dropLeadingSlashes(p.slice(base.length))
    }
  }

  // 任何一层 `..` 段都算逃逸（'../x' 与 'docs/../../x' 同样必须判 outside）
  if (p.split('/').some(seg => seg === '..')) return { path: p, form: 'outside' }
  if (p.length === 0) return { path: '', form: 'workspace' }
  return { path: p, form: 'workspace' }
}
