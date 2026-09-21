import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { manipulationDetectPrompt, ManipulationDetectParams, ManipulationDetectResult } from './prompt';

/**
 * Manipulation Detection Tool
 *
 * 检测个股操纵迹象（M7-3 基础能力）
 */
export class ManipulationDetectTool extends BaseTool<
  ManipulationDetectParams,
  ManipulationDetectResult
> {
  protected readonly metadata: ToolMetadata = {
    name: 'manipulation_detect',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = manipulationDetectPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: ManipulationDetectParams): ValidationResult {
    if (!args.symbol || typeof args.symbol !== 'string') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是字符串',
        received: typeof args.symbol,
        expected: 'string',
        example: '600519',
      };
    }
    if (!/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是 6 位数字',
        received: args.symbol,
        expected: '6位数字',
        example: '600519',
      };
    }
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(
    args: ManipulationDetectParams,
    _context: ToolContext
  ): Promise<ManipulationDetectResult> {
    try {
      const response: any = await this.qv2.detectManipulation({
        symbol: args.symbol,
        ...(args.days ? { days: args.days } : {}),
      });

      return sanitizeLossless({
        symbol: response?.symbol ?? args.symbol,
        risk_level: response?.risk_level ?? 'low',
        signals: response?.signals ?? [],
        volume_anomaly: response?.volume_anomaly ?? false,
        price_pump: response?.price_pump ?? false,
        wash_trade: response?.wash_trade ?? false,
        description: response?.description ?? '无数据',
      });
    } catch (e: any) {
      throw new Error(
        `操纵检测失败: ${e?.message ?? e}`,
        { cause: e }
      );
    }
  }
}
