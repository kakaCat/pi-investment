/**
 * SectorAnalysisTool - 行业分析工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { sectorAnalysisPrompt, SectorAnalysisParams, SectorAnalysisResult } from './prompt';

/**
 * 行业分析工具类
 */
export class SectorAnalysisTool extends BaseTool<SectorAnalysisParams, SectorAnalysisResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'sector_analysis',
    category: 'market',
    version: '1.0.1',
    timeoutMs: 40000,
  };

  protected readonly prompt = sectorAnalysisPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(_args: SectorAnalysisParams): ValidationResult {
    // 参数都是可选的，直接通过
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: SectorAnalysisParams, _context: ToolContext): Promise<SectorAnalysisResult> {
    const requestedDays = args.days || 5;
    const result: any = await this.qv2.getSectorAnalysis({
      sector: args.sector,
      days: requestedDays,
    });

    // 2026-09-11 修复（REQ-342799）：实测后端 /api/market/sectors 路由不接收 days 参数
    // （curl days=5 与 days=20 返回完全相同的 change_pct），返回的是『最新快照』单一窗口。
    // 此前工具对外表现为支持多窗口，导致分析时把单日快照误当 5/20 日区间涨幅使用。
    // 同时：client.unwrap 会剥掉外层 {success,data}，路由在数据源故障回退 DB 快照时标注的
    // degraded/stale/stale_from 字段位于外层 → 会被静默丢弃。此处显式补齐，避免把陈旧快照当实时。
    return {
      ...(result as any),
      days_requested: requestedDays,
      window_note: '后端该接口忽略 days，返回单一窗口（最新快照）；请勿当作 N 日区间涨幅',
      data_degraded: (result as any)?.degraded ?? null,
      data_stale: (result as any)?.stale ?? null,
      stale_from: (result as any)?.stale_from ?? null,
    } as SectorAnalysisResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: SectorAnalysisResult, _context: ToolContext): ToolResponse<SectorAnalysisResult> {
    return {
      success: true,
      data: result,
    };
  }
}
