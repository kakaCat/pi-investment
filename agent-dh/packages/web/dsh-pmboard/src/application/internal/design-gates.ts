/**
 * 设计阶段规范化闸门（REQ-2d1c74）——G2 完整性门 / 拆分内容硬门 / 登记可打开性门。
 *
 * 为什么独立成模块：content-gate-wiring.ts 受尺寸门禁（≤400 行）约束，
 * 本需求的三个新闸门集中放这里，调用方继续从 content-gate-wiring.js import（再导出），
 * 与本仓 content-gates/content-trace 的拆分方式同款。
 *
 * @module dsh-pmboard/application/internal/design-gates
 */
import type { RequirementRecord } from '../../shared/protocol.js'
import type { GateFailure } from './artifact-gates.js'
import { detectDecompositionFeatures, parseDocument, type DocsReader } from './content-gates.js'
import { designDocPolicyFrom, missingCategoryDocs } from './category-doc-sets.js'
import { normalizeArtifactPath } from '../../domain/artifact/ArtifactPath.js'
import { fmt } from '../../domain/text/fmt.js'
import { envelope, type GateFeedback } from './gate-feedback.js'


/**
 * 拆分内容硬门禁（REQ-2d1c74 FR-3）：确认 kind=design 产物前，三条确认通道
 * （会话弹框 / 会话文字证据 / 看板一键）统一在落章前调用。
 *
 * 扫描 design/ 目录实际落盘的全部 .md（ground truth，含尚未登记的新文档），
 * 命中任务表/拆分章节特征即拒——拆分内容（任务表/DAG）属拆分阶段产物，
 * 不得出现在设计文档里（D3：此前无任何代码检查，REQ-c48f99 实证混入）。
 */
export async function checkDesignDecompositionGate(
  docs: DocsReader,
  req: RequirementRecord,
): Promise<GateFailure | undefined> {
  const designDir = 'docs/requirements/' + req.id + '/design'
  const names = (docs.list?.(designDir) ?? [])
    .filter(e => e.isFile !== false && (e.name ?? '').endsWith('.md'))
    .map(e => e.name ?? '')
    .filter(n => n.length > 0)
  const hits: string[] = []
  for (const name of names) {
    const p = designDir + '/' + name
    if (!docs.exists(p)) continue
    const features = detectDecompositionFeatures(parseDocument(await docs.read(p)))
    for (const f of features) hits.push(name + ' → ' + f)
  }
  if (hits.length === 0) return undefined
  return {
    code: 'design_contains_decomposition',
    kind: 'design',
    gaps: hits,
    message: envelope({
      what: fmt('设计文档命中拆分内容：{list}', { list: hits.join('；') }),
      why: '任务表/拆分计划属拆分阶段产物，不得出现在 design/*.md',
      how: fmt('把该内容挪到拆分阶段（docs/requirements/{req}/decomposition.md）后重调 reqboard_ask_confirm(target=artifact, kind=design)', { req: req.id }),
    }),
  }
}

// ---------------------------------------------------------------------------
// 登记可打开性校验（REQ-2d1c74 FR-5）
// ---------------------------------------------------------------------------

/**
 * 抛出带 code 的登记拒绝（与 support.reject 同构：message 自带（code）文本——跨包时工具层读的是 message）。
 * REQ-260924213231-b1c4 FR-2：文案走统一信封（`what —— why。补齐：how`），形态判定一律不动。
 */
function openableError(code: 'REQBOARD_FILE_MISSING' | 'REQBOARD_ARTIFACT_NOT_OPENABLE', f: GateFeedback): never {
  throw Object.assign(new Error(envelope(f) + '（' + code + '）'), { code })
}

/**
 * 产物登记前的可打开性校验（与 http/routers/artifacts.ts 的 classify 同口径的 use-case 侧版本）。
 *
 * 判定顺序（先形态、后存在）：
 *  ① 伪路径/越界（空串 / 反斜杠 / `..` 段 / brace-通配 / 工作区外）→
 *     REQBOARD_ARTIFACT_NOT_OPENABLE（消息含 normalized 路径与原因）；
 *  ② 归一后 docs.exists 必须为真 → 否则 REQBOARD_FILE_MISSING（未落盘或路径写错）。
 * 通过 → 返回 normalized 工作区相对路径（调用方以归一值登记，台账不再形态各异）。
 *
 * 目的（D6）：让"文档没落盘/路径写错"在登记时就响亮失败，而不是等人点看才发现。
 */
export function assertArtifactOpenable(docs: DocsReader, rawPath: string): string {
  const raw = (rawPath ?? '').trim()
  const BACKSLASH = String.fromCharCode(92)
  if (raw.length === 0) {
    openableError('REQBOARD_ARTIFACT_NOT_OPENABLE', {
      what: '产物登记被拒：路径为空（normalized=（空））',
      why: '空串无法定位任何文档',
      how: '传入工作区相对路径，如 docs/requirements/<REQ>/design/architecture.md',
    })
  }
  // 反斜杠与 `..` 在归一之前就拦下——不把攻击路径洗白成工作区相对路径（同 classify 口径）
  if (raw.includes(BACKSLASH) || raw.split('/').some(s => s === '..')) {
    openableError('REQBOARD_ARTIFACT_NOT_OPENABLE', {
      what: fmt('产物登记被拒：路径含 .. 或反斜杠（normalized={path}）', { path: raw }),
      why: '该形态可能越出工作区或指向非目标文件',
      how: '改为工作区内的真实相对路径（不含 .. 与反斜杠）后重调 reqboard_submit 登记',
    })
  }
  // normalizeArtifactPath 需要工作区根做前缀剥离；DocsReader 不保证提供，鸭子探测、缺省 '/'
  // （root='/' 时 base 为空，相对路径原样归一，满足登记侧"工作区相对"语义）。
  const root = (docs as { workspaceRoot?: () => string }).workspaceRoot?.() ?? '/'
  const norm = normalizeArtifactPath(raw, root)
  if (norm.form === 'pseudo') {
    openableError('REQBOARD_ARTIFACT_NOT_OPENABLE', {
      what: fmt('产物登记被拒：不是文件路径——brace / 通配写法或空串（normalized={path}）', { path: norm.path }),
      why: 'brace / 通配写法不是真实文件路径',
      how: '改为工作区内的真实文件路径（先落盘再调 reqboard_submit 登记）',
    })
  }
  if (norm.form === 'outside') {
    openableError('REQBOARD_ARTIFACT_NOT_OPENABLE', {
      what: fmt('产物登记被拒：路径在工作区之外（normalized={path}）', { path: norm.path }),
      why: '越界路径不被接受（只认工作区相对路径）',
      how: '改为工作区内的相对路径再调 reqboard_submit 登记',
    })
  }
  if (!docs.exists(norm.path)) {
    openableError('REQBOARD_FILE_MISSING', {
      what: fmt('产物登记被拒：文件不存在（normalized={path}）', { path: norm.path }),
      why: '文档未落盘或路径写错',
      how: '先把文档落到该路径（或改传正确路径），再调 reqboard_submit 登记',
    })
  }
  return norm.path
}

/**
 * G2 文档集完整性闸门（REQ-2d1c74 FR-2）：design→decomposing **四条转移路径**统一调用
 * （MoveRequirement / AskConfirm 推进块 / 看板移动 / 看板确认后自动推进）。
 *
 * 两级核验：
 *  ① 文档集交齐——必交 ∪ sides 命中的条件必交 − 有效豁免；策略来源 = requirement.md
 *    front-matter（designDocPolicyFrom），交没交以 design/ 目录实际落盘为准（不看登记簿，
 *    防止"登记了但文件没落盘"或反过来的漂移）；
 *  ② 全部 kind=design 产物已确认——磁盘上的每份 design/*.md 都必须有确认章
 *    （含"确认后新自动发现的那一份"，UC-4：无章即拦，消息点名）。
 *
 * isLegacy（artifacts 空/undefined）→ undefined（放行，向后兼容）。
 */
export async function checkDesignCompletenessGate(
  docs: DocsReader,
  req: RequirementRecord,
): Promise<GateFailure | undefined> {
  const isLegacy = req.artifacts === undefined || req.artifacts.length === 0
  if (isLegacy) return undefined

  const gaps: string[] = []
  const reqPath = 'docs/requirements/' + req.id + '/requirement.md'
  const designDir = 'docs/requirements/' + req.id + '/design'
  const onDisk = (docs.list?.(designDir) ?? [])
    .filter(e => e.isFile !== false && (e.name ?? '').endsWith('.md'))
    .map(e => e.name ?? '')
    .filter(n => n.length > 0)

  // ── ① 文档集交齐 ──────────────────────────────────────────────────────
  if (!docs.exists(reqPath)) {
    gaps.push('requirement.md 不存在（无法核验文档集策略与端侧/豁免声明）')
  } else {
    const rootText = await docs.read(reqPath)
    const policy = designDocPolicyFrom(parseDocument(rootText).frontmatter)
    gaps.push(...missingCategoryDocs({
      category: req.category,
      rootExists: true,
      rootText,
      designNames: onDisk,
      sides: policy.sides,
      exempt: policy.exempt,
    }))
  }

  // ── ② 全部 kind=design 产物已确认 ────────────────────────────────────
  // REQ-260924213231-b1c4 FR-2：两种病因**分叉**——art === undefined（未登记，产物簿无此条）
  // 与 confirmedAt === undefined（待确认，已登记未落章）此前同写一句「未确认」，agent 只能盲试；
  // 现各自带唯一可行命令。判定口径不变（仍是"磁盘上每份 design/*.md 都要有确认章"）。
  for (const name of onDisk) {
    const suffix = '/design/' + name
    const path = designDir + '/' + name
    const art = (req.artifacts ?? []).find(a => a.kind === 'design' && a.path.endsWith(suffix))
    if (art === undefined) {
      gaps.push(fmt('{path} 未登记（产物簿无此条，先调 reqboard_submit(kind=design)）', { path }))
    } else if (art.confirmedAt === undefined) {
      gaps.push(fmt('{path} 待确认（已登记未落章，先调 reqboard_ask_confirm(target=artifact, kind=design)）', { path }))
    }
  }

  if (gaps.length === 0) return undefined
  return {
    code: 'design_doc_incomplete',
    kind: 'design',
    gaps,
    message: envelope({
      what: fmt('design → decomposing 的设计文档集：{list}', { list: gaps.join('；') }),
      why: '设计文档集未交齐或未全部确认',
      how: '未交的按 templates/design/*.md 落盘，未登记的调 reqboard_submit(kind=design)，待确认的调 reqboard_ask_confirm(target=artifact, kind=design)',
    }),
  }
}
