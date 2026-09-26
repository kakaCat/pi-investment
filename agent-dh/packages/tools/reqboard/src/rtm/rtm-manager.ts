import { scanFRDirectory } from './fr-parser.js';
import type { TaskCoverage, AcceptanceTracking, FRMetadata, RTMData } from '../types/rtm.js';

/**
 * RTM 管理器
 * 负责填充和更新需求追踪矩阵数据
 */
export class RTMManager {
  /**
   * 填充任务覆盖追踪
   * @param reqDir 需求目录
   * @param tasks 任务列表（含 requirement_refs）
   * @returns 任务覆盖追踪列表
   */
  static fillTaskCoverage(
    reqDir: string,
    tasks: Array<{
      key: string;
      title: string;
      requirement_refs?: string[];
    }>
  ): TaskCoverage[] {
    // 1. 扫描所有 FR 文件
    const frMetadata = scanFRDirectory(reqDir);
    const frMap = new Map<string, FRMetadata>();
    for (const fr of frMetadata) {
      frMap.set(fr.id, fr);
    }
    
    // 2. 为每个任务生成 task_coverage
    const taskCoverage: TaskCoverage[] = [];
    
    for (const task of tasks) {
      const coversFRs = task.requirement_refs || [];
      const coversAcceptance: string[] = [];
      
      // 提取所有接收的 FR 的验收标准
      for (const frId of coversFRs) {
        const fr = frMap.get(frId);
        if (fr) {
          // 添加该 FR 的所有验收标准 ID
          for (const ac of fr.acceptance_criteria) {
            coversAcceptance.push(ac.id);
          }
        }
      }
      
      taskCoverage.push({
        task_id: '', // 实际使用时会填充真实的 task_id
        task_key: task.key,
        task_title: task.title,
        covers_frs: coversFRs,
        covers_acceptance: coversAcceptance,
        assigned_at: Date.now(),
        status: 'todo'
      });
    }
    
    return taskCoverage;
  }
  
  /**
   * 填充验收追踪
   * @param frMetadata FR 元数据列表
   * @returns 验收追踪列表（所有初始为 pending）
   */
  static fillAcceptanceTracking(frMetadata: FRMetadata[]): AcceptanceTracking[] {
    const tracking: AcceptanceTracking[] = [];
    
    for (const fr of frMetadata) {
      for (const ac of fr.acceptance_criteria) {
        tracking.push({
          acceptance_id: ac.id,
          fr_id: fr.id,
          description: ac.description,
          verification: ac.verification,
          status: 'pending',
          evidence: null,
          judged_at: null,
          judged_by: null,
          user_feedback: null
        });
      }
    }
    
    return tracking;
  }
  
  /**
   * 更新验收追踪
   * @param tracking 现有的验收追踪列表
   * @param judgements 裁决结果（acceptance_id → { status, evidence?, feedback? }）
   * @param judgedBy 裁决人
   * @returns 更新后的验收追踪列表
   */
  static updateAcceptanceTracking(
    tracking: AcceptanceTracking[],
    judgements: Record<string, {
      status: 'passed' | 'failed';
      evidence?: string;
      feedback?: string;
    }>,
    judgedBy: string = 'system'
  ): AcceptanceTracking[] {
    const updated = [...tracking];
    const now = Date.now();
    
    for (const item of updated) {
      const judgement = judgements[item.acceptance_id];
      if (judgement) {
        item.status = judgement.status;
        item.evidence = judgement.evidence || null;
        item.user_feedback = judgement.feedback || null;
        item.judged_at = now;
        item.judged_by = judgedBy;
      }
    }
    
    return updated;
  }
}
