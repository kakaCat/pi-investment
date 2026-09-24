/**
 * 产物种类 / 节点文档文件名 → 中文名：唯一事实源（REQ-260922182638-0777 FR-1）。
 *
 * 背景：此前 dsh-pmboard 前端有六处各自为政的中文映射表（stage-panel / views/artifacts /
 * views/verification / toolviews/shared / toolviews/rows/ask-confirm / tools/render-summaries），
 * 注释互相声称「保持一致」但已实质漂移（如归档区把 requirement 译作「需求说明」）。
 * 本模块是**唯一**定义处：所有展示层一律 import 本模块的查询函数，禁止再建本地映射表。
 * 防漂移护栏见 tests/artifact-labels.test.ts TC-001/TC-005（新增 kind / 规范文件名未配中文名即红）。
 *
 * 纯函数、零 IO、零运行时依赖：client 与 host 双向安全（与 protocol.ts 同层同性质）。
 * 任何输入不 throw——展示层兜底契约集中在函数内部，调用方不得再写 `?? kind` 兜底。
 *
 * 设计来源：docs/requirements/REQ-260922182638-0777/design/interfaces.md（I-1~I-3）。
 *
 * @module dsh-pmboard/shared/artifact-labels
 */

/* ------------------------------------------------------------------ 映射表（I-3 终稿） */

/**
 * 种类 → 中文名：7 种 ArtifactKind + 文档区扩展种类（ui/proposal/retro/notes）。
 * 与 prototype.html 第一层表逐字一致；新增 ArtifactKind 时必须在此配中文名（TC-001 拦截）。
 */
export const KIND_LABELS: Readonly<Record<string, string>> = {
  requirement: '需求文档',
  design: '设计文档',
  plan: '拆分计划（旧版）', // 2026-09-21：plan 退役，拆分计划由 decomposition 承载
  decomposition: '拆分计划',
  task_detail: '任务卡',
  verification: '验收材料',
  archive: '归档材料',
  notes: '其他',
  task_output: '任务产物',
  // 文档区扩展种类（非 ArtifactKind，docLinks / 归档清单使用）
  ui: 'UI 文档',
  proposal: '设计文档',
  retro: '复盘',
}

/** 种类 → 图标（图标归属不变，仅从 verification.ts DOC_KIND_META 集中一处）。 */
export const KIND_ICONS: Readonly<Record<string, string>> = {
  requirement: '📄',
  ui: '🎨',
  proposal: '📐',
  plan: '📝',
  decomposition: '🧩',
  design: '📐',
  task_detail: '🗂️',
  verification: '✅',
  archive: '📦',
  retro: '🔁',
  notes: '📒',
  task_output: '📤',
}

/**
 * 文件名 → 中文文档名：追溯链 / 文档记录区的主标签不再裸显英文文件名（FR-4）。
 * 键 = 需求目录相对尾段（design/architecture.md）或裸文件名（requirement.md）；
 * 与 prototype.html 第二层表逐字一致，并补齐 category-doc-sets 全部规范文件名
 * （effectiveDesignDocs 的产出必须全部在此有中文名——TC-005 护栏，缺配即红）。
 */
export const DOC_FILE_LABELS: Readonly<Record<string, string>> = {
  'requirement.md': '需求文档',
  'decomposition.md': '拆分计划',
  'design/architecture.md': '架构文档',
  'design/data-model.md': '数据模型',
  'design/interfaces.md': '接口文档',
  'design/test-cases.md': '测试用例',
  'design/migration.md': '迁移方案',
  'design/frontend.md': '前端设计',
  'design/backend.md': '后端设计',
  'design/use-cases.md': '用例文档',
}

/* ------------------------------------------------------------------ 查询函数（I-2 契约） */

/**
 * 产物种类 → 中文名。
 * 命中 KIND_LABELS → 中文名；未命中 → `产物（原枚举值）`（中文引导 + 原文附注，不裸显英文）；
 * 空串 → `产物`。任何输入不 throw。
 */
export function artifactKindLabel(kind: string): string {
  const hit = KIND_LABELS[kind]
  if (hit !== undefined) return hit
  return kind ? `产物（${kind}）` : '产物'
}

/**
 * 文档路径 → 中文文档名。
 * path 归一化（去前导 `./`）后对 DOC_FILE_LABELS 做**段边界后缀匹配**
 * （path === key || path.endsWith('/' + key)）→ 中文名；
 * 未命中 → basename 非空时 `<kind中文>（<文件名>）`（kind 缺省用「文档」），basename 为空 → artifactKindLabel(kind)。
 */
export function docFileLabel(path: string, kind?: string): string {
  const normalized = (path ?? '').replace(/^\.\//, '')
  for (const [key, label] of Object.entries(DOC_FILE_LABELS)) {
    if (normalized === key || normalized.endsWith('/' + key)) return label
  }
  const base = normalized.split('/').pop() ?? ''
  if (base.length > 0) return `${kind !== undefined ? artifactKindLabel(kind) : '文档'}（${base}）`
  return artifactKindLabel(kind ?? '')
}

/**
 * 任务卡标签：title 非空 → `任务卡 · <任务名称>`（FR-5：逐张列出且带名称）；
 * 否则取 basename 去 `.md` 后缀 → `任务卡（<id>）`（id 空则 `任务卡`）。
 */
export function taskCardLabel(path: string, title?: string): string {
  if (title !== undefined && title.trim().length > 0) return `任务卡 · ${title}`
  const base = (path ?? '').split('/').pop() ?? ''
  const id = base.replace(/\.md$/i, '')
  return id.length > 0 ? `任务卡（${id}）` : '任务卡'
}
