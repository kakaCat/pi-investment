/**
 * 设计文档交付状态（REQ-81aabd FR-2）。
 *
 * 设计节点要回答"设计文档交齐了没"。此前只把分类模板要求的**文件名清单**摆在页面上，
 * 与需求目录里实际交了什么脱节（design/*.md 自动发现成 notes，页面上只显示模板名）。
 * 这里按类型模板逐份核对需求台账里 design/<name> 是否已登记，产出 { name, path, submitted }。
 *
 * 纯函数：不读 fs、不写盘——文件系统扫描仍只在 adapters（INV-7）；调用方是设计节点装配器。
 * **不参与任何闸门**：闸门由 STAGE_ARTIFACT_REQUIREMENTS / ARTIFACT_CONFIRM_GATES 决定，
 * 本模块只产出展示数据（2026-09-17 用户裁定选项 A：只加呈现，不动门禁）。
 *
 * @module dsh-pmboard/application/internal/design-docs
 */
import { CATEGORY_DELTAS } from './category-doc-sets.js'
import type { DesignDocStatus, RequirementRecord } from '../../shared/protocol.js'

/** 分类模板要求的设计文档 → 逐份交付状态（需求目录里已登记 = 已交）。 */
export function designDocStatus(req: RequirementRecord, category: string): DesignDocStatus[] {
  const required = CATEGORY_DELTAS.find(d => d.category === category)?.requiredDesignDocs ?? []
  const artifacts = req.artifacts ?? []
  return required.map(name => {
    const suffix = '/design/' + name
    return {
      name,
      path: 'docs/requirements/' + req.id + suffix,
      submitted: artifacts.some(a => a.path.endsWith(suffix)),
    }
  })
}
