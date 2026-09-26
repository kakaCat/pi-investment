/**
 * 覆盖度门禁校验（REQ-260926140539-457b FR-9 / architecture.md）。
 *
 * 阈值单点定义：设计 100%、拆分/实施 100%、验收 ≥80%。
 * 不过门禁时 message 必须点名**缺哪一项**（可照着补），不得只报一个百分比。
 *
 * @module @pi-investment/reqboard/rtm/validator
 */
import type { Coverage, GateResult } from './types.js'

/** 各节点覆盖度门禁阈值（百分比）。 */
export const GATE_THRESHOLDS: Readonly<Record<string, number>> = {
  design: 100,
  decomposing: 100,
  implementing: 100,
  accepting: 80,
}

/** 取节点阈值；未知节点默认 100。 */
export function thresholdFor(stage: string): number {
  return GATE_THRESHOLDS[stage] ?? 100
}

/** 覆盖度门禁校验器。 */
export class RTMValidator {
  /** 设计/实施覆盖度校验（threshold 必填）。 */
  checkGate(stage: string, coverage: Coverage, threshold?: number): GateResult {
    const th = threshold ?? thresholdFor(stage)
    const passed = coverage.rate >= th
    if (passed) {
      return { passed: true, stage, coverage, threshold: th }
    }
    const missing = coverage.uncovered.length > 0
      ? coverage.uncovered.join('、')
      : `共 ${coverage.total} 项`
    return {
      passed: false,
      stage,
      coverage,
      threshold: th,
      message: `${stage} 覆盖度不足（${coverage.rate}% < ${th}%），缺少以下项：${missing}`,
    }
  }

  /** 设计门禁：所有 FR 必须有设计。 */
  checkDesign(coverage: Coverage): GateResult {
    return this.checkGate('design', coverage, GATE_THRESHOLDS.design)
  }

  /** 实施门禁：所有设计章节必须有任务。 */
  checkImplementation(coverage: Coverage): GateResult {
    return this.checkGate('decomposing', coverage, GATE_THRESHOLDS.decomposing)
  }

  /** 验收门禁：测试覆盖度 ≥80%。 */
  checkAcceptance(coverage: Coverage): GateResult {
    return this.checkGate('accepting', coverage, GATE_THRESHOLDS.accepting)
  }
}

/** 便捷单例。 */
export const rtmValidator = new RTMValidator()
