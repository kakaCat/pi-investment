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
 * planning>decomposing 的门用既有 planApproved 判定（plan.approvedAt），
 * 不重复要求 artifact.confirmedAt——把这道门映射到 planApproved 检查即可。
 *
 * @module dsh-pmboard/host/artifact-gates
 */
import {
  confirmGateKindFor,
  flowProfileFor,
  planApproved,
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
// 分类感知闸门（两级校验）
// ---------------------------------------------------------------------------

/** 闸门校验结果（成功 → undefined；失败 → 结构化原因）。 */
export interface GateFailure {
  code: 'missing_artifact' | 'artifact_not_confirmed'
  /** 缺/待确认的产物 kind */
  kind: ArtifactKind
  /** 提示消息（含产物 path 或缺失说明） */
  message: string
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
 * planning>decomposing 特殊：用既有 planApproved 判定，不查 artifact.confirmedAt。
 *
 * @returns GateFailure | undefined（undefined = 通过）
 */
export function assertArtifactGates(
  req: RequirementRecord,
  from: RequirementStatus,
  to: RequirementStatus,
): GateFailure | undefined {
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
    // planning>decomposing 特殊：用既有 planApproved 判定
    if (from === 'planning' && to === 'decomposing') {
      if (!planApproved(req)) {
        return {
          code: 'artifact_not_confirmed',
          kind: gateKind,
          message: '实施计划尚未获人批准：请在项目看板点「批准计划」后再拆分落库',
        }
      }
      return undefined
    }
    // 其余门：查 artifact.confirmedAt
    const artifact = artifacts?.find(a => a.stage === from && a.kind === gateKind)
    if (artifact === undefined && !isLegacy) {
      return {
        code: 'missing_artifact',
        kind: gateKind,
        message: '节点产物缺失：' + from + ' 阶段须先完成产物（kind=' + gateKind + '）并登记',
      }
    }
    if (artifact !== undefined && artifact.confirmedAt === undefined) {
      return {
        code: 'artifact_not_confirmed',
        kind: gateKind,
        message: '产物待确认：' + artifact.path + '（kind=' + gateKind + '）——请人在项目看板一键确认后放行',
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
