/**
 * OpportunityScanTool - 机会扫描工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { opportunityScanPrompt, OpportunityScanParams, OpportunityScanResult } from './prompt';

export class OpportunityScanTool extends BaseTool<OpportunityScanParams, OpportunityScanResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'opportunity_scan',
    category: 'strategy',
    version: '2.0.1',
    timeoutMs: 60000,
  };

  protected readonly prompt = opportunityScanPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: OpportunityScanParams): ValidationResult {
    if (args.scan_type) {
      const validTypes = ['technical', 'fundamental', 'hybrid'];
      if (!validTypes.includes(args.scan_type)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'scan_type',
          issue: 'scan_type 必须是 technical/fundamental/hybrid',
          received: args.scan_type,
          expected: 'technical | fundamental | hybrid',
        };
      }
    }

    if (args.pool_id !== undefined && (!Number.isInteger(args.pool_id) || args.pool_id <= 0)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'pool_id',
        issue: 'pool_id 必须是正整数',
        received: args.pool_id,
        expected: '正整数',
      };
    }

    if (args.min_score !== undefined && (typeof args.min_score !== 'number' || args.min_score < 0 || args.min_score > 100)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'min_score',
        issue: 'min_score 必须是 0-100 的数字',
        received: args.min_score,
        expected: '0-100',
      };
    }

    return { success: true };
  }

  protected async execute(
    args: OpportunityScanParams,
    _context: ToolContext
  ): Promise<OpportunityScanResult> {
    const raw: any = await this.qv2.scanOpportunities({
      scan_type: args.scan_type || 'hybrid',
      pool_id: args.pool_id,
      symbols: args.symbols,
      min_score: args.min_score || 60,
    });

    return {
      opportunities: Array.isArray(raw?.opportunities) ? raw.opportunities : [],
      scan_summary: raw?.scan_summary ?? { total_scanned: 0, opportunities_found: 0, scan_time: new Date().toISOString() },
    };
  }

  protected wrap(data: OpportunityScanResult): ToolResponse<OpportunityScanResult> {
    return { success: true, data };
  }
}
