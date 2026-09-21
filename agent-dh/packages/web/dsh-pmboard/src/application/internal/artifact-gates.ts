/**
 * 产物登记与分类感知闸门（REQ-31e11f t4）。
 *
 * 「节点完成 = 节点产物就位」的代码级落地：
 *   - registerArtifact()：产物登记幂等助手（同 stage+kind+path 不重复）；
 *   - assertArtifactGates()：状态转移前的两级校验——
 *     ① 产物存在门（missing_artifact）：该分类启用的阶段，必备产物已登记；
 *     ② 五道人工确认门（artifact_not_confirmed）：对应 kind 的产物须人确认（confirmedAt）。
 *
 * 分类感知：按 CATEGORY_FLOW_PROFILES 过滤该分类生效的门——bug 免需求分析门、
 * spike/doc/chore 只保留验收+归档门。存量需求（artifacts 字段 undefined/空）不硬拦，
 * 仅标记（向后兼容，避免锁死历史工作）。
 *
 * 2026-09-21 用户裁定：design>decomposing 不再用 planApproved 特判（原注释见 git 历史）——
 * 设计阶段只写设计文档，该门与拆分计划批准门（decomposing>implementing 锚定
 * decomposition 产物）都走通用 artifact.confirmedAt 判定。
 *
 * @module dsh-pmboard/host/artifact-gates
 */
import {
  confirmGateKindFor,
  flowProfileFor,
  STAGE_ARTIFACT_REQUIREMENTS,
  type ArtifactKind,
  type RequirementRecord,
  type RequirementStatus,
  type StageArtifact,
  type StageKey,
} from '../../shared/protocol.js'

// ---------------------------------------------------------------------------
// 产物登记（幂等）
// ---------------------------------------------------------------------------

/**
 * 向 req.artifacts 登记一条产物（就地修改）。
 * 幂等：同 stage+kind+path 已存在 → 不重复 push，返回 false。
 */
export function registerArtifact(
  req: RequirementRecord,
  artifact: StageArtifact,
): boolean {
  req.artifacts ??= []
  const already = req.artifacts.some(
    a => a.stage === artifact.stage && a.kind === artifact.kind && a.path === artifact.path,
  )
  if (already) return false
  req.artifacts.push(artifact)
  return true
}

// ---------------------------------------------------------------------------
// 成组落章（REQ-2d1c74 FR-2/FR-3）
// ---------------------------------------------------------------------------

/**
 * 按确认语义收集待落章产物：kind=design **成组**（该需求全部 design 产物一次落章），
 * 其余 kind 维持首份（历史语义）。三条确认通道（弹框/文字证据/看板一键）共用，
 * 保证"一次确认设计 = 全部设计文档都有章"的口径全仓只有这一处。
 * 空数组 = 没有该 kind 产物（调用方按 missing_artifact 处理）。
 */
export function artifactsToConfirm(req: RequirementRecord, kind: ArtifactKind): StageArtifact[] {
  const all = (req.artifacts ?? []).filter(a => a.kind === kind)
  return kind === 'design' ? all : all.slice(0, 1)
}

// ---------------------------------------------------------------------------
// 分类感知闸门（两级校验）
// ---------------------------------------------------------------------------

/** 闸门校验结果（成功 → undefined；失败 → 结构化原因）。 */
export interface GateFailure {
  code:
    | 'missing_artifact'
    | 'artifact_not_confirmed'
    // ── 内容闸门（REQ-d3e61a）：读文档**正文**的校验，与上面两级「登记态」正交互补 ──
    | 'requirement_uncovered'
    | 'dangling_reference'
    | 'orphan_clause'
    | 'design_orphan'
    | 'no_e2e_case'
    | 'acceptance_incomplete'
    | 'task_card_incomplete'
    | 'tbd_not_cleared'
    // ── 需求文档格式闸门（编号规范强制）──
    | 'requirement_missing_clauses'
    | 'requirement_clause_sequence_gap'
    | 'requirement_clause_duplicates'
    // ── 设计阶段规范化（REQ-2d1c74）：G2 完整性门 + 拆分内容硬门 ──
    | 'design_doc_incomplete'
    | 'design_contains_decomposition'
  /** 缺/待确认的产物 kind */
  kind: ArtifactKind
  /** 提示消息（含产物 path 或缺失说明） */
  message: string
  /** 结构化缺口（如缺失的根编号清单）：供 agent 精确修复与 UI 标红 */
  gaps?: string[]
}

/**
 * 该分类下，from 状态对应的必备产物 kind 列表（按 STAGE_ARTIFACT_REQUIREMENTS 过滤）。
 * 只检查「from 状态」的产物是否就位——转移的源头节点必须已完成。
 */
function requiredKindsFor(
  category: RequirementRecord['category'],
  from: RequirementStatus,
): readonly ArtifactKind[] {
  // 分类未启用该阶段 → 不要求产物
  if (!flowProfileFor(category).stages.includes(from as StageKey)) return []
  return STAGE_ARTIFACT_REQUIREMENTS[from as StageKey] ?? []
}

/**
 * 状态转移前的两级产物闸门校验。
 *
 * 在 assertReqTransition **之后**、真正写盘之前调用。
 *
 * 两级：
 *  ① 产物存在门：该分类启用的 from 阶段必备产物已登记（存量需求不硬拦）；
 *  ② 人工确认门：confirmGateKindFor 返回的 kind，对应产物须 confirmedAt（存量不硬拦）。
 *
 * 2026-09-21 用户裁定：design>decomposing 不再特殊（原用 planApproved 判定）——
 * 设计阶段只写设计文档，统一走通用 artifact.confirmedAt 判定（kind=design）。
 *
 * @returns GateFailure | undefined（undefined = 通过）
 */
export function assertArtifactGates(
  req: RequirementRecord,
  from: RequirementStatus,
  to: RequirementStatus,
): GateFailure | undefined {
  // 取消需求（*>canceled）是**放弃路径**，不是节点推进——不适用「节点完成=产物就位」闸门。
  // 否则形成死锁：想取消一个卡在 decomposing 的需求，却被要求先交出 decomposition 产物
  // （2026-09-20 实测：REQ-6cbbf7 人工点取消被 missing_artifact 拒绝，看板无法解锁）。
  // gate-post-chain 早已声明「取消需求不进链」，这里把产物存在门/确认门一并豁免。
  if (to === 'canceled') return undefined

  // 存量需求（无 artifacts 字段或空数组）→ 不硬拦（向后兼容）
  const artifacts = req.artifacts
  const isLegacy = artifacts === undefined || artifacts.length === 0

  // ── 第一级：产物存在门 ────────────────────────────────────────────────
  const requiredKinds = requiredKindsFor(req.category, from)
  for (const kind of requiredKinds) {
    const found = artifacts?.find(a => a.stage === from && a.kind === kind)
    if (found === undefined && !isLegacy) {
      return {
        code: 'missing_artifact',
        kind,
        message: '节点产物缺失：' + from + ' 阶段须先完成产物（kind=' + kind + '）并登记到 req.artifacts',
      }
    }
  }

  // ── 第二级：五道人工确认门 ────────────────────────────────────────────
  const gateKind = confirmGateKindFor(req.category, from, to)
  if (gateKind !== undefined && !isLegacy) {
    // REQ-2d1c74 FR-2：kind=design 改「成组确认」判定——原来 find 第一份，
    // 第一份有章就放行，其余 design 产物（含确认后新自动发现的那份）可无章绕过 G2。
    // 现在 filter 全部、任一未确认即拒，未确认路径进 gaps 供精确修复与 UI 标红。
    // （design>decomposing 的 planApproved 特判已于 2026-09-21 移除——设计阶段只写设计文档，
    //   拆分计划的批准门在 decomposing>implementing。）
    const pool = (artifacts ?? []).filter(a =>
      gateKind === 'design' ? a.kind === 'design' : (a.stage === from && a.kind === gateKind))
    if (pool.length === 0) {
      return {
        code: 'missing_artifact',
        kind: gateKind,
        message: '节点产物缺失：' + from + ' 阶段须先完成产物（kind=' + gateKind + '）并登记',
      }
    }
    const unconfirmed = pool.filter(a => a.confirmedAt === undefined)
    if (unconfirmed.length > 0) {
      return {
        code: 'artifact_not_confirmed',
        kind: gateKind,
        gaps: unconfirmed.map(a => a.path),
        message: '产物待确认：' + unconfirmed.map(a => a.path).join('、') + '（kind=' + gateKind + '）——请人在项目看板一键确认后放行',
      }
    }
  }

  return undefined
}

// ---------------------------------------------------------------------------
// 阶段通知简版
// ---------------------------------------------------------------------------

/**
 * 产物登记成功的通知文案（阶段通知简版）。
 * 调用方负责实际发送（feishu_notify 或 logger.info 降级）。
 */
export function artifactNotifyText(
  req: RequirementRecord,
  artifact: StageArtifact,
): string {
  return '[reqboard] 产物已登记，请人审阅确认'
    + '\n需求：' + req.id + ' ' + req.title
    + '\n节点：' + artifact.stage
    + '\n产物：' + artifact.path + '（kind=' + artifact.kind + '）'
    + '\n确认入口：项目看板 → 需求卡 → 「待确认」一键确认'
}
