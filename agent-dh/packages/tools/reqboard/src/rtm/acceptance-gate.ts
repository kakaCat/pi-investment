import type { AcceptanceTracking } from '../types/rtm.js';

/**
 * 门禁检查结果
 */
export interface GateCheckResult {
  /** 总验收项数 */
  total: number;
  /** 通过项数 */
  passed: number;
  /** 失败项数 */
  failed: number;
  /** 待验项数 */
  pending: number;
  /** 通过率（百分比） */
  pass_rate: number;
  /** 门禁状态 */
  gate_status: 'passed' | 'blocked' | 'pending';
  /** 失败项列表 */
  failed_items: Array<{
    acceptance_id: string;
    description?: string;
    user_feedback?: string | null;
  }>;
}

/**
 * 验收门禁
 * 检查验收通过条件并决定是否自动归档
 */
export class AcceptanceGate {
  /**
   * 检查门禁
   * @param acceptanceTracking 验收追踪列表
   * @returns 门禁检查结果
   */
  static checkGate(acceptanceTracking: AcceptanceTracking[]): GateCheckResult {
    const total = acceptanceTracking.length;
    const passed = acceptanceTracking.filter(a => a.status === 'passed').length;
    const failed = acceptanceTracking.filter(a => a.status === 'failed').length;
    const pending = acceptanceTracking.filter(a => a.status === 'pending').length;
    
    // 计算通过率
    const passRate = total > 0 ? Math.round((passed / total) * 100) : 0;
    
    // 确定门禁状态
    let gateStatus: 'passed' | 'blocked' | 'pending';
    if (pending > 0) {
      gateStatus = 'pending'; // 还有待验项
    } else if (failed > 0) {
      gateStatus = 'blocked'; // 有失败项，门禁拦截
    } else {
      gateStatus = 'passed'; // 全部通过
    }
    
    // 收集失败项
    const failedItems = acceptanceTracking
      .filter(a => a.status === 'failed')
      .map(a => ({
        acceptance_id: a.acceptance_id,
        description: a.description,
        user_feedback: a.user_feedback
      }));
    
    return {
      total,
      passed,
      failed,
      pending,
      pass_rate: passRate,
      gate_status: gateStatus,
      failed_items: failedItems
    };
  }
  
  /**
   * 是否应该自动归档
   * @param gateResult 门禁检查结果
   * @returns 是否应该自动归档
   */
  static shouldAutoArchive(gateResult: GateCheckResult): boolean {
    return gateResult.gate_status === 'passed';
  }
}
