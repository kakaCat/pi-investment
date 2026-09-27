/**
 * 追溯数据装配（REQ-260926140539-457b FR-6）。
 *
 * **为什么有这一层**：canonical RTM YAML 按节点分文件存自己的那一段——
 *   - rtm-design.yml      → traceability.fr_to_design      + coverage.design
 *   - rtm-decomposing.yml → traceability.design_to_tasks / fr_to_tasks + coverage.implementation
 *   - rtm-accepting.yml   → traceability.task_to_tests / fr_to_tests   + coverage.testing
 * 而看板详情希望**任意节点**都能看到完整三级追溯链与相关覆盖度，故此处跨文件合并成
 * 单个投影，供各 StageDetailAssembler 挂到 body 上。
 *
 * **读盘复用 canonical 实现**：dsh-pmboard 不直接依赖 `yaml` 包，解析必须走
 * `tools/reqboard/src/rtm/file-io` 的 readRTM（同时也是"RTM 格式只有一个解析口径"的保证）。
 *
 * **降级语义（FR-9）**：RTM 是增强层。目录/文件缺失、YAML 解析失败一律视为"无数据"，
 * 返回空投影而不抛异常——详情的其它字段必须照常渲染。readRTM 本身已是"失败返回 null"。
 *
 * @module dsh-pmboard/stage-overview/assembler
 */

import {
  readRTM,
  requirementsDir,
  getRTMPath,
} from '../../../../tools/reqboard/src/rtm/file-io.js'
import type {
  TraceabilityProjection,
  DesignCoverageProjection,
  ImplementationCoverageProjection,
  TestingCoverageProjection,
} from '../shared/protocol.js'
// 仅类型引用（type-only），不产生运行时循环依赖
import type { AssembleContext } from '../application/query/QueryStageDetail.js'

/** 装配器可选注入项（host 侧读完 fs 后注入；client 不碰 fs）。 */
export interface AssembleStageOptions {
  designDocPolicy?: AssembleContext['designDocPolicy']
  /** REQ-260926140539-457b FR-6：工作区根，用于读 RTM 追溯数据。 */
  workspaceRoot?: string
}

/**
 * 把 host 注入项摊平进 AssembleContext。
 *
 * 单点收口的原因：此前 assembleStageDetail 与 assembleStageOverview **各自手写**一遍
 * 条件展开；后来给 AssembleContext 与调用方加了 workspaceRoot，两处展开都没跟上——
 * 而对象 spread 绕过 TS 多余属性检查，编译器**不报错**，字段被静默丢弃，
 * `ctx.workspaceRoot` 恒为 undefined、追溯数据永不出现（2026-09-27 实测定位）。
 */
export function contextOf(
  req: AssembleContext['req'],
  ledger: AssembleContext['ledger'],
  opts?: AssembleStageOptions,
): AssembleContext {
  return {
    req,
    ledger,
    ...(opts?.designDocPolicy !== undefined ? { designDocPolicy: opts.designDocPolicy } : {}),
    ...(opts?.workspaceRoot !== undefined ? { workspaceRoot: opts.workspaceRoot } : {}),
  }
}

/** 挂在节点 body 上的追溯投影（各节点只消费自己需要的那一段）。 */
export interface TraceabilityBundle {
  traceability?: TraceabilityProjection
  coverage?: {
    design?: DesignCoverageProjection
    implementation?: ImplementationCoverageProjection
    testing?: TestingCoverageProjection
  }
}

/** RTM 文件的读取形状（只声明本模块消费的字段，未知字段一律忽略）。 */
interface RtmFileLike {
  traceability?: Record<string, unknown>
  coverage?: Record<string, unknown>
}

/** 取对象；非对象一律当空。 */
function asRecord(v: unknown): Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {}
}

/** 取非空的映射表（空对象视为"没有"，以免给前端塞空洞）。 */
function asMap(v: unknown): Record<string, string[]> | undefined {
  const r = asRecord(v)
  const out: Record<string, string[]> = {}
  for (const [k, val] of Object.entries(r)) {
    if (Array.isArray(val)) out[k] = val.filter((x): x is string => typeof x === 'string')
  }
  return Object.keys(out).length > 0 ? out : undefined
}

/**
 * 装配某需求的完整追溯投影。
 *
 * @param workspaceRoot 工作区根（host 侧 deps.cwd；RTM 位于 <root>/docs/requirements/<reqId>/）
 * @param reqId 需求 id
 * @returns 合并后的 traceability / coverage；无任何 RTM 数据时返回空对象
 */
export function assembleTraceability(workspaceRoot: string, reqId: string): TraceabilityBundle {
  try {
    const reqDir = requirementsDir(workspaceRoot, reqId)

    const design = readRTM<RtmFileLike>(getRTMPath(reqDir, 'rtm-design.yml'))
    const decomposing = readRTM<RtmFileLike>(getRTMPath(reqDir, 'rtm-decomposing.yml'))
    const accepting = readRTM<RtmFileLike>(getRTMPath(reqDir, 'rtm-accepting.yml'))

    const dT = asRecord(design?.traceability)
    const cT = asRecord(decomposing?.traceability)
    const aT = asRecord(accepting?.traceability)
    const dC = asRecord(design?.coverage)
    const cC = asRecord(decomposing?.coverage)
    const aC = asRecord(accepting?.coverage)

    const traceability: TraceabilityProjection = {
      ...(asMap(dT['fr_to_design']) !== undefined ? { fr_to_design: asMap(dT['fr_to_design']) } : {}),
      ...(asMap(cT['design_to_tasks']) !== undefined ? { design_to_tasks: asMap(cT['design_to_tasks']) } : {}),
      ...(asMap(cT['fr_to_tasks']) !== undefined ? { fr_to_tasks: asMap(cT['fr_to_tasks']) } : {}),
      ...(asMap(aT['task_to_tests']) !== undefined ? { task_to_tests: asMap(aT['task_to_tests']) } : {}),
      ...(asMap(aT['fr_to_tests']) !== undefined ? { fr_to_tests: asMap(aT['fr_to_tests']) } : {}),
    }

    const coverage: NonNullable<TraceabilityBundle['coverage']> = {
      ...(Object.keys(asRecord(dC['design'])).length > 0
        ? { design: asRecord(dC['design']) as unknown as DesignCoverageProjection }
        : {}),
      ...(Object.keys(asRecord(cC['implementation'])).length > 0
        ? { implementation: asRecord(cC['implementation']) as unknown as ImplementationCoverageProjection }
        : {}),
      ...(Object.keys(asRecord(aC['testing'])).length > 0
        ? { testing: asRecord(aC['testing']) as unknown as TestingCoverageProjection }
        : {}),
    }

    return {
      ...(Object.keys(traceability).length > 0 ? { traceability } : {}),
      ...(Object.keys(coverage).length > 0 ? { coverage } : {}),
    }
  } catch (err) {
    // FR-9：RTM 是增强层，读盘异常绝不能打断详情装配
    console.warn('[stage-overview] 追溯数据装配失败（已降级为无追溯）:', reqId, err)
    return {}
  }
}
