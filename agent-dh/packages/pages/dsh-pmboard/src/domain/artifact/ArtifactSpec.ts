/**
 * 产物规约（REQ-47939a t2）——产物分类 + 节点必备产物 + 人工确认门 + 归档文档清单规则。
 *
 * 为什么单独成文件：产物"是什么种类、哪个节点必须有、哪道门要人确认、归档要哪些文档"
 * 是四条纯数据规则，此前散在 shared/protocol.ts 与 host/sync-artifacts.ts（D2）。
 * 搬到 domain 后成为唯一实现处（INV-7），protocol 与 sync-artifacts 只做再导出/调用。
 *
 * 注释随代码搬；纯数据 + 纯函数（零 import 副作用、不碰时间与随机数）。
 */

import { fmt } from '../text/fmt.js'
import type { RequirementCategory } from '../requirement/Requirement.js'
import type { StageKey } from '../requirement/RequirementStatus.js'

/**
 * 产物种类。前六类 = 六道节点必备产物（闸门依赖）；design = 设计文档
 * （REQ-81aabd：设计节点的交付物，按分类模板逐份核对已交/未交；
 *  2026-09-21 用户裁定：design 升格为 G2 闸门产物——设计阶段只写设计文档，拆分计划归拆分阶段）；
 * notes = 过程产物兜底（REQ-2e9473 t11 自动发现：原型 html / 笔记等不属必备门禁的文件）。
 */
export type ArtifactKind = 'requirement' | 'plan' | 'decomposition' | 'design' | 'task_detail' | 'verification' | 'archive' | 'notes' | 'task_output'
export const ALL_ARTIFACT_KINDS: readonly ArtifactKind[] = ['requirement', 'plan', 'decomposition', 'design', 'task_detail', 'verification', 'archive', 'notes', 'task_output']

/** 每节点必备产物（feature 全流水线基准；分类档案可再裁剪）。 */
export const STAGE_ARTIFACT_REQUIREMENTS: Readonly<Partial<Record<StageKey, readonly ArtifactKind[]>>> = {
  brainstorming: ['requirement'],
  // 2026-09-21 用户裁定：design 阶段的必备产物 = 设计文档（不再是 plan）；拆分计划归拆分阶段
  design: ['design'],
  decomposing: ['decomposition'],
  implementing: ['task_detail'], // 粒度=每任务一份 tasks/t-xxx.md；task_report 汇报追加
  accepting: ['verification'],
  archived: ['archive'],
}

/**
 * 人工确认门表：`from>to` → 须已确认的产物 kind。
 * 语义：产物存在 ≠ 人已审阅——产物登记即发通知请人审阅，人看文档/交流改进后
 * 在看板一键确认（confirmedAt/confirmedBy），才放行对应转移。
 *
 * REQ-e3b6a0 t2：**定义已迁入 `domain/gate/GateCatalog.ts`**（人工闸门唯一事实源），
 * 本处只做再导出以保持既有调用点（protocol / MoveRequirement / 看板）不变。
 */
export { ARTIFACT_CONFIRM_GATES } from '../gate/GateCatalog.js'

/** 归档材料里的一条文档。 */
export interface ArchiveDoc {
  /** requirement=需求说明 / plan=拆分计划 / verification=验收材料 / retro=复盘 / notes=其他 */
  kind: 'requirement' | 'plan' | 'verification' | 'retro' | 'notes'
  path: string
}

/**
 * 需求类型 → 归档时的文档要求。规范文档：agent-dh/docs/architecture/requirement-archive.md。
 * 校验是**代码级**的：缺必填文档或合并去向 → 归档材料提交被拒。
 */
export interface ArchiveDocRule {
  /** 是否**必须**申报项目说明书（L1/L2）的更新点——改变项目级认知的类型才要求。 */
  requireManual: boolean
  /** 需求目录内必填的文档 kind */
  requiredDocs: readonly ArchiveDoc['kind'][]
  /** 必须合并进的项目文档前缀（合并去向必须落在这些目录里） */
  mergeTargets: readonly string[]
  /** 人读的一句话规则说明 */
  note: string
}

export const ARCHIVE_DOC_RULES: Readonly<Record<RequirementCategory, ArchiveDocRule>> = {
  // 合并去向**只允许落在既有文档规范目录内**（docs/adr|architecture|guides|rfcs|work-logs|strategy-research
  // 及其 agent-dh 对应目录）——归档不许自创平行体系（规范见 docs/DOCUMENT-MANAGEMENT-PLAN.md
  // 与 agent-dh/docs/architecture/requirement-archive.md）。
  feature: {
    requireManual: true,
    requiredDocs: ['requirement', 'plan', 'verification'],
    mergeTargets: ['agent-dh/docs/architecture/', 'agent-dh/docs/guides/', 'docs/architecture/', 'docs/guides/'],
    note: '功能：能力/接口变了 → 必须更新架构或使用指南（否则新人只能读代码）',
  },
  bug: {
    requireManual: false,
    requiredDocs: ['requirement', 'verification', 'retro'],
    mergeTargets: ['agent-dh/docs/guides/', 'agent-dh/docs/architecture/', 'docs/guides/', 'docs/architecture/'],
    note: fmt('缺陷：根因与防回归写进 guides/（故障排查手册）或 architecture/（机制性根因）——规范没有单独的 known-issues 目录，别自创平行体系', {}),
  },
  doc: {
    requireManual: false,
    requiredDocs: ['requirement', 'verification'],
    mergeTargets: ['agent-dh/docs/', 'docs/'],
    note: '文档类需求：产出本身就是文档，直接合并进 docs/ 相应子目录',
  },
  refactor: {
    requireManual: true,
    requiredDocs: ['requirement', 'plan', 'verification', 'retro'],
    mergeTargets: ['docs/adr/', 'agent-dh/docs/architecture/', 'docs/architecture/', 'agent-dh/docs/work-logs/', 'docs/work-logs/'],
    note: '重构：重大结构决策进 adr/，架构说明同步更新——否则文档与代码互相说谎',
  },
  spike: {
    requireManual: true,
    requiredDocs: ['requirement', 'retro'],
    mergeTargets: ['docs/rfcs/', 'agent-dh/docs/rfcs/', 'docs/architecture/', 'agent-dh/docs/architecture/', 'docs/strategy-research/'],
    note: '调研：产物是结论（含被证伪的假设）——成提案进 rfcs/，成认知进 architecture/，策略类进 strategy-research/',
  },
  chore: {
    requireManual: false,
    requiredDocs: ['requirement', 'verification'],
    mergeTargets: ['agent-dh/docs/work-logs/', 'docs/work-logs/'],
    note: '杂项/维护：留一条工作记录（work-logs，按月归档）即可，别把运维细节塞进架构文档',
  },
}

/** 文件名 → 必备产物种类映射（未命中 → notes）。 */
const NAME_TO_KIND: ReadonlyArray<readonly [RegExp, ArtifactKind]> = [
  [/^requirement\.md$/, 'requirement'],
  [/^plan\.md$/, 'plan'],
  [/^decomposition\.md$/, 'decomposition'],
  [/^design\/.+\.md$/, 'design'],
  [/^verification\.md$/, 'verification'],
  [/^archive\.md$/, 'archive'],
  [/^tasks\/t-[a-z0-9]+\.md$/, 'task_detail'],
]

/**
 * 该 kind 是否「设计文档」产物（REQ-2d1c74 FR-3：拆分内容扫描与成组落章都以它判定）。
 * 单独成函数是因为 http/ 适配层禁止出现状态/种类字面量（layer-boundary INV-2）。
 */
export function isDesignArtifactKind(kind: string): boolean {
  return kind === 'design'
}

/**
 * 从相对需求目录的路径推断产物种类（REQ-2e9473 t11/W4）。
 * 从 host/sync-artifacts.ts 迁入 domain——分类规则是纯判定，与 fs 扫描解耦后
 * sync-artifacts 只负责遍历目录（INV-7）。
 */
export function kindForRelPath(rel: string): ArtifactKind {
  for (const [re, kind] of NAME_TO_KIND) {
    if (re.test(rel)) return kind
  }
  return 'notes'
}
