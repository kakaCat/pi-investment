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
import type { DesignDocStatus, RequirementRecord } from '../../shared/protocol.js'

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
