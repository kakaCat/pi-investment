import type { TaskCoverage, FRMetadata } from '../types/rtm.js';

/**
 * 覆盖度检查结果
 */
export interface CoverageCheckResult {
  /** FR 总数 */
  total_frs: number;
  /** 被覆盖的 FR 数量 */
  covered_frs: number;
  /** 未被覆盖的 FR 列表 */
  unreceived_clauses: string[];
  /** 覆盖率（百分比） */
  coverage_rate: number;
}

/**
 * 覆盖度检查器
 * 校验所有 FR 是否被任务覆盖
 */
export class CoverageChecker {
  /**
   * 检查覆盖度
   * @param frMetadata 所有 FR 元数据
   * @param taskCoverage 任务覆盖追踪列表
   * @returns 覆盖度检查结果
   */
  static checkCoverage(
    frMetadata: FRMetadata[],
    taskCoverage: TaskCoverage[]
  ): CoverageCheckResult {
    // 1. 收集所有 FR ID
    const allFRs = new Set(frMetadata.map(fr => fr.id));
    
    // 2. 收集已被任务覆盖的 FR ID
    const coveredFRs = new Set<string>();
    for (const tc of taskCoverage) {
      for (const frId of tc.covers_frs) {
        coveredFRs.add(frId);
      }
    }
    
    // 3. 计算未覆盖的 FR
    const unreceivedClauses: string[] = [];
    for (const frId of allFRs) {
      if (!coveredFRs.has(frId)) {
        unreceivedClauses.push(frId);
      }
    }
    
    // 4. 计算覆盖率
    const totalFRs = allFRs.size;
    const coveredCount = coveredFRs.size;
    const coverageRate = totalFRs > 0 ? Math.round((coveredCount / totalFRs) * 100) : 100;
    
    return {
      total_frs: totalFRs,
      covered_frs: coveredCount,
      unreceived_clauses: unreceivedClauses.sort(), // 排序，方便测试
      coverage_rate: coverageRate
    };
  }
  
  /**
   * 验证覆盖度（100% 覆盖时通过，否则抛出错误）
   * @param frMetadata 所有 FR 元数据
   * @param taskCoverage 任务覆盖追踪列表
   * @throws Error 当覆盖度 < 100% 时
   */
  static validateCoverage(
    frMetadata: FRMetadata[],
    taskCoverage: TaskCoverage[]
  ): void {
    const result = this.checkCoverage(frMetadata, taskCoverage);
    
    if (result.unreceived_clauses.length > 0) {
      const unreceivedList = result.unreceived_clauses.join(', ');
      throw new Error(
        `需求覆盖度不足（${result.coverage_rate}%）：未覆盖的 FR: ${unreceivedList}`
      );
    }
  }
}
