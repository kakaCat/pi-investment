/**
 * 设计文档交付状态（REQ-81aabd FR-2；REQ-2d1c74 FR-1/FR-2 扩展）。
 *
 * 设计节点要回答"设计文档交齐了没"。按类型模板 + **需求 front-matter 策略**
 * （sides 端侧声明 / design_exempt 豁免声明）逐份核对需求台账里 design/<name> 是否已登记，
 * 产出 { name, path, submitted, conditional?, exempted? }：
 *   - 必交 ∪ sides 命中的条件必交（条件必交带 conditional 标记）；
 *   - 有效豁免（理由非空）的条目保留在清单里并带 exempted=理由（页面上灰显"已豁免"），
 *     让"少交一份"是显式决策而不是静默漏交。
 *
 * 头注更新（REQ-2d1c74 FR-2）：旧注"不参与任何闸门"作废——呈现与 G2 完整性闸门
 * 共用同一份策略解析（designDocPolicyFrom），页面上"已交/未交/豁免"与 G2 拦截清单天然一致。
 * 纯函数：不读 fs、不写盘——文件系统扫描仍只在 adapters（INV-7）；front-matter 由 host 侧
 * 读取后经 designDocPolicyOf 传入（client 不碰 fs）。
 *
 * @module dsh-pmboard/application/internal/design-docs
 */
import { designDocPolicyFrom, effectiveDesignDocs, type DesignDocPolicy } from './category-doc-sets.js'
import { parseDocument } from './doc-parse.js'
import type { DesignDocRegistration, DesignDocStatus, RequirementRecord } from '../../shared/protocol.js'

/** 空策略（无 front-matter 声明时的默认：只有必交、无豁免）。 */
export const EMPTY_DESIGN_DOC_POLICY: DesignDocPolicy = { sides: [], exempt: {} }

/** host 侧读取 requirement.md front-matter 并解析设计文档策略（client 不碰 fs，统一走这里）。 */
export async function designDocPolicyOf(
  docs: { exists(relPath: string): boolean; read(relPath: string): Promise<string> },
  req: RequirementRecord,
): Promise<DesignDocPolicy> {
  const path = 'docs/requirements/' + req.id + '/requirement.md'
  if (!docs.exists(path)) return EMPTY_DESIGN_DOC_POLICY
  return designDocPolicyFrom(parseDocument(await docs.read(path)).frontmatter)
}

/**
 * 分类模板 + 策略要求的设计文档 → 逐份交付状态（需求目录里已登记 = 已交）。
 * 豁免条目保留在清单中（exempted=理由），供页面灰显"已豁免"。
 */
export function designDocStatus(
  req: RequirementRecord,
  category: string,
  policy: DesignDocPolicy = EMPTY_DESIGN_DOC_POLICY,
): DesignDocStatus[] {
  const artifacts = req.artifacts ?? []
  return effectiveDesignDocs(category, policy.sides).map(({ name, conditional }) => {
    const suffix = '/design/' + name
    const entry: DesignDocStatus = {
      name,
      path: 'docs/requirements/' + req.id + suffix,
      submitted: artifacts.some(a => a.path.endsWith(suffix)),
      ...(conditional !== undefined ? { conditional } : {}),
    }
    const reason = policy.exempt[name]
    if (reason !== undefined && reason.trim() !== '') entry.exempted = reason
    return entry
  })
}

/**
 * 设计文档**逐份登记态**（T-3，REQ-260924213231-b1c4 / I-1）——磁盘 / 产物簿 / 确认章三源合成一行。
 *
 * 与 designDocStatus（已交/未交，设计节点展示）的区别：本投影多带 `on_disk`（目录扫描）与
 * `confirmed`（确认章），让 agent 不打开看板也能读出「未登记 / 待确认 / 已落章」。
 *
 * 纯函数、不落盘：磁盘清单（`onDisk`）与 front-matter 策略（`policy`）由调用方（用例 / QueryState）
 * 经 DocRepository 端口读好后传入——application 不碰 fs（INV-7）。
 *
 * 行集 = 该类型要求的设计文档（含条件必交、含缺失项）∪ 磁盘实际存在的 .md（含清单外的额外件），
 * 逐份：
 *   - `on_disk`   = 目录扫描命中；
 *   - `registered` = 产物簿有 kind=design 且 path 命中该份；
 *   - `confirmed`  = 该产物已落章（`confirmedAt !== undefined`）；
 *   - `exempted`   = 有效豁免理由（front-matter design_exempt，空理由不算）；
 *   - `conditional`= 条件必交标记（仅声明了对应端侧时必交）。
 */
export function designDocRegistration(
  req: RequirementRecord,
  category: string | undefined,
  policy: DesignDocPolicy = EMPTY_DESIGN_DOC_POLICY,
  onDisk: readonly string[] = [],
): DesignDocRegistration[] {
  const dir = 'docs/requirements/' + req.id + '/design'
  const disk = new Set(onDisk)
  const artifacts = req.artifacts ?? []
  const rows: DesignDocRegistration[] = []
  const seen = new Set<string>()
  const collect = (name: string, conditional?: 'frontend' | 'backend'): void => {
    if (name.length === 0 || seen.has(name)) return
    seen.add(name)
    const art = artifacts.find(a => a.kind === 'design' && a.path.endsWith('/design/' + name))
    const reason = policy.exempt[name]
    rows.push({
      name,
      path: dir + '/' + name,
      on_disk: disk.has(name),
      registered: art !== undefined,
      confirmed: art?.confirmedAt !== undefined,
      ...(reason !== undefined && reason.trim() !== '' ? { exempted: reason } : {}),
      ...(conditional !== undefined ? { conditional } : {}),
    })
  }
  // 必交 ∪ sides 命中的条件必交在前（缺失项也列出，agent 才知道还差哪份），磁盘额外件补在后。
  for (const d of effectiveDesignDocs(category, policy.sides)) collect(d.name, d.conditional)
  for (const name of onDisk) collect(name)
  return rows
}

/**
 * 设计文档扫描端口的最小面（T-4）：application 只经端口读文档，不直接碰 fs（INV-7）。
 * `list` 的口径与提交路径（SubmitDesignArtifacts 的 designDocNames）一致：扁平列 design/ 目录、只认 .md。
 */
export interface DesignDocScanPort {
  exists(relPath: string): boolean
  read(relPath: string): Promise<string>
  list(relDir: string): readonly { name?: string; isFile?: boolean }[]
}

/** design/ 目录下已落盘的设计文档文件名（只认 .md；口径与 reqboard_submit(kind=design) 的扫描一致）。 */
export function designDocNamesOf(scan: Pick<DesignDocScanPort, 'list'>, reqId: string): string[] {
  const dir = 'docs/requirements/' + reqId + '/design'
  return scan.list(dir)
    .filter(e => e.isFile !== false && (e.name ?? '').endsWith('.md'))
    .map(e => e.name ?? '')
    .filter(n => n.length > 0)
}

/**
 * 逐份登记态投影（端口版，T-4）——扫设计目录 + 读 requirement.md front-matter 策略 +
 * `designDocRegistration` 三源合成。reqboard_status 与 reqboard_submit(kind=design) 共用
 * 同一份合成规则与同一扫描口径，避免"两处投影两套真相"。
 *
 * 目录不存在 / 无 .md → 仍返回必交清单（逐份 on_disk=false），让 agent 知道还差哪份。
 */
export async function designDocRegistrationOf(
  scan: DesignDocScanPort,
  req: RequirementRecord,
): Promise<DesignDocRegistration[]> {
  const policy = await designDocPolicyOf(scan, req)
  return designDocRegistration(req, req.category, policy, designDocNamesOf(scan, req.id))
}
