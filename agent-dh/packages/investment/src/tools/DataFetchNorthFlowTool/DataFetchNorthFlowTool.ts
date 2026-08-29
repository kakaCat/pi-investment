import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchNorthFlowPrompt, DataFetchNorthFlowParams, DataFetchNorthFlowResult } from './prompt';

export class DataFetchNorthFlowTool extends BaseTool<DataFetchNorthFlowParams, DataFetchNorthFlowResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_north_flow',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = dataFetchNorthFlowPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DataFetchNorthFlowParams): ValidationResult {
    if (args.days !== undefined && (args.days <= 0 || !Number.isInteger(args.days))) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'days',
        issue: 'days 必须是正整数',
        received: args.days,
        expected: '正整数（例如 5, 20）',
      };
    }
    return { success: true };
  }

  protected async execute(
    args: DataFetchNorthFlowParams,
    context: ToolContext
  ): Promise<DataFetchNorthFlowResult> {
    const days = args.days || 5;
    const result = await this.qv2.getNorthFlow(days);
    return result as DataFetchNorthFlowResult;
  }

  protected wrap(data: DataFetchNorthFlowResult): ToolResponse<DataFetchNorthFlowResult> {
    return { success: true, data };
  }
}
