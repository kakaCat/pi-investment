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

    // 2026-09-11（REQ-733c5e, w-348bf585）：纠正上一版写死的错误结论。
    // 实测：后端 days>1 时按 DB 日快照复合（data.window 自述 basis=compounded_daily_snapshots，
    // 快照深度不足会诚实降级标注 days_computed）。此前本工具硬编码『后端忽略 days，返回单一窗口』
    // 与后端 data.window 自述互相矛盾——改为透传后端 window，不再伪造结论。
    const data: any = (result as any)?.data ?? {};
    const inds: any[] = Array.isArray(data?.industries) ? data.industries : [];
    const codes = inds.map((x: any) => String(x?.code ?? '')).filter(Boolean);
    const taxonomy = codes.some((c) => c.startsWith('new_'))
      ? 'legacy(new_*, 49个申万口径)'
      : codes.some((c) => c.startsWith('BK'))
        ? 'eastmoney(BK*, 496个东财口径)'
        : 'unknown';
    return {
      ...(result as any),
      days_requested: requestedDays,
      window: data?.window ?? null,
      window_note: data?.window?.note ?? data?.window_note ?? null,
      taxonomy,
      taxonomy_note: '板块列表存在两套口径（legacy new_* 49个 / eastmoney BK* 496个），随数据源/快照回退切换；同一入参两次调用可能返回不同口径且不可比，做结论前先核对 taxonomy 与 window.days_computed',
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
