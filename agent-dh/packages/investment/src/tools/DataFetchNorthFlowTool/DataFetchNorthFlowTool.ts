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
    // 2026-08-29: 北向资金数据源已不可用，直接返回替代方案指导
    // 背景：交易所自 2024-08-17 起停止披露北向每日净买入，港交所 CCASS 数据访问也已受限

    return {
      days: args.days || 5,
      data: [],
      summary: {
        total_net_flow: 0,
        sh_net_flow: 0,
        sz_net_flow: 0,
        latest_date: new Date().toISOString().split('T')[0],
        method: 'unavailable',
        message: '北向资金数据源已不可用（交易所停止披露 + 港交所数据访问受限）',
      },
      alternatives: [
        {
          name: 'Wind 终端',
          description: '北向资金实时监控，专业金融终端',
          url: 'https://www.wind.com.cn',
        },
        {
          name: '东方财富 Choice 终端',
          description: '提供北向资金流向数据',
          url: 'https://choice.eastmoney.com',
        },
        {
          name: '聚宽 JQData API',
          description: '量化数据接口，支持北向资金查询',
          url: 'https://www.joinquant.com/help/api/help#name:Stock',
        },
        {
          name: 'Tushare Pro API',
          description: '金融数据接口，需要积分权限',
          url: 'https://tushare.pro/document/2',
        },
        {
          name: '沪深港通官网',
          description: '港交所官方数据，需手动查询',
          url: 'http://sc.hkex.com.hk',
        },
      ],
    } as DataFetchNorthFlowResult;
  }

  protected wrap(data: DataFetchNorthFlowResult): ToolResponse<DataFetchNorthFlowResult> {
    return { success: true, data };
  }
}
