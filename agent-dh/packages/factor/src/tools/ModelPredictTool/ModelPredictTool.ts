/**
 * ModelPredictTool - ML 模型上涨概率预测
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { modelPredictPrompt, ModelPredictParams } from './prompt';

export class ModelPredictTool extends BaseTool<ModelPredictParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'model_predict',
    category: 'factor',
    version: '1.0.0',
    timeoutMs: 120000,
  };

  protected readonly prompt = modelPredictPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: ModelPredictParams): ValidationResult {
    if (!Array.isArray(args.symbols) || args.symbols.length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbols',
        issue: 'symbols 必须是非空数组',
        expected: '["601857","600519"]',
        example: '["601857"]',
      };
    }
    if (args.symbols.length > 50) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbols',
        issue: 'symbols 一次最多 50 只',
        received: String(args.symbols.length),
        expected: '≤ 50',
      };
    }
    const bad = args.symbols.find((s) => !/^\d{6}$/.test(String(s)));
    if (bad) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbols',
        issue: `非法股票代码: ${bad}（必须 6 位数字）`,
        received: String(bad),
        expected: '6位数字',
        example: '601857',
      };
    }
    return { success: true };
  }

  protected async execute(args: ModelPredictParams, _context: ToolContext): Promise<any> {
    const result = await this.qv2.mlPredict({ symbols: args.symbols.map(String) });
    return sanitizeLossless({
      predictions: result?.predictions ?? [],
      model_gate: result?.model_gate ?? null,
      count: result?.predictions?.length ?? 0,
    });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
